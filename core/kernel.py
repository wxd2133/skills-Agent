"""
ReAct 推理引擎（大脑）
实现 Thought → Action → Observation 循环，驱动 Agent 自主推理与工具调用。
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any

from core.config import Config
from core.handlers import AgentEventHandler
from core.llm import chat, parse_tool_arguments
from core.skills import Skill, ToolSpec, build_tool_registry, build_skill_manuals, load_all_skills

logger = logging.getLogger(__name__)

# ---------- 系统提示词 ----------

SYSTEM_PROMPT_TEMPLATE = """\
你是一个强大的 AI 助手（Skill Agent），能够通过调用各种工具来完成用户的任务。

## 工作方式
你使用 ReAct（Reasoning + Acting）模式工作：
1. **思考 (Thought)**: 分析用户需求，规划下一步行动
2. **行动 (Action)**: 调用合适的工具来获取信息或执行操作
3. **观察 (Observation)**: 查看工具返回的结果
4. 重复以上步骤直到得出最终答案

## 规则
- 每次只调用一个工具
- 仔细分析工具返回的结果再做下一步决定
- 如果工具执行失败，尝试其他方法
- 当你有足够的信息来回答用户问题时，直接给出最终答案，不要再调用工具
- 用中文回答用户问题
{skill_manuals}"""


def _build_system_prompt(skills: list[Skill]) -> str:
    """拼装系统提示词：基础模板 + 技能操作手册。"""
    manuals = build_skill_manuals(skills)
    if manuals:
        skill_section = (
            "\n## 技能操作手册\n"
            "以下是你可用的技能及其详细使用说明，请严格按照手册中的指引调用工具。\n\n"
            f"{manuals}\n"
        )
    else:
        skill_section = ""
    return SYSTEM_PROMPT_TEMPLATE.format(skill_manuals=skill_section)


class ReActKernel:
    """
    ReAct 推理引擎。
    
    管理对话历史，执行 Thought-Action-Observation 循环。
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

        # 构建系统提示词（含技能操作手册）
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

        openai_tools = [tool.to_openai_tool() for tool in self.tool_registry.values()]

        for step in range(1, Config.MAX_REACT_STEPS + 1):
            try:
                # 调用 LLM
                assistant_msg = chat(
                    messages=self.messages,
                    tools=openai_tools if openai_tools else None,
                )

                # 记入对话历史
                self.messages.append(assistant_msg)

                # 判断是否有工具调用
                tool_calls = assistant_msg.get("tool_calls")

                if not tool_calls:
                    # 没有工具调用 → LLM 直接给出了最终回答
                    answer = assistant_msg.get("content", "")
                    if assistant_msg.get("content"):
                        self.handler.on_think(step, assistant_msg["content"])
                    self.handler.on_answer(answer)
                    return answer

                # 有工具调用 → 执行 Action
                # 先输出思考内容（如果有）
                if assistant_msg.get("content"):
                    self.handler.on_think(step, assistant_msg["content"])

                for tc in tool_calls:
                    func_name = tc["function"]["name"]
                    func_args_raw = tc["function"]["arguments"]
                    func_args = parse_tool_arguments(func_args_raw)
                    call_id = tc["id"]

                    self.handler.on_action(step, func_name, func_args)

                    # 执行工具
                    result = self._execute_tool(func_name, func_args)

                    self.handler.on_observation(step, func_name, result)

                    # 将工具结果加入对话历史
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result,
                    })

            except Exception as exc:
                error_msg = f"推理步骤 {step} 出错: {exc}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self.handler.on_error(error_msg)
                return f"抱歉，处理过程中发生错误：{exc}"

        # 超过最大步数
        exhaust_msg = f"已达到最大推理步数 ({Config.MAX_REACT_STEPS})，请尝试简化问题。"
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
