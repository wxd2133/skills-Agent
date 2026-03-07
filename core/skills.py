"""
技能加载器模块
负责从 skills/ 目录动态发现和加载技能插件。

每个技能是 skills/ 下的一个子目录，要求包含：
  - SKILL.md     技能定义文件（YAML Frontmatter + Markdown 操作手册）
  - tool.py      工具实现（包含 frontmatter 中声明的函数）

SKILL.md 格式说明：
  ---
  name: 技能名称
  description: 技能简介
  tools:
    - name: 工具名
      function: tool.py 中的函数名
      parameters: { JSON Schema }
  ---
  # Markdown 正文
  Agent 的操作手册，描述工具用法、参数详情、注意事项等。
"""

from __future__ import annotations

import importlib.util
import logging
import re
from pathlib import Path
from typing import Any, Callable

import yaml

from core.config import Config

logger = logging.getLogger(__name__)


# ---------- SKILL.md 解析 ----------

def _parse_skill_md(filepath: Path) -> tuple[dict[str, Any], str]:
    """
    解析 SKILL.md 文件，拆分为 YAML frontmatter 和 Markdown 正文。

    参数:
        filepath: SKILL.md 的路径

    返回:
        (frontmatter_dict, markdown_body) 元组。
    """
    raw = filepath.read_text(encoding="utf-8")

    # 匹配 --- 包裹的 YAML frontmatter
    pattern = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
    match = pattern.match(raw)

    if not match:
        raise ValueError(f"SKILL.md 格式错误：缺少 YAML Frontmatter（需要 --- 包裹）: {filepath}")

    frontmatter_str = match.group(1)
    body = match.group(2).strip()

    frontmatter = yaml.safe_load(frontmatter_str)
    if not isinstance(frontmatter, dict):
        raise ValueError(f"SKILL.md Frontmatter 不是合法的 YAML 映射: {filepath}")

    return frontmatter, body


# ---------- 数据结构 ----------

