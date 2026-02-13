#!/usr/bin/env python3
"""
Skill Agent - GUI 图形界面入口
基于 tkinter 的桌面聊天界面。

用法:
    python main_gui.py
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
from typing import Any

from core.config import Config
from core.handlers import AgentEventHandler
from core.kernel import ReActKernel


# ---------- GUI 事件处理器 ----------

class GuiHandler(AgentEventHandler):
    """将 Agent 事件转发到 GUI 文本框。"""

    def __init__(self, chat_display: scrolledtext.ScrolledText, app: "SkillAgentApp"):
        self.chat_display = chat_display
        self.app = app

    def _append(self, text: str, tag: str = "") -> None:
        """线程安全地追加文本到聊天区域。"""
        def _do():
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.insert(tk.END, text + "\n", tag)
            self.chat_display.see(tk.END)
            self.chat_display.config(state=tk.DISABLED)
        self.app.root.after(0, _do)

    def on_think(self, step: int, thought: str) -> None:
        self._append(f"💭 [步骤 {step}] 思考:\n{thought}", "think")

    def on_action(self, step: int, tool_name: str, tool_args: dict[str, Any]) -> None:
        self._append(f"🔧 [步骤 {step}] 调用工具: {tool_name}\n   参数: {tool_args}", "action")

    def on_observation(self, step: int, tool_name: str, result: str) -> None:
        display = result if len(result) <= 300 else result[:300] + "\n... (已截断)"
        self._append(f"👁️ [步骤 {step}] 结果 ({tool_name}):\n   {display}", "observation")

    def on_answer(self, answer: str) -> None:
        self._append(f"\n✅ Agent:\n{answer}\n", "answer")
        self.app.root.after(0, self.app._set_idle)

    def on_error(self, error: str) -> None:
        self._append(f"❌ 错误: {error}", "error")
        self.app.root.after(0, self.app._set_idle)

    def on_status(self, message: str) -> None:
        self._append(f"ℹ️ {message}", "status")


# ---------- 主窗口 ----------

class SkillAgentApp:
    """Skill Agent GUI 主窗口。"""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("🤖 Skill Agent - ReAct 推理引擎")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)

        # 配色
        self.bg_color = "#1e1e2e"
        self.fg_color = "#cdd6f4"
        self.input_bg = "#313244"
        self.accent_color = "#89b4fa"

        self.root.configure(bg=self.bg_color)

        self._build_ui()
        self._init_engine()

    def _build_ui(self) -> None:
        """构建界面组件。"""
        # --- 顶部工具栏 ---
        toolbar = tk.Frame(self.root, bg=self.bg_color, pady=5)
        toolbar.pack(fill=tk.X, padx=10)

        title_label = tk.Label(toolbar, text="🤖 Skill Agent",
                               font=("Segoe UI", 14, "bold"),
                               bg=self.bg_color, fg=self.accent_color)
        title_label.pack(side=tk.LEFT)

        # 按钮
        btn_style = {"bg": "#45475a", "fg": self.fg_color, "relief": "flat",
                     "padx": 10, "pady": 3, "font": ("Segoe UI", 9)}

        btn_reset = tk.Button(toolbar, text="🔄 重置", command=self._on_reset, **btn_style)
        btn_reset.pack(side=tk.RIGHT, padx=3)

        btn_skills = tk.Button(toolbar, text="📦 技能", command=self._on_skills, **btn_style)
        btn_skills.pack(side=tk.RIGHT, padx=3)

        btn_config = tk.Button(toolbar, text="⚙️ 配置", command=self._on_config, **btn_style)
        btn_config.pack(side=tk.RIGHT, padx=3)

        # --- 聊天区域 ---
        chat_frame = tk.Frame(self.root, bg=self.bg_color)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#181825",
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief="flat",
            state=tk.DISABLED,
            padx=10, pady=10,
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # 文本标签样式
        self.chat_display.tag_config("user", foreground="#a6e3a1", font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("think", foreground="#94e2d5")
        self.chat_display.tag_config("action", foreground="#f9e2af")
        self.chat_display.tag_config("observation", foreground="#89b4fa")
        self.chat_display.tag_config("answer", foreground="#a6e3a1")
        self.chat_display.tag_config("error", foreground="#f38ba8")
        self.chat_display.tag_config("status", foreground="#6c7086")

        # --- 输入区域 ---
        input_frame = tk.Frame(self.root, bg=self.bg_color)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.input_entry = tk.Entry(
            input_frame,
            font=("Segoe UI", 11),
            bg=self.input_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief="flat",
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.input_entry.bind("<Return>", self._on_send)

        self.send_btn = tk.Button(
            input_frame,
            text="发送 ▶",
            command=self._on_send,
            bg=self.accent_color,
            fg="#1e1e2e",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=15, pady=5,
        )
        self.send_btn.pack(side=tk.RIGHT, padx=(8, 0))

        # --- 状态栏 ---
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(
            self.root, textvariable=self.status_var,
            bg="#11111b", fg="#6c7086",
            font=("Segoe UI", 9), anchor="w", padx=10,
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # 输入框自动聚焦
        self.input_entry.focus_set()

    def _init_engine(self) -> None:
        """初始化推理引擎。"""
        errors = Config.validate()
        if errors:
            for err in errors:
                self._append_chat(f"⚠️ 配置警告: {err}", "error")
            self._append_chat("请编辑 .env 文件设置 API Key 后重启。", "status")

        self.handler = GuiHandler(self.chat_display, self)
        self.kernel = ReActKernel(handler=self.handler)

        self._append_chat("欢迎使用 Skill Agent！输入问题开始对话。\n", "status")

    def _append_chat(self, text: str, tag: str = "") -> None:
        """向聊天区域追加文本。"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, text + "\n", tag)
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    # --- 事件处理 ---

    def _on_send(self, event=None) -> None:
        """发送消息。"""
        user_input = self.input_entry.get().strip()
        if not user_input:
            return

        self.input_entry.delete(0, tk.END)
        self._append_chat(f"🧑 你: {user_input}", "user")

        # 禁用输入
        self.send_btn.config(state=tk.DISABLED)
        self.input_entry.config(state=tk.DISABLED)
        self.status_var.set("Agent 思考中...")

        # 在后台线程执行推理（避免阻塞 UI）
        thread = threading.Thread(target=self._run_agent, args=(user_input,), daemon=True)
        thread.start()

    def _run_agent(self, user_input: str) -> None:
        """后台线程中运行 Agent。"""
        try:
            self.kernel.run(user_input)
        except Exception as exc:
            self.handler.on_error(str(exc))

    def _set_idle(self) -> None:
        """恢复输入区域为可用状态。"""
        self.send_btn.config(state=tk.NORMAL)
        self.input_entry.config(state=tk.NORMAL)
        self.input_entry.focus_set()
        self.status_var.set("就绪")

    def _on_reset(self) -> None:
        """重置对话。"""
        self.kernel.reset()
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self._append_chat("对话已重置。输入问题开始新对话。\n", "status")

    def _on_skills(self) -> None:
        """显示技能信息。"""
        messagebox.showinfo("已加载技能", self.kernel.get_skill_summary())

    def _on_config(self) -> None:
        """显示配置信息。"""
        messagebox.showinfo("当前配置", Config.summary())

    def run(self) -> None:
        """启动 GUI 主循环。"""
        self.root.mainloop()


def main() -> None:
    """GUI 主函数。"""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = SkillAgentApp()
    app.run()


if __name__ == "__main__":
    main()
