"""
命令行/文件操作技能 - 工具实现
所有路径限制在工作区（workspace）内；删除等危险操作由调用方确认后再执行。
"""

from __future__ import annotations

from pathlib import Path

from core.config import Config

# 工作区根目录，所有路径必须在此之下
WORKSPACE_ROOT = Config.WORKSPACE_DIR


def _resolve_and_validate(path_str: str, must_exist: bool = False) -> Path | str:
    """
    将用户传入的路径解析为工作区内的绝对路径。
    - 相对路径视为相对于工作区根
    - 绝对路径必须在工作区内
    若非法则返回错误字符串，否则返回 Path。
    """
    path_str = (path_str or "").strip()
    if not path_str:
        return "错误：路径不能为空"

    try:
        p = Path(path_str)
        if not p.is_absolute():
            p = (WORKSPACE_ROOT / p).resolve()
        else:
            p = p.resolve()
    except (OSError, RuntimeError) as e:
        return f"错误：路径无效 - {e}"

    try:
        root = WORKSPACE_ROOT.resolve()
        p.relative_to(root)
    except ValueError:
        return f"错误：路径必须在工作区内。工作区: {root}"
    except Exception as e:
        return f"错误：路径校验失败 - {e}"

    if must_exist and not p.exists():
        return f"错误：路径不存在: {p}"

    return p


def list_dir(path: str = ".") -> str:
    """
    列出目录下的文件和子目录（仅工作区内）。

    参数:
        path: 相对工作区的路径，默认 "." 表示工作区根目录

    返回:
        多行字符串，每行一个条目；若为文件则带 [文件] 标记。
    """
    res = _resolve_and_validate(path, must_exist=True)
    if isinstance(res, str):
        return res
    if not res.is_dir():
        return f"错误：不是目录: {res}"

    lines = []
    try:
        for child in sorted(res.iterdir()):
            name = child.name
            if child.is_file():
                lines.append(f"  [文件]  {name}")
            else:
                lines.append(f"  [目录]  {name}")
    except PermissionError:
        return f"错误：无权限读取目录 {res}"
    except OSError as e:
        return f"错误：{e}"

    if not lines:
        return f"（空目录） {res}"
    return f"目录: {res}\n" + "\n".join(lines)


def read_file(path: str, encoding: str = "utf-8", max_lines: int = 2000) -> str:
    """
    读取工作区内的文本文件内容。

    参数:
        path: 相对工作区的文件路径
        encoding: 编码，默认 utf-8
        max_lines: 最多返回行数，防止过大文件，默认 2000

    返回:
        文件内容；若超过 max_lines 会截断并注明。
    """
    res = _resolve_and_validate(path, must_exist=True)
    if isinstance(res, str):
        return res
    if res.is_dir():
        return f"错误：是目录不是文件: {res}"

    try:
        text = res.read_text(encoding=encoding)
    except UnicodeDecodeError:
        return f"错误：无法以 {encoding} 解码，可能为二进制文件: {res}"
    except PermissionError:
        return f"错误：无权限读取文件 {res}"
    except OSError as e:
        return f"错误：{e}"

    lines = text.splitlines()
    if len(lines) > max_lines:
        head = "\n".join(lines[:max_lines])
        return f"{head}\n\n... (已截断，共 {len(lines)} 行，仅显示前 {max_lines} 行)"
    return text


def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """
    在工作区内创建或覆盖写入文本文件。若父目录不存在会自动创建。

    参数:
        path: 相对工作区的文件路径
        content: 要写入的文本内容
        encoding: 编码，默认 utf-8

    返回:
        成功信息或错误说明。
    """
    res = _resolve_and_validate(path, must_exist=False)
    if isinstance(res, str):
        return res
    if res.is_dir():
        return f"错误：路径是目录不能写入文件: {res}"

    try:
        res.parent.mkdir(parents=True, exist_ok=True)
        res.write_text(content, encoding=encoding)
        return f"已写入 {len(content)} 字符到: {res}"
    except PermissionError:
        return f"错误：无权限写入 {res}"
    except OSError as e:
        return f"错误：{e}"


