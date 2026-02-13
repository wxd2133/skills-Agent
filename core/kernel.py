"""
ReAct 推理引擎（大脑）
实现 感知 → 思考 → 执行 循环，通过 JSON 结构化输出驱动状态机。

LLM 每轮输出一个 JSON 对象，包含 state 字段表示当前状态：
  - "thinking"   : 仅思考，不执行动作
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
    build_tool_registry, build_skill_manuals, build_tools_schema, load_all_skills,
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
JSON 中必须包含 `state` 字段，取值为以下三种之一：

### 状态 1: thinking —— 仅思考，不执行动作
当你还在分析问题、需要更多推理时使用。
```json
{{
  "state": "thinking",
  "thought": "我的分析和思考过程..."
}}
```

### 状态 2: tool_call —— 调用一个工具
当你决定调用某个工具时使用。每次只能调用一个工具。
```json
{{
  "state": "tool_call",
  "thought": "我决定调用这个工具的原因...",
  "tool": "工具名称",
  "args": {{
    "参数名": "参数值"
  }}
}}
```

### 状态 3: answer —— 提交最终答案
当你已经收集到足够的信息，可以回答用户时使用。**只有输出此状态才会结束对话。**
```json
{{
  "state": "answer",
  "thought": "得出结论的推理过程...",
  "answer": "给用户的完整最终回答"
}}
```

## 规则
- 每次只输出一个 JSON 对象
- 每次只能调用一个工具
- 仔细分析工具返回的观察结果再做下一步决定
- 如果工具执行失败，在 thought 中分析原因，尝试其他方法
- **必须通过 state=answer 提交最终答案**，不要在 thinking 中直接写答案
- 用中文回答用户问题

{tools_schema}
{skill_manuals}"""


def _build_system_prompt(skills: list[Skill]) -> str:
    """拼装系统提示词：基础模板 + 工具 Schema + 技能操作手册。"""
    # 工具 JSON Schema 定义
    tools_schema_text = build_tools_schema(skills)
    tools_section = f"## 可用工具\n\n{tools_schema_text}" if skills else ""

    # 技能操作手册（Markdown 正文）
    manuals = build_skill_manuals(skills)
    manuals_section = (
        f"## 技能操作手册\n"
        f"以下是工具的详细使用说明，请严格按照手册中的指引调用。\n\n"
        f"{manuals}"
    ) if manuals else ""

    return SYSTEM_PROMPT_TEMPLATE.format(
        tools_schema=tools_section,
        skill_manuals=manuals_section,
    )


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

        # 对话历史
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
        ]

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
        self.messages.append({"role": "user", "content": user_input})

        max_steps = Config.MAX_REACT_STEPS
        step = 1

        while step <= max_steps:
            try:
                # ──── 1. 感知 + 思考：LLM 读取完整对话历史，输出 JSON 决策 ────
                decision = chat(messages=self.messages)

                state = decision.get("state", "thinking")
                thought = decision.get("thought", "")

                # 将 LLM 的 JSON 输出记入对话历史
                self.messages.append({
                    "role": "assistant",
                    "content": json.dumps(decision, ensure_ascii=False),
                })

                # ──── 2. 根据 state 分派 ────

                if state == "thinking":
                    # 仅思考 → 展示思考内容，进入下一轮
                    self.handler.on_think(step, thought)
                    step += 1
                    continue

                elif state == "tool_call":
                    # 调用工具 → 执行并将观察结果写回历史
                    tool_name = decision.get("tool", "")
                    tool_args = decision.get("args", {})

                    if thought:
                        self.handler.on_think(step, thought)

                    self.handler.on_action(step, tool_name, tool_args)

                    # ──── 3. 执行动作 ────
                    observation = self._execute_tool(tool_name, tool_args)
                    self.handler.on_observation(step, tool_name, observation)

                    # ──── 4. 将观察结果加入历史，供下一轮感知 ────
                    self.messages.append({
                        "role": "user",
                        "content": json.dumps({
                            "observation": observation,
                            "tool": tool_name,
                        }, ensure_ascii=False),
                    })

                    step += 1
                    continue

                elif state == "answer":
                    # 最终答案 → 结束循环
                    answer = decision.get("answer", "")
                    if thought:
                        self.handler.on_think(step, thought)
                    self.handler.on_answer(answer)
                    return answer

                else:
                    # 未知状态 → 当作思考处理
                    self.handler.on_think(step, f"(未知状态 '{state}') {thought}")
                    step += 1
                    continue

            except Exception as exc:
                error_msg = f"推理步骤 {step} 出错: {exc}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self.handler.on_error(error_msg)
                return f"抱歉，处理过程中发生错误：{exc}"

        # 达到最大步数仍未得到答案
        exhaust_msg = f"已达到最大推理步数 ({max_steps})，请尝试简化问题。"
        self.handler.on_error(exhaust_msg)
        return exhaust_msg

    def reset(self) -> None:
        """重置对话历史（保留系统提示词）。"""
        self.messages = [{"role": "system", "content": self._system_prompt}]
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

    # ---------- 内部方法 ----------

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
