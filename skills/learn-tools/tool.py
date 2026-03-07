"""
学习/自我升级技能 - 工具实现
将新技能保存到 skills/user/ 目录，需用户确认；加载由系统工具 load_new_skill 完成。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from core.config import Config

USER_SKILLS_DIR = Config.USER_SKILLS_DIR


def save_skill(
    name: str,
    description: str,
    tools_spec: str,
    manual_content: str,
    tool_py_content: str,
) -> str:
    """
    将新技能保存到 skills/user/<name>/（SKILL.md + tool.py）。
    此为写盘操作，执行前需用户确认。保存后请调用 load_new_skill(name) 使本会话立即可用。

    参数:
        name: 技能目录名（英文、数字、连字符），如 my-helper
        description: 技能简短描述，会出现在「可用技能」列表中
        tools_spec: JSON 数组，每项为 {"name":"工具名","function":"函数名","parameters":{...},"needs_confirmation":false}
        manual_content: SKILL.md 的 Markdown 正文（不含 YAML frontmatter）
        tool_py_content: tool.py 的完整 Python 源码

    返回:
        成功或错误信息。
    """
    name = (name or "").strip()
    if not name:
        return "错误：技能名称不能为空。"
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        return "错误：技能名称仅允许英文、数字、连字符和下划线。"

    # 禁止覆盖：同名技能已存在会与现有工具冲突，导致失效
    out_dir = USER_SKILLS_DIR / name
    if out_dir.exists() and (out_dir / "SKILL.md").exists():
        return (
            f"错误：已存在同名技能「{name}」。"
            "请改用新名称保存，或先删除旧技能目录 skills/user/" + name + " 后再保存。"
        )

    try:
        spec_list = json.loads(tools_spec) if isinstance(tools_spec, str) else tools_spec
    except json.JSONDecodeError as e:
        return f"错误：tools_spec 不是合法 JSON: {e}"
    if not isinstance(spec_list, list) or not spec_list:
        return "错误：tools_spec 须为非空 JSON 数组。"

    description = (description or "").strip() or name
    manual_content = (manual_content or "").strip() or f"# {name}\n\n无额外说明。"
    tool_py_content = (tool_py_content or "").strip()
    if not tool_py_content:
        return "错误：tool_py_content 不能为空。"

    # 规范 tools 项：补齐 function、parameters，并校验
    tools = []
    seen_names: set[str] = set()
    for t in spec_list:
        if not isinstance(t, dict):
            continue
        tool_name = (t.get("name") or "").strip() or "unnamed"
        func_name = (t.get("function") or t.get("name") or "unnamed").strip()
        if tool_name in seen_names:
            return f"错误：工具名重复「{tool_name}」，同一技能内工具名必须唯一。"
        seen_names.add(tool_name)
        entry = {
            "name": tool_name,
            "function": func_name,
            "parameters": t.get("parameters", {"type": "object", "properties": {}, "required": []}),
        }
        if t.get("needs_confirmation"):
            entry["needs_confirmation"] = True
        tools.append(entry)
    if not tools:
        return "错误：tools_spec 中无有效工具项。"

    # 校验 tool.py 中必须定义 tools_spec 里声明的每个 function，否则加载时会报错
    for entry in tools:
        fn = entry["function"]
        if not re.search(rf"\bdef\s+{re.escape(fn)}\s*\(", tool_py_content):
            return (
                f"错误：tool_py_content 中未定义函数「{fn}」。"
                "SKILL.md 中声明的每个 function 都必须在 tool.py 里存在对应 def。"
            )

    front = {"name": name, "description": description, "tools": tools}
    frontmatter = "---\n" + yaml.dump(front, allow_unicode=True, default_flow_style=False, sort_keys=False).strip() + "\n---"
    skill_md_content = frontmatter + "\n\n" + manual_content

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
        (out_dir / "tool.py").write_text(tool_py_content, encoding="utf-8")
        return f"已保存技能到 {out_dir}。请调用 load_new_skill(name=\"{name}\") 使本会话立即可用。"
    except OSError as e:
        return f"错误：写入失败 - {e}"
