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
    build_tool_registry, load_all_skills,
)

logger = logging.getLogger(__name__)

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

        # 构建系统提示词（含工具 Schema + 技能操作手册）
        self._system_prompt = _build_system_prompt(skills)

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
        while step < self.max_steps:
            try:
                # 1. 构建消息：系统提示 + 完整历史
                messages = [
                    {"role": "system", "content": self._system_prompt},
                ] + self.history

                # 2. 调用 LLM
                decision = chat(messages=messages)

                # 3. 解析并校验 JSON 响应
                state = decision.get("state", "")
                if state not in ("thinking", "view_skill", "tool_call", "answer"):
                    self.history.append({
                        "role": "user",
                        "content": "[SYSTEM OBSERVATION]\n"
                        "你的上一轮输出不是合法 JSON 或缺少有效的 state 字段（应为 thinking / view_skill / tool_call / answer），请重新输出。\n"
                        "[/SYSTEM OBSERVATION]",
                    })
                    step += 1
                    continue

                thought = decision.get("thought", "")

                # 4. 分发执行
                result = ""

                if state == "answer":
                    if thought:
                        self.handler.on_think(step + 1, thought)
                    answer = decision.get("answer", "")
                    self.handler.on_answer(answer)
                    return answer

                elif state == "thinking":
                    self.handler.on_think(step + 1, thought)
                    result = "(无)"

                elif state == "view_skill":
                    skill_name = (decision.get("skill") or "").strip()
                    if thought:
                        self.handler.on_think(step + 1, thought)
                    self.handler.on_action(step + 1, "view_skill", {"skill": skill_name})
                    result = self._get_skill_manual(skill_name)
                    # 完整说明写入 history 供 Agent 使用，界面只提示已加载、不输出长文档
                    self.handler.on_observation(step + 1, "view_skill", f"已加载「{skill_name}」完整说明")

                elif state == "tool_call":
                    tool_name = decision.get("tool", "")
                    tool_args = decision.get("args", {})
                    if thought:
                        self.handler.on_think(step + 1, thought)
                    self.handler.on_action(step + 1, tool_name, tool_args)
                    result = self._execute_tool(tool_name, tool_args)
                    self.handler.on_observation(step + 1, tool_name, result)

                # 5. 将本步结果统一加入历史
                self.history.append({
                    "role": "assistant",
                    "content": json.dumps(decision, ensure_ascii=False),
                })
                self.history.append({
                    "role": "user",
                    "content": f"[SYSTEM OBSERVATION]\n{result}\n[/SYSTEM OBSERVATION]",
                })

                step += 1

            except Exception as exc:
                error_msg = f"推理步骤 {step + 1} 出错: {exc}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self.handler.on_error(error_msg)
                return f"抱歉，处理过程中发生错误：{exc}"

        exhaust_msg = f"已达到最大推理步数 ({self.max_steps})，请尝试简化问题。"
        self.handler.on_error(exhaust_msg)
        return exhaust_msg

    def reset(self) -> None:
        """重置对话历史（保留系统提示词）。"""
        self.history = []
        self.handler.on_status("对话已重置")

    def get_skill_summary(self) -> str:
        """返回当前已加载技能和工具的摘要。"""
        lines = ["已加载技能:"]
        for skill in self.skills:
            lines.append(f"  📦 {skill.name} - {skill.description}")
            for tool in skill.tools:
                lines.append(f"     🔧 {tool.name}: {tool.description}")
        if not self.skills:
            lines.append("  （暂无技能）")
        return "\n".join(lines)

    def get_prompt_snippet(self) -> str:
        """生成注入到 System Prompt 的技能列表摘要（供外部查看）。"""
        return _get_prompt_snippet(self.skills)

    # ---------- 内部方法 ----------

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
