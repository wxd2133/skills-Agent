"""
LLM API 调用模块
封装与大语言模型的通信，支持普通对话和带工具调用的对话。

使用 OpenAI 兼容的 HTTP 接口（/v1/chat/completions），
仅依赖 httpx，不依赖 openai 官方 SDK，可对接任意兼容该协议的服务。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from core.config import Config

logger = logging.getLogger(__name__)


def _chat_completions_url() -> str:
    """Chat Completions API 地址。"""
    base = Config.OPENAI_BASE_URL.rstrip("/")
    return f"{base}/chat/completions"


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    发送聊天请求到 LLM，返回助手的回复消息。

    请求格式遵循 OpenAI Chat Completions API，可与 OpenAI、Azure、
    本地部署等任何兼容该协议的服务对接。

    参数:
        messages:    OpenAI 格式的消息列表
        tools:       可选的工具定义列表（function calling）
        temperature: 采样温度（默认使用全局配置）
        model:       模型名称（默认使用全局配置）

    返回:
        助手消息的字典，包含 role、content、tool_calls 等字段。
    """
    url = _chat_completions_url()
    headers = {
        "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model or Config.OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature if temperature is not None else Config.TEMPERATURE,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    logger.debug("LLM 请求: model=%s, messages=%d, tools=%s",
                 body["model"], len(messages), bool(tools))

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    # 解析 OpenAI 兼容的响应结构
    choice = data["choices"][0]
    message = choice["message"]

    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content") or "",
    }

    tool_calls_raw = message.get("tool_calls")
    if tool_calls_raw:
        result["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                },
            }
            for tc in tool_calls_raw
        ]

    logger.debug("LLM 响应: content_len=%d, tool_calls=%d",
                 len(result["content"]),
                 len(result.get("tool_calls", [])))

    return result


def parse_tool_arguments(arguments_json: str) -> dict[str, Any]:
    """安全解析工具调用的 JSON 参数字符串。"""
    try:
        return json.loads(arguments_json)
    except json.JSONDecodeError as exc:
        logger.warning("解析工具参数失败: %s", exc)
        return {}