def create_dir(path: str) -> str:
    """
    在工作区内创建目录（含多级父目录）。

    参数:
        path: 相对工作区的目录路径

    返回:
        成功信息或错误说明。
    """
    res = _resolve_and_validate(path, must_exist=False)
    if isinstance(res, str):
        return res
    if res.exists() and not res.is_dir():
        return f"错误：已存在同名文件: {res}"

    try:
        res.mkdir(parents=True, exist_ok=True)
        return f"已创建目录: {res}"
    except PermissionError:
        return f"错误：无权限创建目录 {res}"
    except OSError as e:
        return f"错误：{e}"


def search_files(
    query: str,
    path: str = ".",
    file_pattern: str = "*",
    case_sensitive: bool = False,
    max_results: int = 100,
) -> str:
    """
    在工作区内按文件名或内容搜索。

    参数:
        query: 搜索关键词（匹配文件名或文件内容）
        path: 相对工作区的起始目录，默认 "."
        file_pattern: 文件名通配符，默认 "*" 表示所有文件
        case_sensitive: 是否区分大小写，默认 False
        max_results: 最多返回的匹配条数，默认 100

    返回:
        匹配到的文件路径及所在行（内容匹配时）；仅文件名匹配时只列路径。
    """
    res = _resolve_and_validate(path, must_exist=True)
    if isinstance(res, str):
        return res
    if not res.is_dir():
        return f"错误：不是目录: {res}"

    query = (query or "").strip()
    if not query:
        return "错误：搜索关键词不能为空"

    q = query if case_sensitive else query.lower()
    results: list[str] = []
    count = 0

    try:
        for fp in res.rglob(file_pattern):
            if not fp.is_file():
                continue
            try:
                rel = fp.relative_to(WORKSPACE_ROOT)
            except ValueError:
                continue
            rel_str = str(rel)

            # 文件名匹配
            name_match = q in fp.name if case_sensitive else q in fp.name.lower()
            if name_match:
                if count < max_results:
                    results.append(f"  [文件] {rel_str}")
                count += 1
                continue

            # 内容匹配（文本文件）
            if count >= max_results:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except (OSError, PermissionError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                line_check = line if case_sensitive else line.lower()
                if q in line_check:
                    results.append(f"  {rel_str}:{i}  {line.strip()[:80]}")
                    count += 1
                    if count >= max_results:
                        break
            if count >= max_results:
                break
    except PermissionError:
        return f"错误：无权限遍历 {res}"
    except OSError as e:
        return f"错误：{e}"

    if not results:
        return f"未找到包含「{query}」的匹配（路径: {res}）"
    head = f"共 {min(count, max_results)} 条匹配（路径: {res}）:\n"
    return head + "\n".join(results[:max_results])


def delete_path(path: str) -> str:
    """
    删除工作区内的文件或空目录。
    **此为危险操作，执行前需由用户确认。**

    参数:
        path: 相对工作区的路径

    返回:
        成功信息或错误说明。
    """
    res = _resolve_and_validate(path, must_exist=True)
    if isinstance(res, str):
        return res

    if res == WORKSPACE_ROOT.resolve():
        return "错误：不能删除工作区根目录"

    try:
        if res.is_file():
            res.unlink()
            return f"已删除文件: {res}"
        if res.is_dir():
            if any(res.iterdir()):
                return f"错误：目录非空，无法删除: {res}。请先删除其内容或使用其他方式。"
            res.rmdir()
            return f"已删除空目录: {res}"
    except PermissionError:
        return f"错误：无权限删除 {res}"
    except OSError as e:
        return f"错误：{e}"

    return f"错误：路径不存在或无法删除: {res}"
