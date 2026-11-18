"""
ReAct 推理引擎（大脑）
实现 感知 → 思考 → 执行 循环，通过 JSON 结构化输出驱动状态机。

LLM 每轮输出一个 JSON 对象，包含 state 字段表示当前状态：
  - "thinking"   : 仅思考，不执行动作
  - "view_skill" : 查看某技能的完整说明（渐进式披露）
  - "tool_call"  : 调用一个工具
  - "answer"     : 提交最终答案，结束循环
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any

from core.config import Config
from core.handlers import AgentEventHandler
from core.llm import chat
from core.skills import (
    Skill, ToolSpec,
    build_tool_registry, load_all_skills, load_skill_from_dir,
)

logger = logging.getLogger(__name__)

# 连续纯思考在这个次数内不占用推理步数；再继续只思考才计入步数。
_FREE_THINKING_LIMIT = 2
# 模型请求失败或输出不合协议时，先免费重试这么多次，之后才占用步数或结束本轮。
_SOFT_FAILURE_LIMIT = 2

# ---------- 系统提示词 ----------

SYSTEM_PROMPT_TEMPLATE = """\
你是一个强大的 AI 助手（Skill Agent），能够通过调用各种工具来完成用户的任务。

## 工作方式
你使用 ReAct（Reasoning + Acting）模式工作，每轮循环包括：
1. **感知 (Perception)**: 阅读用户输入和之前的观察结果
2. **思考 (Thought)**: 分析当前状态，规划下一步行动
3. **执行 (Action)**: 调用工具获取信息，或提交最终答案

## 输出格式
你 **必须且只能** 输出一个 JSON 对象，不要输出任何其他文字。
JSON 中必须包含 `state` 字段，取值为以下四种之一：

### 状态 1: thinking —— 仅思考，不执行动作
当你还在分析问题、需要更多推理时使用。
```json
{{ "state": "thinking", "thought": "我的分析和思考过程..." }}
```

### 状态 2: view_skill —— 查看某技能的完整说明（渐进式披露）
**当你要使用某技能时，必须先通过 view_skill 加载该技能的完整文档**（含工具名称、参数与用法），再使用 tool_call。
```json
{{ "state": "view_skill", "thought": "我需要使用该技能的原因...", "skill": "技能名称" }}
```
技能名称必须是下方「可用技能」列表中的名称（如 math-tools、draw-tools、web-search）。

### 状态 3: tool_call —— 调用一个工具
在通过 view_skill 查看过该技能的完整说明后，再调用具体工具。每次只能调用一个工具。
```json
{{ "state": "tool_call", "thought": "...", "tool": "工具名称", "args": {{ "参数名": "参数值" }} }}
```

### 状态 4: answer —— 提交最终答案
当你已经收集到足够的信息，可以回答用户时使用。**只有输出此状态才会结束对话。**
```json
{{ "state": "answer", "thought": "...", "answer": "给用户的完整最终回答" }}
```

## 规则
- 每次只输出一个 JSON 对象
- **使用某技能前必须先 view_skill 该技能**，再根据文档中的工具说明进行 tool_call
- 每次只能调用一个工具
- 仔细分析观察结果再做下一步决定
- **必须通过 state=answer 提交最终答案**
- 用中文回答用户问题
- **最终答案只针对用户当前（最后一条）提问**：回答应紧扣本轮用户问题，总结你为本轮问题做了什么、得到什么结果；不要将之前多轮对话的内容糅进同一段回答（例如用户先问了 A 再问 B，提交答案时只回答 B，不要重复 A 的结论）

