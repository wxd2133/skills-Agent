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
from urllib.parse import urlparse

import httpx

from core.config import Config

logger = logging.getLogger(__name__)


def _chat_completions_url() -> str:
    """Chat Completions API 地址。"""
    base = Config.OPENAI_BASE_URL.rstrip("/")
    return f"{base}/chat/completions"


def _is_ollama_base_url() -> bool:
    """
    判断当前 base_url 是否是 Ollama 风格地址（默认 11434，或 /api 路径）。
    """
    base = (Config.OPENAI_BASE_URL or "").strip()
    if not base:
        return False
    parsed = urlparse(base)
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower().strip("/")
    return parsed.port == 11434 or path.startswith("api")


def _ollama_chat_url() -> str:
    """Ollama /api/chat 地址。"""
    base = Config.OPENAI_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    if base.endswith("/api"):
        return f"{base}/chat"
    return f"{base}/api/chat"


def _parse_json_from_model_output(content: str) -> dict[str, Any] | None:
    """
    从模型输出中尽量提取 JSON 对象。
    支持三种常见情况：
    1) 纯 JSON
    2) ```json ... ``` 代码块包裹
    3) 前后有杂文本，只截取最外层 { ... }
    """
    raw = (content or "").strip()
    if not raw:
        return None

    # 1) 直接解析
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    # 2) 去 markdown 代码块
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            inner = "\n".join(lines[1:-1]).strip()
            if inner.lower().startswith("json"):
                inner = inner[4:].strip()
            try:
                data = json.loads(inner)
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                pass

    # 3) 截取最外层 JSON
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


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
    use_ollama = _is_ollama_base_url()
    model_name = model or Config.OPENAI_MODEL
    temp = temperature if temperature is not None else Config.TEMPERATURE

    logger.debug("LLM 请求: model=%s, messages=%d, ollama=%s", model_name, len(messages), use_ollama)

    with httpx.Client(timeout=120.0) as client:
        if use_ollama:
            url = _ollama_chat_url()
            body: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": temp,
                    "num_predict": Config.MAX_COMPLETION_TOKENS,
                },
            }
            resp = client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            content_str = data.get("message", {}).get("content", "")
        else:
            url = _chat_completions_url()
            headers = {"Content-Type": "application/json"}
            if Config.OPENAI_API_KEY:
                headers["Authorization"] = f"Bearer {Config.OPENAI_API_KEY}"
            body = {
                "model": model_name,
                "messages": messages,
                "temperature": temp,
                "max_tokens": Config.MAX_COMPLETION_TOKENS,
                "response_format": {"type": "json_object"},
            }
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            # 提取 content 并解析为 JSON
            content_str = data["choices"][0]["message"].get("content", "")

    logger.debug("LLM 原始输出: %s", content_str[:200])

    result = _parse_json_from_model_output(content_str)
    if result is not None:
        return result

    logger.error("LLM 输出不是合法 JSON，原文片段: %s", content_str[:300])
    # 关键修复：不要伪装成 thinking，交给 kernel 的非法 state 反馈机制要求重输 JSON
    return {
        "state": "invalid_json",
        "thought": "模型输出不是合法 JSON，请按协议仅输出一个 JSON 对象。",
    }
