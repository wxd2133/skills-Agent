"""
网页搜索技能 - 工具实现
使用 ddgs（原 duckduckgo_search）进行网页搜索，无需 API Key。
"""

from __future__ import annotations


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
