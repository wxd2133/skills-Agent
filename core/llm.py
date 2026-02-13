"""
LLM API 调用模块
封装与大语言模型的通信，强制 JSON 结构化输出。

使用 OpenAI 兼容的 HTTP 接口（/v1/chat/completions），
通过 response_format = {"type": "json_object"} 确保输出为合法 JSON。
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
    temperature: float | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    发送聊天请求到 LLM，强制 JSON 格式输出。

    参数:
        messages:    消息列表
        temperature: 采样温度（默认使用全局配置）
        model:       模型名称（默认使用全局配置）

    返回:
        解析后的 JSON 字典（即 LLM 输出的 JSON 对象）。
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
        "response_format": {"type": "json_object"},
    }

    logger.debug("LLM 请求: model=%s, messages=%d", body["model"], len(messages))

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    # 提取 content 并解析为 JSON
    content_str = data["choices"][0]["message"].get("content", "")

    logger.debug("LLM 原始输出: %s", content_str[:200])

    try:
        result = json.loads(content_str)
    except json.JSONDecodeError as exc:
        logger.error("LLM 输出不是合法 JSON: %s", exc)
        # 兜底：包装为思考状态
        result = {"state": "thinking", "thought": content_str}

    return result