class ToolSpec:
    """单个工具的规格说明（对应 OpenAI function calling 的格式）。"""

    def __init__(self, name: str, description: str, parameters: dict[str, Any],
                 execute_fn: Callable[..., str], needs_confirmation: bool = False):
        self.name = name
        self.description = description
        self.parameters = parameters        # JSON Schema
        self.execute_fn = execute_fn        # 实际执行函数
        self.needs_confirmation = needs_confirmation  # 危险操作，执行前需用户确认

    def to_openai_tool(self) -> dict[str, Any]:
        """转为 OpenAI tools 参数格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class Skill:
    """一个技能包，可能包含多个工具。"""

    def __init__(self, name: str, description: str, tools: list[ToolSpec],
                 manual: str, path: Path):
        self.name = name
        self.description = description
        self.tools = tools
        self.manual = manual    # Markdown 正文（Agent 操作手册）
        self.path = path

    def __repr__(self) -> str:
        tool_names = ", ".join(t.name for t in self.tools)
        return f"<Skill '{self.name}' tools=[{tool_names}]>"


# ---------- 加载逻辑 ----------

def _load_skill(skill_dir: Path) -> Skill | None:
    """从指定目录加载单个技能。"""
    skill_md_path = skill_dir / "SKILL.md"
    tool_path = skill_dir / "tool.py"

    if not skill_md_path.exists():
        logger.warning("跳过 %s：缺少 SKILL.md", skill_dir.name)
        return None

    if not tool_path.exists():
        logger.warning("跳过 %s：缺少 tool.py", skill_dir.name)
        return None

    # ---- 解析 SKILL.md ----
    try:
        meta, manual = _parse_skill_md(skill_md_path)
    except ValueError as exc:
        logger.error("解析失败: %s", exc)
        return None

    skill_name = meta.get("name", skill_dir.name)
    skill_desc = meta.get("description", "")

    # ---- 动态导入 tool.py ----
    spec = importlib.util.spec_from_file_location(f"skill_{skill_dir.name}", tool_path)
    if spec is None or spec.loader is None:
        logger.error("无法加载模块: %s", tool_path)
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    # ---- 解析工具列表 ----
    tools: list[ToolSpec] = []
    for tool_def in meta.get("tools", []):
        fn_name = tool_def["function"]  # tool.py 中的函数名
        fn = getattr(module, fn_name, None)
        if fn is None:
            logger.warning("技能 '%s' 中找不到函数 '%s'", skill_name, fn_name)
            continue

        # 工具描述：优先用 frontmatter 中的，否则从 Markdown 正文无法自动提取，留空
        tool_desc = tool_def.get("description", "")
        needs_confirmation = bool(tool_def.get("needs_confirmation", False))

        tools.append(ToolSpec(
            name=tool_def["name"],
            description=tool_desc,
            parameters=tool_def.get("parameters", {"type": "object", "properties": {}}),
            execute_fn=fn,
            needs_confirmation=needs_confirmation,
        ))

    if not tools:
        logger.warning("技能 '%s' 没有有效工具，跳过", skill_name)
        return None

    logger.info("已加载技能: %s (%d 个工具, 操作手册 %d 字符)",
                skill_name, len(tools), len(manual))
    return Skill(name=skill_name, description=skill_desc, tools=tools,
                 manual=manual, path=skill_dir)


def load_skill_from_dir(skill_dir: Path) -> Skill | None:
    """
    从指定目录加载单个技能（用于运行时动态加载）。

    参数:
        skill_dir: 技能目录，须包含 SKILL.md 与 tool.py

    返回:
        Skill 或 None
    """
    return _load_skill(skill_dir)


def load_all_skills(skills_dir: Path | None = None) -> list[Skill]:
    """
    扫描技能目录，加载全部技能插件（含 skills/user/ 下 Agent 保存的技能）。

    返回:
        成功加载的 Skill 列表。
    """
    skills_dir = skills_dir or Config.SKILLS_DIR
    skills: list[Skill] = []

    if not skills_dir.exists():
        logger.warning("技能目录不存在: %s", skills_dir)
        return skills

    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and not child.name.startswith("_"):
            skill = _load_skill(child)
            if skill:
                skills.append(skill)

    # 加载用户/Agent 保存的技能（skills/user/*）
    user_dir = Config.USER_SKILLS_DIR
    if user_dir.exists() and user_dir.is_dir():
        for child in sorted(user_dir.iterdir()):
            if child.is_dir() and not child.name.startswith("_"):
                skill = _load_skill(child)
                if skill:
                    skills.append(skill)
                    logger.info("已加载用户技能: %s", skill.name)

    logger.info("共加载 %d 个技能", len(skills))
    return skills


def build_tool_registry(skills: list[Skill]) -> dict[str, ToolSpec]:
    """
    将所有技能的工具展平为 {工具名: ToolSpec} 映射表，
    方便 kernel 通过名称快速查找并执行。
    """
    registry: dict[str, ToolSpec] = {}
    for skill in skills:
        for tool in skill.tools:
            if tool.name in registry:
                logger.warning("工具名冲突: '%s'，后者将覆盖前者", tool.name)
            registry[tool.name] = tool
    return registry


def build_skill_manuals(skills: list[Skill]) -> str:
    """
    将所有技能的 Markdown 操作手册拼合为一段文本，
    用于注入到系统提示词中供 Agent 阅读。

    返回:
        拼合后的操作手册文本。如果没有技能则返回空字符串。
    """
    if not skills:
        return ""

    sections: list[str] = []
    for skill in skills:
        if skill.manual:
            sections.append(skill.manual)

    if not sections:
        return ""

    return "\n\n---\n\n".join(sections)


def build_tools_schema(skills: list[Skill]) -> str:
    """
    将所有技能的工具名、描述、参数 JSON Schema 格式化为文本，
    写入系统提示词供模型在 JSON 输出中引用。

    返回:
        工具定义文本。每个工具一小段。
    """
    import json

    if not skills:
        return "（暂无可用工具）"

    lines: list[str] = []
    for skill in skills:
        for tool in skill.tools:
            params_str = json.dumps(tool.parameters, ensure_ascii=False, indent=2)
            lines.append(
                f"### `{tool.name}`\n"
                f"- 描述: {tool.description}\n"
                f"- 参数 JSON Schema:\n```json\n{params_str}\n```"
            )

    return "\n\n".join(lines)
