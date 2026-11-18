"""
网页搜索技能 - 工具实现
使用 ddgs（原 duckduckgo_search）进行网页搜索，无需 API Key；
提供获取当前日期时间、根据 URL 获取网页内容功能。
"""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
import time
from datetime import datetime
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore[misc, assignment]


def get_time(timezone: str = "") -> str:
    """
    获取当前日期和时间，可用于回答「今天几号」「现在几点」或为搜索补充时间上下文。

    参数:
        timezone: 时区名称，如 "Asia/Shanghai"、"UTC"、"America/New_York"；空则使用本机本地时间

    返回:
        格式化的日期时间字符串（含星期）。
    """
    try:
        if (timezone or "").strip():
            if ZoneInfo is None:
                return "错误：获取指定时区需要 Python 3.9+ 的 zoneinfo，当前使用本机时间。"
            tz = ZoneInfo(timezone.strip())
            now = datetime.now(tz)
            tz_label = timezone.strip()
        else:
            now = datetime.now()
            tz_label = "本机"
        weekday = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")[now.weekday()]
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        return f"当前时间（{tz_label}）\n日期: {date_str} {weekday}\n时间: {time_str}"
    except Exception as e:
        hint = ""
        if "No time zone found" in str(e):
            hint = " 请安装 tzdata（pip install tzdata）后重试。"
        return f"错误：获取时间失败 - {e}.{hint}"


def web_search(query: str, max_results: int = 5) -> str:
    """
    在网页上搜索信息，返回标题、摘要和链接。

    参数:
        query:        搜索关键词或问句
        max_results:  返回结果数量，默认 5

    返回:
        格式化的搜索结果文本；失败时返回错误说明。
    """
    try:
        from ddgs import DDGS
    except ImportError:
        return (
            "错误：未安装网页搜索依赖。请执行 pip install ddgs 后重试。"
        )

    query = (query or "").strip()
    if not query:
        return "错误：搜索关键词不能为空。"

    max_results = max(1, min(int(max_results), 15))
    results: list = []
    last_error: Exception | None = None
    # 单个引擎超时短一些，整次搜索还有总预算，避免一个工具调用拖住整轮推理
    per_backend_timeout = 6
    total_budget_seconds = 16
    started = time.monotonic()

    for backend in ("duckduckgo", "bing", "brave"):
        remaining = total_budget_seconds - (time.monotonic() - started)
        if remaining < 1:
            last_error = TimeoutError("搜索总时间已用完")
            break
        timeout = max(1, min(per_backend_timeout, int(remaining)))
        box: dict = {}

        def _run(backend: str = backend, timeout: int = timeout) -> None:
            try:
                ddgs = DDGS(timeout=timeout)
                found = ddgs.text(query, max_results=max_results, backend=backend) or []
                box["results"] = list(found)
            except Exception as exc:
                box["error"] = exc

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(timeout + 1)
        if worker.is_alive():
            last_error = TimeoutError(f"{backend} 超过 {timeout} 秒")
            continue
        if "error" in box:
            last_error = box["error"]
            continue
        results = box.get("results") or []
        if results:
            break

    if not results:
        msg = f"未找到与「{query}」相关的网页结果，可尝试换一组关键词。"
        if last_error:
            msg += f"\n（最后错误: {last_error}）"
        return msg

    lines = [f"搜索「{query}」共 {len(results)} 条结果：\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip() or "(无标题)"
        body = (r.get("body") or r.get("snippet") or "").strip() or "(无摘要)"
        href = (r.get("href") or r.get("link") or "").strip()
        lines.append(f"{i}. {title}")
        lines.append(f"   {body}")
        if href:
            lines.append(f"   链接: {href}")
        lines.append("")

    return "\n".join(lines).strip()


_MAX_DOWNLOAD_BYTES = 512_000


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """本地、内网、链路本地、保留地址和组播地址都不允许抓取。"""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_blocked_ip(ip.ipv4_mapped)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _reject_unsafe_url(url: str) -> str | None:
    """公网 http/https 返回 None，其余返回给调用方的错误说明。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "错误：仅支持 http/https 链接。"
    host = (parsed.hostname or "").strip().rstrip(".").lower()
    if not host:
        return "错误：URL 缺少主机名。"
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal"} or host.endswith(".local"):
        return "错误：不允许访问本地或内网地址。"

    literal_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and _is_blocked_ip(literal_ip):
        return "错误：不允许访问本地或内网地址。"

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror as exc:
        return f"错误：无法解析主机 - {exc}"
    if not infos:
        return "错误：无法解析主机。"
    for info in infos:
        try:
            resolved = ipaddress.ip_address(info[4][0])
        except ValueError:
            return "错误：无法解析主机。"
        if _is_blocked_ip(resolved):
            return "错误：不允许访问本地或内网地址。"
    return None


class _SafeRedirectHandler(HTTPRedirectHandler):
    """重定向目标也要经过同一套地址检查。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        rejected = _reject_unsafe_url(newurl)
        if rejected:
            raise HTTPError(req.full_url, code, rejected, headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get_webpage(url: str, max_chars: int = 12000) -> str:
    """
    根据 URL 获取网页正文内容（去标签、UTF-8 解码），便于归纳或引用。

    参数:
        url: 网页 URL，须为 http 或 https
        max_chars: 最多返回字符数，默认 12000，避免过长

    返回:
        网页文本片段或错误说明。
    """
    url = (url or "").strip()
    if not url:
        return "错误：URL 不能为空。"
    rejected = _reject_unsafe_url(url)
    if rejected:
        return rejected
    try:
        max_chars = int(max_chars)
    except (TypeError, ValueError):
        max_chars = 12000
    max_chars = max(500, min(max_chars, 20000))

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SkillAgent/1.0)"})
        opener = build_opener(_SafeRedirectHandler)
        with opener.open(req, timeout=15) as resp:
            chunks: list[bytes] = []
            total = 0
            while total < _MAX_DOWNLOAD_BYTES:
                block = resp.read(min(65536, _MAX_DOWNLOAD_BYTES - total))
                if not block:
                    break
                chunks.append(block)
                total += len(block)
        text = b"".join(chunks).decode("utf-8", errors="replace")
    except HTTPError as e:
        reason = str(e.reason or "")
        if reason.startswith("错误："):
            return reason
        return f"错误：HTTP {e.code} - {e.reason}"
    except URLError as e:
        return f"错误：无法访问 - {e.reason}"
    except Exception as e:
        return f"错误：{e}"

    # 简单去标签，保留可见文本
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n... (已截断)"
    return text or "（页面无正文内容）"
