"""
学习/自我升级技能 - 工具实现
将新技能保存到 skills/user/ 目录，需用户确认；加载由系统工具 load_new_skill 完成。
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import yaml

from core.config import Config

USER_SKILLS_DIR = Config.USER_SKILLS_DIR
SKILLS_DIR = Config.SKILLS_DIR
REQUIREMENTS_FILE = Config.PROJECT_ROOT / "requirements.txt"


def _collect_existing_tool_names(exclude_skill_name: str | None = None) -> set[str]:
    """
    从磁盘上所有技能的 SKILL.md 中收集工具名（name）。
    exclude_skill_name: 若指定，则排除该技能下的工具名（用于 overwrite 时避免与自己冲突）。
    """
    names: set[str] = set()
    for base_dir in (SKILLS_DIR, USER_SKILLS_DIR):
        if not base_dir.exists() or not base_dir.is_dir():
            continue
        for child in base_dir.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if base_dir == SKILLS_DIR and child.name == "user":
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                raw = skill_md.read_text(encoding="utf-8", errors="replace")
                match = re.match(r"\A---\s*\n(.*?)\n---", raw, re.DOTALL)
                if not match:
                    continue
                meta = yaml.safe_load(match.group(1))
                if not isinstance(meta, dict):
                    continue
                skill_name = meta.get("name") or child.name
                if exclude_skill_name and skill_name == exclude_skill_name:
                    continue
                for t in meta.get("tools") or []:
                    if isinstance(t, dict) and t.get("name"):
                        names.add(str(t["name"]).strip())
            except Exception:
                continue
    return names


def _normalize_requirements(requirements: str | list[str] | None) -> tuple[list[str], str | None]:
    """
    解析并校验依赖列表，返回 (规范化后的依赖列表, 错误信息)。
    允许:
      - "openpyxl>=3.1.5, pandas"
      - "openpyxl>=3.1.5\npandas"
      - ["openpyxl>=3.1.5", "pandas"]
    """
    if requirements is None:
        return [], None

    items: list[str]
    if isinstance(requirements, str):
        parts = requirements.replace(",", "\n").splitlines()
        items = [x.strip() for x in parts if x.strip()]
    elif isinstance(requirements, list):
        if not all(isinstance(x, str) for x in requirements):
            return [], "错误：requirements 列表中的每一项都必须是字符串。"
        items = [x.strip() for x in requirements if str(x).strip()]
    else:
        return [], "错误：requirements 仅支持字符串或字符串数组。"

    normalized: list[str] = []
    seen: set[str] = set()
    for dep in items:
        # 包含常见版本符号；禁止空格、分号等可疑字符，避免注入
        if not re.match(r"^[a-zA-Z0-9_.\-]+(?:\[[a-zA-Z0-9_,.\-]+\])?(?:\s*(?:==|>=|<=|>|<|~=|!=)\s*[a-zA-Z0-9*_.\-]+)?$", dep):
            return [], f"错误：非法依赖格式「{dep}」。示例：openpyxl>=3.1.5"
        if dep not in seen:
            seen.add(dep)
            normalized.append(dep)
    return normalized, None


def _append_requirements_and_install(new_requirements: list[str]) -> tuple[bool, str]:
    """
    将依赖追加写入 requirements.txt（去重）并执行 pip install。
    返回 (是否成功, 结果消息)。
    """
    if not new_requirements:
        return True, "未声明新依赖，跳过依赖安装。"

    existing_lines: list[str] = []
    existing_set: set[str] = set()
    if REQUIREMENTS_FILE.exists():
        existing_lines = REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines()
        for line in existing_lines:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            existing_set.add(s)

    to_add = [dep for dep in new_requirements if dep not in existing_set]
    if to_add:
        if existing_lines and existing_lines[-1].strip():
            existing_lines.append("")
        existing_lines.append("# learn-tools 自动追加依赖")
        existing_lines.extend(to_add)
        REQUIREMENTS_FILE.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")

    try:
        cmd = ["python", "-m", "pip", "install"] + new_requirements
        r = subprocess.run(
            cmd,
            cwd=str(Config.PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "依赖安装超时（>300s），请检查网络后重试。"
    except Exception as exc:
        return False, f"依赖安装异常：{exc}"

    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        return False, f"依赖安装失败：{err[:1200]}"

    installed = ", ".join(new_requirements)
    if to_add:
        return True, f"依赖安装成功：{installed}；并已写入 requirements.txt。"
    return True, f"依赖安装成功：{installed}（requirements.txt 已存在相同项）。"


def save_skill(
    name: str,
    description: str,
    tools_spec: str,
    manual_content: str,
    tool_py_content: str,
    requirements: str | list[str] | None = None,
    overwrite: bool = False,
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
        requirements: 依赖列表（字符串或字符串数组），如 "openpyxl>=3.1.5, pandas"
        overwrite: 为 True 时允许覆盖已存在的同名技能（用于升级技能）

    返回:
        成功或错误信息。
    """
    name = (name or "").strip()
    if not name:
        return "错误：技能名称不能为空。"
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        return "错误：技能名称仅允许英文、数字、连字符和下划线。"

    out_dir = USER_SKILLS_DIR / name
    if out_dir.exists() and (out_dir / "SKILL.md").exists() and not overwrite:
        return (
            f"错误：已存在同名技能「{name}」。"
            "请改用新名称保存、先删除旧目录后再保存，或设置 overwrite=True 覆盖升级。"
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
    requirements_list, req_err = _normalize_requirements(requirements)
    if req_err:
        return req_err

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

    # 工具名全局唯一：不能与已有技能中的工具名重复（overwrite 时排除本技能）
    existing = _collect_existing_tool_names(exclude_skill_name=name if (out_dir.exists() and overwrite) else None)
    for entry in tools:
        tn = entry["name"]
        if tn in existing:
            return f"错误：工具名「{tn}」已被其他技能使用，请换名。创建前请先调用 list_available_tools 查看已有工具名。"

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
        ok, install_msg = _append_requirements_and_install(requirements_list)
        if not ok:
            return (
                f"已保存技能到 {out_dir}，但{install_msg}"
                "请先修复依赖问题，再调用 load_new_skill。"
            )
        return (
            f"已保存技能到 {out_dir}。{install_msg} "
            f"请调用 load_new_skill(name=\"{name}\") 使本会话立即可用。"
        )
    except OSError as e:
        return f"错误：写入失败 - {e}"
