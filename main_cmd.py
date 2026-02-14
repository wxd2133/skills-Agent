#!/usr/bin/env python3
"""
Skill Agent - CLI 命令行入口
交互式对话界面，在终端中与 Agent 对话。

用法:
    python main_cmd.py
"""

from __future__ import annotations

import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.config import Config
from core.handlers import PrintHandler
from core.kernel import ReActKernel

console = Console()


class CmdHandler(PrintHandler):
    """CLI 用处理器：危险操作确认使用 Rich 输出与输入，确保在 CMD 下可见。"""

    def confirm_dangerous(self, step: int, tool_name: str, tool_args: dict) -> bool:
        from rich.prompt import Confirm
        path = tool_args.get("path", "")
        msg = f"即将执行: [bold red]{tool_name}[/bold red] 参数: {tool_args}"
        if path:
            msg = f"即将删除: [bold yellow]{path}[/bold yellow]（工作区内）"
        console.print()
        try:
            return Confirm.ask("是否确认?", default=False, console=console)
        except (EOFError, KeyboardInterrupt):
            return False


def print_banner() -> None:
    """打印启动横幅。"""
    banner = Text()
    banner.append("🤖 Skill Agent", style="bold cyan")
    banner.append(" - ReAct 推理引擎\n", style="dim")
    banner.append("输入你的问题，Agent 会思考并调用工具来回答。\n", style="dim")
    banner.append("特殊命令: ", style="dim")
    banner.append("/help", style="bold yellow")
    banner.append(" | ", style="dim")
    banner.append("/skills", style="bold yellow")
    banner.append(" | ", style="dim")
    banner.append("/config", style="bold yellow")
    banner.append(" | ", style="dim")
    banner.append("/reset", style="bold yellow")
    banner.append(" | ", style="dim")
    banner.append("/quit", style="bold yellow")

    console.print(Panel(banner, border_style="cyan"))


def print_help() -> None:
    """打印帮助信息。"""
    console.print("\n[bold]可用命令:[/bold]")
    console.print("  [yellow]/help[/yellow]    - 显示帮助信息")
    console.print("  [yellow]/skills[/yellow]  - 查看已加载的技能和工具")
    console.print("  [yellow]/config[/yellow]  - 查看当前配置")
    console.print("  [yellow]/reset[/yellow]   - 重置对话历史")
    console.print("  [yellow]/quit[/yellow]    - 退出程序")
    console.print()


def main() -> None:
    """CLI 主函数。"""
    # 配置日志
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 检查配置
    errors = Config.validate()
    if errors:
        console.print("[bold red]配置错误:[/bold red]")
        for err in errors:
            console.print(f"  ❌ {err}")
        console.print("\n请检查 .env 文件后重试。")
        sys.exit(1)

    # 初始化
    print_banner()
    handler = CmdHandler()
    kernel = ReActKernel(handler=handler)

    console.print(f"\n{kernel.get_skill_summary()}\n")

    # 主循环
    while True:
        try:
            user_input = console.input("[bold green]你> [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n再见！👋")
            break

        if not user_input:
            continue

        # 处理特殊命令
        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]
            if cmd in ("/quit", "/exit", "/q"):
                console.print("再见！👋")
                break
            elif cmd == "/help":
                print_help()
                continue
            elif cmd == "/skills":
                console.print(f"\n{kernel.get_skill_summary()}\n")
                continue
            elif cmd == "/config":
                console.print(f"\n[dim]{Config.summary()}[/dim]\n")
                continue
            elif cmd == "/reset":
                kernel.reset()
                console.print("[dim]对话已重置。[/dim]\n")
                continue
            else:
                console.print(f"[red]未知命令: {cmd}[/red]（输入 /help 查看帮助）\n")
                continue

        # 执行推理
        console.rule("[dim]Agent 思考中...[/dim]")
        kernel.run(user_input)
        console.print()


if __name__ == "__main__":
    main()
