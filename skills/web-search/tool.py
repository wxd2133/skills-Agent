"""
网页搜索技能 - 工具实现
面向国内网络：优先必应中国、百度，再用 360 搜索兜底。
提供获取当前日期时间、根据 URL 获取网页内容功能。
"""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from datetime import datetime
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, urlparse

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


_SEARCH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_SEARCH_SOURCES = (
    ("必应", "_search_bing"),
    ("百度", "_search_baidu"),
    ("360搜索", "_search_360"),
)


def _plain_text(fragment: str) -> str:
    """去掉标签并还原 HTML 实体。"""
    text = re.sub(r"<[^>]+>", "", fragment or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_search_html(url: str, timeout: int = 8) -> tuple[str, str]:
    """请求固定的公网搜索地址，返回最终 URL 和 HTML。"""
    req = Request(
        url,
        headers={
            "User-Agent": _SEARCH_UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        raw = resp.read(400_000)
    return final_url, raw.decode("utf-8", errors="replace")


def _search_bing(query: str, max_results: int) -> list[dict[str, str]]:
    """必应中国。国内一般可直接打开，结果在 li.b_algo 里。"""
    url = "https://cn.bing.com/search?" + urlencode({"q": query, "ensearch": "0", "setlang": "zh-Hans"})
    _, page = _fetch_search_html(url)
    results: list[dict[str, str]] = []
    for block in re.findall(r'<li class="b_algo".*?</li>', page, flags=re.S):
        link = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        if not link:
            continue
        href = html.unescape(link.group(1)).strip()
        if "bing.com/aclick" in href:
            continue
        snippet = re.search(r"<p[^>]*>(.*?)</p>", block, flags=re.S)
        title = _plain_text(link.group(2))
        if not title:
            continue
        results.append({
            "title": title,
            "body": _plain_text(snippet.group(1)) if snippet else "",
            "href": href,
        })
        if len(results) >= max_results:
            break
    return results


def _search_baidu(query: str, max_results: int) -> list[dict[str, str]]:
    """百度网页搜索。遇到安全验证页时放弃，交给下一个来源。"""
    url = "https://www.baidu.com/s?" + urlencode({"wd": query, "ie": "utf-8", "rn": str(max_results)})
    final_url, page = _fetch_search_html(url)
    if "百度安全验证" in page or "wappass.baidu.com" in final_url:
        raise RuntimeError("百度返回了安全验证页")
    results: list[dict[str, str]] = []
    for block in re.findall(r'<h3[^>]*class="[^"]*\bt\b[^"]*"[^>]*>.*?</h3>', page, flags=re.S):
        link = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        if not link:
            continue
        title = _plain_text(link.group(2))
        href = html.unescape(link.group(1)).strip()
        if not title or not href.startswith("http"):
            continue
        results.append({"title": title, "body": "", "href": href})
        if len(results) >= max_results:
            break
    return results


def _search_360(query: str, max_results: int) -> list[dict[str, str]]:
    """360 搜索。优先用 data-mdurl 里的真实链接。"""
    url = "https://www.so.com/s?" + urlencode({"q": query})
    _, page = _fetch_search_html(url)
    results: list[dict[str, str]] = []
    pattern = re.compile(
        r'<h3[^>]*class="[^"]*res-title[^"]*"[^>]*>\s*<a\s+([^>]+)>(.*?)</a>',
        re.S,
    )
    for attrs, title_html in pattern.findall(page):
        real = re.search(r'data-mdurl="([^"]+)"', attrs)
        href_match = re.search(r'href="([^"]+)"', attrs)
        href = html.unescape((real or href_match).group(1)).strip() if (real or href_match) else ""
        title = _plain_text(title_html)
        if not title or not href.startswith("http"):
            continue
        results.append({"title": title, "body": "", "href": href})
        if len(results) >= max_results:
            break
    return results


def web_search(query: str, max_results: int = 5) -> str:
    """
    在网页上搜索信息，返回标题、摘要和链接。
    顺序为必应中国、百度、360 搜索，某个来源有结果就停止。

    参数:
        query:        搜索关键词或问句
        max_results:  返回结果数量，默认 5

    返回:
        格式化的搜索结果文本；失败时返回错误说明。
    """
    query = (query or "").strip()
    if not query:
        return "错误：搜索关键词不能为空。"

    max_results = max(1, min(int(max_results), 15))
    errors: list[str] = []
    found: list[dict[str, str]] = []
    source_name = ""
    searchers = {
        "必应": _search_bing,
        "百度": _search_baidu,
        "360搜索": _search_360,
    }

    for name, _ in _SEARCH_SOURCES:
        try:
            found = searchers[name](query, max_results)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            continue
        if found:
            source_name = name
            break
        errors.append(f"{name}: 无结果")

    if not found:
        msg = f"未找到与「{query}」相关的网页结果，可尝试换一组关键词。"
        if errors:
            msg += "\n（" + "；".join(errors) + "）"
        return msg

    lines = [f"来源: {source_name}", f"搜索「{query}」共 {len(found)} 条结果：\n"]
    for i, item in enumerate(found, 1):
        lines.append(f"{i}. {item.get('title') or '(无标题)'}")
        body = (item.get("body") or "").strip()
        if body:
            lines.append(f"   {body}")
        href = (item.get("href") or "").strip()
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
