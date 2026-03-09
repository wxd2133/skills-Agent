#!/usr/bin/env python3
"""
Skill Agent - GUI 图形界面入口
基于 tkinter 的桌面聊天界面。

用法:
    python main_gui.py
"""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
from typing import Any

from core.config import Config
from core.handlers import AgentEventHandler
from core.kernel import ReActKernel

# 观察结果在 GUI 中的展示长度（0=不截断）
OBSERVATION_DISPLAY_MAX = Config.OBSERVATION_DISPLAY_MAX_LENGTH


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
        max_len = OBSERVATION_DISPLAY_MAX
        display = result if max_len <= 0 or len(result) <= max_len else result[:max_len] + "\n... (已截断)"
        self._append(f"👁️ [步骤 {step}] 结果 ({tool_name}):\n   {display}", "observation")

    def confirm_dangerous(self, step: int, tool_name: str, tool_args: dict[str, Any]) -> bool:
        """危险操作：在主线程弹出确认框，工作线程阻塞等待用户选择。"""
        self.app._confirm_request_queue.put((step, tool_name, tool_args))
        self.app.root.after(0, self._show_confirm_dialog)
        try:
            return self.app._confirm_result_queue.get(timeout=300)
        except queue.Empty:
            return False

    def _show_confirm_dialog(self) -> None:
        """主线程执行：弹出确认框并将结果放入队列。"""
        try:
            step, tool_name, tool_args = self.app._confirm_request_queue.get_nowait()
        except queue.Empty:
            return
        msg = f"是否执行以下危险操作？\n\n工具: {tool_name}\n参数: {tool_args}"
        ok = messagebox.askyesno("危险操作确认", msg, icon=messagebox.WARNING)
        self.app._confirm_result_queue.put(ok)

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
        self.root.title("Skill Agent")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)

        # 黑白色系 · 苹果风（浅色）
        self.bg_color = "#f5f5f7"
        self.fg_color = "#1d1d1f"
        self.fg_secondary = "#6e6e73"
        self.input_bg = "#ffffff"
        self.border_color = "#d2d2d7"
        self.accent_color = "#1d1d1f"
        self.chat_bg = "#ffffff"

        self.root.configure(bg=self.bg_color)

        self._build_ui()
        self._confirm_request_queue: queue.Queue = queue.Queue()
        self._confirm_result_queue: queue.Queue = queue.Queue()
        self._init_engine()

    def _build_ui(self) -> None:
        """构建界面组件。"""
        # --- 顶部工具栏 ---
        toolbar = tk.Frame(self.root, bg=self.bg_color, pady=5)
        toolbar.pack(fill=tk.X, padx=10)

        title_label = tk.Label(toolbar, text="Skill Agent",
                               font=("Segoe UI", 14, "bold"),
                               bg=self.bg_color, fg=self.fg_color)
        title_label.pack(side=tk.LEFT)

        # 按钮：浅灰底、黑字、细边框
        btn_style = {"bg": "#e8e8ed", "fg": self.fg_color, "relief": "flat",
                     "padx": 12, "pady": 4, "font": ("Segoe UI", 9),
                     "activebackground": "#d2d2d7", "activeforeground": self.fg_color}

        btn_reset = tk.Button(toolbar, text="🔄 重置", command=self._on_reset, **btn_style)
        btn_reset.pack(side=tk.RIGHT, padx=3)

        btn_skills = tk.Button(toolbar, text="📦 技能", command=self._on_skills, **btn_style)
        btn_skills.pack(side=tk.RIGHT, padx=3)

        btn_config = tk.Button(toolbar, text="⚙️ 配置", command=self._on_config, **btn_style)
        btn_config.pack(side=tk.RIGHT, padx=3)

        # --- 聊天区域 ---
        chat_frame = tk.Frame(self.root, bg=self.bg_color)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        # 聊天区使用等宽字体，表格与字符画才能对齐
        self._chat_font = ("Consolas", 10)
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=self._chat_font,
            bg=self.chat_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            relief="flat",
            state=tk.DISABLED,
            padx=12, pady=12,
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # 文本标签：黑白色系（统一等宽字体以保持表格对齐）
        self.chat_display.tag_config("user", foreground="#1d1d1f", font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("think", foreground="#424245")
        self.chat_display.tag_config("action", foreground="#6e6e73")
        self.chat_display.tag_config("observation", foreground="#424245")
        self.chat_display.tag_config("answer", foreground="#1d1d1f", font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("error", foreground="#1d1d1f")
        self.chat_display.tag_config("status", foreground=self.fg_secondary)

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
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.fg_color,
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.input_entry.bind("<Return>", self._on_send)

        self.send_btn = tk.Button(
            input_frame,
            text="发送",
            command=self._on_send,
            bg=self.accent_color,
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16, pady=5,
            activebackground="#424245",
            activeforeground="#ffffff",
        )
        self.send_btn.pack(side=tk.RIGHT, padx=(8, 0))

        # --- 状态栏 ---
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(
            self.root, textvariable=self.status_var,
            bg=self.bg_color, fg=self.fg_secondary,
            font=("Segoe UI", 9), anchor="w", padx=12,
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
