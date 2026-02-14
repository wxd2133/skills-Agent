"""
字符绘制技能 - 工具实现
表格使用 tabulate 库；方框与条形图为手绘。
"""

from __future__ import annotations

from tabulate import tabulate


def draw_table(headers: list[str], rows: list[list[str]]) -> str:
    """
    绘制带边框的文本表格（使用 tabulate 库，grid 格式）。

    参数:
        headers: 表头列名列表
        rows:    数据行，每行为与表头等长的字符串列表

    返回:
        多行字符串，可直接打印或放入代码块。
    """
    if not headers:
        return "错误：表头不能为空"

    cols = len(headers)
    data_rows = [[str(cell) for cell in row] for row in rows]
    for row in data_rows:
        while len(row) < cols:
            row.append("")
        if len(row) > cols:
            row[:] = row[:cols]

    return tabulate(
        data_rows,
        headers=headers,
        tablefmt="grid",
        stralign="left",
    )


def draw_box(width: int, height: int, title: str = "") -> str:
    """
    绘制矩形方框，可选框内标题。

    参数:
        width:  宽度（字符数）
        height: 高度（行数）
        title:  框内第一行标题

    返回:
        多行字符串。
    """
    width = max(2, int(width))
    height = max(2, int(height))

    top = "+" + "-" * (width - 2) + "+"
    mid = "|" + " " * (width - 2) + "|"

    lines = [top]
    for i in range(height - 2):
        if i == 0 and title:
            t = title[: width - 4].center(width - 2)
            lines.append("|" + t + "|")
        else:
            lines.append(mid)
    lines.append(top)
    return "\n".join(lines)


def draw_shape(shape: str, width: int, height: int, fill: str = "*") -> str:
    """
    绘制简单形状：rectangle / triangle / diamond。

    参数:
        shape:  形状类型
        width:  宽度（字符数）
        height: 高度（行数）
        fill:   填充字符

    返回:
        多行字符串。
    """
    width = max(1, int(width))
    height = max(1, int(height))
    ch = fill if len(fill) == 1 else "*"

    if shape == "rectangle":
        line = ch * width
        return "\n".join(line for _ in range(height))

    if shape == "triangle":
        # 等腰三角形，底边宽 width，高 height 行
        lines = []
        for r in range(height):
            w = int(round((r + 1) * width / height)) or 1
            pad = (width - w) // 2
            lines.append(" " * pad + ch * w)
        return "\n".join(lines)

    if shape == "diamond":
        # 菱形：上半部分 + 下半部分
        lines = []
        half = (height + 1) // 2
        for r in range(half):
            w = int(round((r + 1) * width / half)) or 1
            pad = (width - w) // 2
            lines.append(" " * pad + ch * w)
        for r in range(half - 1, -1, -1):
            if r == half - 1 and height % 2 == 1:
                continue
            w = int(round((r + 1) * width / half)) or 1
            pad = (width - w) // 2
            lines.append(" " * pad + ch * w)
        return "\n".join(lines) if lines else ch

    return f"错误：不支持的形状 '{shape}'，可选 rectangle / triangle / diamond"


def draw_ascii_art(lines: list[str], width: int | None = None) -> str:
    """
    按行拼接字符画，保证对齐。用于猫、脸等多行组合图，避免在回答里手排错位。

    参数:
        lines: 每一行字符串，从上到下顺序
        width: 可选；若给出，则每行右侧补空格到该宽度，保证所有行等长

    返回:
        多行字符串。
    """
    if not lines:
        return "错误：lines 不能为空"
    lines = [str(ln) for ln in lines]
    if width is not None and int(width) > 0:
        w = int(width)
        lines = [ln[:w].ljust(w) for ln in lines]
    return "\n".join(lines)


def draw_bar(items: list[dict], bar_width: int = 20) -> str:
    """
    绘制横向条形图。

    参数:
        items:     列表，每项为 {"label": str, "value": number}
        bar_width: 最长条对应的字符数

    返回:
        多行字符串。
    """
    if not items:
        return "错误：items 不能为空"

    values = []
    labels = []
    for x in items:
        if isinstance(x, dict):
            labels.append(str(x.get("label", "")))
            try:
                values.append(float(x.get("value", 0)))
            except (TypeError, ValueError):
                values.append(0.0)
        else:
            labels.append(str(x))
            values.append(0.0)

    max_val = max(values) if values else 1
    if max_val <= 0:
        max_val = 1

    max_label_len = max(len(l) for l in labels) if labels else 0
    max_label_len = max(max_label_len, 1)

    lines = []
    for label, val in zip(labels, values):
        w = int(round(val / max_val * bar_width)) if max_val else 0
        bar = "█" * w if w else ""
        lines.append(f"{label.rjust(max_label_len)} | {bar} {val}")

    return "\n".join(lines)
