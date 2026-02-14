"""
事件处理接口模块
定义 Agent 运行过程中的回调接口，UI 层（CLI / GUI）通过实现这些接口来接收事件。
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import Any

from core.config import Config


class AgentEventHandler(ABC):
    """
    Agent 事件处理器的抽象基类。
    
    Kernel 在推理过程中会调用这些方法来通知 UI 层当前状态，
    CLI 和 GUI 分别提供各自的具体实现。
    """

    @abstractmethod
    def on_think(self, step: int, thought: str) -> None:
        """
        当 Agent 产生一条思考（Thought）时触发。

        参数:
            step:    当前推理步骤编号（从 1 开始）
            thought: 思考内容
        """

    @abstractmethod
    def on_action(self, step: int, tool_name: str, tool_args: dict[str, Any]) -> None:
        """
        当 Agent 决定调用工具（Action）时触发。

        参数:
            step:      当前推理步骤编号
            tool_name: 工具名称
            tool_args: 工具调用参数
        """

    def confirm_dangerous(self, step: int, tool_name: str, tool_args: dict[str, Any]) -> bool:
        """
        危险操作（如删除）执行前询问用户是否确认。
        若返回 False，该工具将不执行并视为「用户取消」。

        参数:
            step:      当前推理步骤编号
            tool_name: 工具名称
            tool_args: 工具调用参数

        返回:
            True 表示用户确认执行，False 表示取消。
        默认实现：直接返回 True（不拦截，适用于无交互场景）。
        """
        return True

    @abstractmethod
    def on_observation(self, step: int, tool_name: str, result: str) -> None:
        """
        当工具返回结果（Observation）时触发。

        参数:
            step:      当前推理步骤编号
            tool_name: 工具名称
            result:    工具执行的返回结果
        """

    @abstractmethod
    def on_answer(self, answer: str) -> None:
        """
        当 Agent 得出最终答案时触发。

        参数:
            answer: 最终回答内容
        """

    @abstractmethod
    def on_error(self, error: str) -> None:
        """
        当推理过程发生错误时触发。

        参数:
            error: 错误信息
        """

    def on_status(self, message: str) -> None:
        """
        通用状态更新（可选覆盖）。

        参数:
            message: 状态描述文本
        """


# ---------- 内置实现 ----------

class PrintHandler(AgentEventHandler):
    """简单的终端打印处理器，适用于 CLI。"""

    def on_think(self, step: int, thought: str) -> None:
        print(f"\n💭 [步骤 {step}] 思考:\n{thought}")

    def on_action(self, step: int, tool_name: str, tool_args: dict[str, Any]) -> None:
        print(f"🔧 [步骤 {step}] 调用工具: {tool_name}")
        print(f"   参数: {tool_args}")

    def confirm_dangerous(self, step: int, tool_name: str, tool_args: dict[str, Any]) -> bool:
        sys.stdout.flush()
        sys.stderr.flush()
        print(f"\n⚠️  [危险操作] {tool_name} 参数: {tool_args}")
        print("    是否确认执行? 输入 y/yes/是 确认，其他或直接回车取消: ", end="")
        sys.stdout.flush()
        try:
            ans = input().strip().lower()
            return ans in ("y", "yes", "是")
        except (EOFError, KeyboardInterrupt):
            print()
            return False

    def on_observation(self, step: int, tool_name: str, result: str) -> None:
        print(f"👁️  [步骤 {step}] 观察结果 ({tool_name}):")
        max_len = Config.OBSERVATION_DISPLAY_MAX_LENGTH
        display = result if max_len <= 0 or len(result) <= max_len else result[:max_len] + "\n... (超长部分已省略)"
        print(f"   {display}")

    def on_answer(self, answer: str) -> None:
        print(f"\n✅ 最终回答:\n{answer}")

    def on_error(self, error: str) -> None:
        print(f"\n❌ 错误: {error}")

    def on_status(self, message: str) -> None:
        print(f"ℹ️  {message}")


class SilentHandler(AgentEventHandler):
    """静默处理器，不输出任何内容（用于测试或批量执行）。"""

    def on_think(self, step: int, thought: str) -> None:
        pass

    def on_action(self, step: int, tool_name: str, tool_args: dict[str, Any]) -> None:
        pass

    def on_observation(self, step: int, tool_name: str, result: str) -> None:
        pass

    def on_answer(self, answer: str) -> None:
        pass

    def on_error(self, error: str) -> None:
        pass
