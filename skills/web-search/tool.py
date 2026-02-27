"""
网页搜索技能 - 工具实现
使用 ddgs（原 duckduckgo_search）进行网页搜索，无需 API Key；
提供获取当前日期时间功能。
"""

from __future__ import annotations

from datetime import datetime

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
        return f"错误：获取时间失败 - {e}"


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

    # 依次尝试不同 backend，避免单一引擎不可用
    for backend in ["duckduckgo", "brave", "bing", "auto"]:
        try:
            ddgs = DDGS()
            gen = ddgs.text(query, max_results=max_results, backend=backend)
            results = list(gen) if gen else []
            if results:
                break
        except Exception as exc:
            last_error = exc
            continue

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