## 可用技能（仅摘要；完整说明请通过 view_skill 加载）
{skill_snippet}"""


def _get_prompt_snippet(skills: list[Skill]) -> str:
    """生成注入到 System Prompt 的技能列表摘要（渐进式披露：仅名称与简短描述）。"""
    if not skills:
        return "（暂无可用技能）"
    lines = [f"- **{s.name}**: {s.description}" for s in skills]
    return "\n".join(lines)


def _build_system_prompt(skills: list[Skill]) -> str:
    """拼装系统提示词：基础模板 + 技能摘要（不含完整手册，由 view_skill 按需加载）。"""
    snippet = _get_prompt_snippet(skills)
    return SYSTEM_PROMPT_TEMPLATE.format(skill_snippet=snippet)


class ReActKernel:
    """
    ReAct 推理引擎。

    管理对话历史，执行 感知→思考→执行 循环。
    LLM 输出 JSON，根据 state 字段驱动状态转移。
    """

    def __init__(self, handler: AgentEventHandler, skills: list[Skill] | None = None):
        """
        初始化引擎。

        参数:
            handler: 事件处理器（用于向 UI 层推送状态）
            skills:  预加载的技能列表（为 None 则自动扫描加载）
        """
        self.handler = handler

        # 加载技能
        if skills is None:
            skills = load_all_skills()
        self.skills = skills
        self.tool_registry: dict[str, ToolSpec] = build_tool_registry(skills)

        # 构建系统提示词（技能摘要；完整手册由 view_skill 按需加载）
        self._system_prompt = _build_system_prompt(skills)

        # 注册系统工具（如 load_new_skill），供 Agent 自我升级后加载新技能
        self._register_system_tools()

        # 对话历史（仅 user/assistant，不含 system；每轮用 system + history 构建消息）
        self.history: list[dict[str, Any]] = []
        self.max_steps = Config.MAX_REACT_STEPS

        handler.on_status(f"引擎就绪：已加载 {len(self.skills)} 个技能，"
                          f"共 {len(self.tool_registry)} 个工具")

    # ---------- 公开接口 ----------

    def run(self, user_input: str) -> str:
        """
        处理一条用户输入，执行 ReAct 循环，返回最终回答。

        参数:
            user_input: 用户的自然语言输入

        返回:
            Agent 的最终回答文本。
        """
        self.history.append({"role": "user", "content": user_input})
        step = 0
        think_streak = 0
        soft_failures = 0

        while step < self.max_steps:
            try:
                self._trim_history()
                decision = chat(messages=self._build_messages())
            except Exception as exc:
                soft_failures += 1
                logger.warning("模型请求失败（第 %d 次）: %s", soft_failures, exc)
                self.handler.on_status(f"模型请求失败，正在重试（{soft_failures}）：{exc}")
                self.history.append({
                    "role": "user",
                    "content": "[SYSTEM OBSERVATION]\n"
                    f"模型请求失败：{exc}\n"
                    "请根据已有信息继续。若无法继续，请直接输出 state=answer。\n"
                    "[/SYSTEM OBSERVATION]",
                })
                if soft_failures > _SOFT_FAILURE_LIMIT:
                    self._report_step_error(step + 1, exc)
                    return f"抱歉，处理过程中发生错误：{exc}"
                continue

            if self._push_invalid_decision_feedback(decision):
                soft_failures += 1
                self.handler.on_status("模型输出不符合 JSON 协议，正在要求重新输出。")
                if soft_failures > _SOFT_FAILURE_LIMIT:
                    step += 1
                continue

            soft_failures = 0
            state = decision.get("state", "")
            if state == "thinking":
                think_streak += 1
            else:
                think_streak = 0

            answer, observation = self._execute_decision(decision, step + 1)
            if answer is not None:
                self.history.append({
                    "role": "assistant",
                    "content": json.dumps(decision, ensure_ascii=False),
                })
                return answer

            if state == "thinking" and think_streak > _FREE_THINKING_LIMIT:
                observation = (
                    "你已连续多次只思考而没有行动。"
                    "请立即输出 view_skill、tool_call 或 answer，不要再输出 thinking。"
                )
                self.handler.on_observation(step + 1, "thinking", observation)
                self._append_step_to_history(decision, observation)
                step += 1
                continue

            self._append_step_to_history(decision, observation)
            if state != "thinking":
                step += 1

        self.handler.on_error(f"已达到最大推理步数 ({self.max_steps})，请尝试简化问题。")
        return f"已达到最大推理步数 ({self.max_steps})，请尝试简化问题。"

    def reset(self) -> None:
        """重置对话历史（保留系统提示词）。"""
        self.history = []
        self.handler.on_status("对话已重置")

    def get_skill_summary(self) -> str:
        """返回当前已加载技能和工具的摘要（简洁版）。"""
        if not self.skills:
            return "已加载技能：无"
        n_tools = len(self.tool_registry)
        lines = [f"已加载 {len(self.skills)} 个技能，共 {n_tools} 个工具："]
        for skill in self.skills:
            lines.append(f"  • {skill.name}（{len(skill.tools)} 个工具）")
        return "\n".join(lines)

    def get_prompt_snippet(self) -> str:
        """生成注入到 System Prompt 的技能列表摘要（供外部查看）。"""
        return _get_prompt_snippet(self.skills)

    def add_skill(self, skill: Skill) -> None:
        """
        动态添加一个技能到当前会话（合并到 skills 与 tool_registry，并刷新系统提示词）。
        用于 save_skill 保存后通过 load_new_skill 立即生效。
        """
        if any(s.name == skill.name for s in self.skills):
            logger.warning("技能 '%s' 已存在，将覆盖", skill.name)
            self.skills = [s for s in self.skills if s.name != skill.name]
        self.skills.append(skill)
        # 按当前技能重建注册表，覆盖时去掉已删除的旧工具，再补回系统工具。
        self.tool_registry = build_tool_registry(self.skills)
        self._register_system_tools()
        self._system_prompt = _build_system_prompt(self.skills)
        logger.info("已动态加载技能: %s (%d 个工具)", skill.name, len(skill.tools))

    def _register_system_tools(self) -> None:
        """注册由 Kernel 提供的系统工具（如 load_new_skill、list_available_tools）。"""
        load_new_skill_spec = ToolSpec(
            name="load_new_skill",
            description="加载刚保存的新技能，使其在本会话中立即可用。保存技能后调用此工具。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能目录名，与 save_skill 时使用的 name 一致"},
                },
                "required": ["name"],
            },
            execute_fn=self._load_new_skill_impl,
        )
        self.tool_registry["load_new_skill"] = load_new_skill_spec

        list_tools_spec = ToolSpec(
            name="list_available_tools",
            description="列出当前已加载的所有技能及其工具名。创建新技能前必须先调用此工具，确保新工具名与已有工具名不重复。",
            parameters={"type": "object", "properties": {}, "required": []},
            execute_fn=self._list_available_tools_impl,
        )
        self.tool_registry["list_available_tools"] = list_tools_spec

    def _load_new_skill_impl(self, name: str) -> str:
        """系统工具 load_new_skill 的实现：从 USER_SKILLS_DIR 加载并加入当前会话。"""
        name = (name or "").strip()
        if not name:
            return "错误：未指定技能名称。"
        skill_dir = Config.USER_SKILLS_DIR / name
        if not skill_dir.exists() or not skill_dir.is_dir():
            return f"错误：未找到技能目录 {skill_dir}，请先使用 save_skill 保存。"
        try:
            skill = load_skill_from_dir(skill_dir)
            if skill is None:
                return f"错误：加载失败，请确认 {skill_dir} 下存在 SKILL.md 与 tool.py。"
            self.add_skill(skill)
            return f"已加载技能「{skill.name}」，共 {len(skill.tools)} 个工具。可在本会话中直接使用。"
        except Exception as e:
            logger.exception("加载新技能失败: %s", name)
            return f"加载失败: {e}"

    def _list_available_tools_impl(self) -> str:
        """系统工具 list_available_tools 的实现：返回当前已加载技能及工具名列表。"""
        lines = ["当前已加载技能及工具名（创建新技能时请勿与下列工具名重复）：\n"]
        for skill in self.skills:
            tool_names = [t.name for t in skill.tools]
            lines.append(f"  • {skill.name}: {', '.join(tool_names)}")

        skill_tool_names = {t.name for s in self.skills for t in s.tools}
        system_tools = [n for n in self.tool_registry if n not in skill_tool_names]
        if system_tools:
            lines.append(f"  • [系统工具]: {', '.join(system_tools)}")

        lines.append(f"\n共 {len(self.skills)} 个技能，{len(self.tool_registry)} 个工具（含系统工具）。")
        return "\n".join(lines)

    # ---------- 内部方法 ----------

    def _build_messages(self) -> list[dict[str, Any]]:
        """系统提示 + 完整历史，供本轮 LLM 调用。"""
        return [{"role": "system", "content": self._system_prompt}] + self.history

    def _trim_history(self) -> None:
        """压缩较早的观察结果，避免技能手册和工具输出把上下文撑满。"""
        max_chars = Config.HISTORY_MAX_CHARS
        if max_chars <= 0 or not self.history:
            return

        def total() -> int:
            return sum(len(str(msg.get("content", ""))) for msg in self.history)

        latest_manual: dict[str, int] = {}
        for index, msg in enumerate(self.history):
            content = str(msg.get("content", ""))
            if not content.startswith("[SYSTEM OBSERVATION]\n# "):
                continue
            headline = content.split("\n", 2)[1]
            if headline.startswith("# "):
                latest_manual[headline[2:].strip()] = index

        for index, msg in enumerate(self.history):
            content = str(msg.get("content", ""))
            if not content.startswith("[SYSTEM OBSERVATION]\n# "):
                continue
            headline = content.split("\n", 2)[1]
            if not headline.startswith("# "):
                continue
            name = headline[2:].strip()
            if latest_manual.get(name) != index:
                msg["content"] = (
                    "[SYSTEM OBSERVATION]\n"
                    f"（技能「{name}」的完整说明已在后续步骤重新提供，此处省略）\n"
                    "[/SYSTEM OBSERVATION]"
                )

        if total() <= max_chars:
            return

        protected = 4
        for msg in self.history[:-protected] if len(self.history) > protected else []:
            content = str(msg.get("content", ""))
            if content.startswith("[SYSTEM OBSERVATION]") and len(content) > 800:
                msg["content"] = content[:700] + "\n... (较早的观察已截断)\n[/SYSTEM OBSERVATION]"

        def is_real_user(msg: dict[str, Any]) -> bool:
            return msg.get("role") == "user" and not str(msg.get("content", "")).startswith("[SYSTEM OBSERVATION]")

        while total() > max_chars and len(self.history) > 2:
            real_users = [msg for msg in self.history if is_real_user(msg)]
            if is_real_user(self.history[0]) and len(real_users) == 1:
                break
            self.history.pop(0)

    def _push_invalid_decision_feedback(self, decision: dict[str, Any]) -> bool:
        """若决策结构不合法则追加反馈到 history 并返回 True，否则返回 False。"""
        state = decision.get("state", "")
        if state not in ("thinking", "view_skill", "tool_call", "answer"):
            self.history.append({
                "role": "user",
                "content": "[SYSTEM OBSERVATION]\n"
                "你的上一轮输出不是合法 JSON 或缺少有效的 state 字段（应为 thinking / view_skill / tool_call / answer），请重新输出。\n"
                "[/SYSTEM OBSERVATION]",
            })
            return True

        # 每种 state 做最小字段校验，防止“半合法 JSON”进入执行阶段
        if state == "view_skill":
            skill_name = decision.get("skill")
            if not isinstance(skill_name, str) or not skill_name.strip():
                self.history.append({
                    "role": "user",
                    "content": "[SYSTEM OBSERVATION]\n"
                    "state=view_skill 时必须提供非空 skill 字段（技能名）。请严格按 JSON 协议重试。\n"
                    "[/SYSTEM OBSERVATION]",
                })
                return True

        if state == "tool_call":
            tool_name = decision.get("tool")
            tool_args = decision.get("args", {})
            if not isinstance(tool_name, str) or not tool_name.strip():
                self.history.append({
                    "role": "user",
                    "content": "[SYSTEM OBSERVATION]\n"
                    "state=tool_call 时必须提供非空 tool 字段（工具名）。请严格按 JSON 协议重试。\n"
                    "[/SYSTEM OBSERVATION]",
                })
                return True
            if not isinstance(tool_args, dict):
                self.history.append({
                    "role": "user",
                    "content": "[SYSTEM OBSERVATION]\n"
                    "state=tool_call 时 args 必须是 JSON 对象。请严格按 JSON 协议重试。\n"
                    "[/SYSTEM OBSERVATION]",
                })
                return True

        if state == "answer":
            answer = decision.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                self.history.append({
                    "role": "user",
                    "content": "[SYSTEM OBSERVATION]\n"
                    "state=answer 时必须提供非空 answer 字段。请严格按 JSON 协议重试。\n"
                    "[/SYSTEM OBSERVATION]",
                })
                return True

        return False

    def _execute_decision(self, decision: dict[str, Any], step: int) -> tuple[str | None, str]:
        """
        按 state 分发执行，通知 handler，返回 (最终答案或 None, 本步观察结果)。
        若 state==answer 则返回 (answer_text, "")，否则返回 (None, observation)。
        """
        state = decision.get("state", "")
        thought = decision.get("thought", "")

        if state == "answer":
            if thought:
                self.handler.on_think(step, thought)
            answer = decision.get("answer", "")
            self.handler.on_answer(answer)
            return (answer, "")

        if state == "thinking":
            self.handler.on_think(step, thought)
            return (None, "(无)")

        if state == "view_skill":
            skill_name = (decision.get("skill") or "").strip()
            if thought:
                self.handler.on_think(step, thought)
            self.handler.on_action(step, "view_skill", {"skill": skill_name})
            full_manual = self._get_skill_manual(skill_name)
            self.handler.on_observation(step, "view_skill", f"已加载「{skill_name}」完整说明")
            return (None, full_manual)

        if state == "tool_call":
            tool_name = decision.get("tool", "")
            tool_args = decision.get("args", {})
            if thought:
                self.handler.on_think(step, thought)
            self.handler.on_action(step, tool_name, tool_args)
            tool = self.tool_registry.get(tool_name)
            if tool and getattr(tool, "needs_confirmation", False):
                if not self.handler.confirm_dangerous(step, tool_name, tool_args):
                    result = "用户未确认，已取消。"
                    self.handler.on_observation(step, tool_name, result)
                    return (None, result)
            result = self._execute_tool(tool_name, tool_args)
            self.handler.on_observation(step, tool_name, result)
            return (None, result)

        return (None, "(无)")

    def _append_step_to_history(self, decision: dict[str, Any], observation: str) -> None:
        """将本步 assistant 输出与观察结果统一追加到 history。"""
        self.history.append({
            "role": "assistant",
            "content": json.dumps(decision, ensure_ascii=False),
        })
        self.history.append({
            "role": "user",
            "content": f"[SYSTEM OBSERVATION]\n{observation}\n[/SYSTEM OBSERVATION]",
        })

    def _report_step_error(self, step: int, exc: Exception) -> None:
        """记录异常并通知 handler。"""
        error_msg = f"推理步骤 {step} 出错: {exc}\n{traceback.format_exc()}"
        logger.error(error_msg)
        self.handler.on_error(error_msg)

    def _get_skill_manual(self, skill_name: str) -> str:
        """按技能名称返回该技能的完整操作手册（SKILL.md 正文）。"""
        if not skill_name:
            return "错误：view_skill 未指定技能名称。"
        for skill in self.skills:
            if skill.name == skill_name:
                if skill.manual:
                    return f"# {skill.name}\n\n{skill.manual}"
                return f"技能「{skill.name}」暂无完整说明文档。"
        available = "、".join(s.name for s in self.skills)
        return f"错误：未找到技能「{skill_name}」。可用技能：{available}"

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """
        根据工具名查找并执行对应的工具函数。

        参数:
            name: 工具名
            args: 工具参数

        返回:
            工具执行结果的字符串表示。
        """
        tool = self.tool_registry.get(name)
        if tool is None:
            return f"错误：未找到工具 '{name}'"

        try:
            result = tool.execute_fn(**args)
            return str(result)
        except TypeError as exc:
            return f"工具参数错误: {exc}"
        except Exception as exc:
            logger.exception("工具 '%s' 执行异常", name)
            return f"工具执行出错: {exc}"
