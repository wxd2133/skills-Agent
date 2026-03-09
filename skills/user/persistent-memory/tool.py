"""
持久化记忆技能 - 数据存放在工作区 workspace/persistent_data.json，不污染项目根目录。
"""

from __future__ import annotations

import json
from pathlib import Path

from core.config import Config

_DATA_FILE = Config.WORKSPACE_DIR / "persistent_data.json"


def save_info(key: str, value: str) -> str:
    """
    保存键值对到工作区 persistent_data.json 文件。
    """
    file_path = _DATA_FILE
    data = {}
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return f"读取现有文件时出错: {e}"
    data[key] = value
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"信息已保存: key='{key}', value='{value}'"
    except IOError as e:
        return f"保存文件时出错: {e}"

def read_info(key: str) -> str:
    """
    从工作区 persistent_data.json 文件读取指定键的值。
    """
    file_path = _DATA_FILE
    if not file_path.exists():
        return f"文件不存在，键 '{key}' 未找到。"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return f"读取文件时出错: {e}"
    if key in data:
        return f"键 '{key}' 的值为: {data[key]}"
    else:
        return f"键 '{key}' 未找到。"

def delete_info(key: str) -> str:
    """
    从工作区 persistent_data.json 文件删除指定键。
    """
    file_path = _DATA_FILE
    if not file_path.exists():
        return f"文件不存在，键 '{key}' 未找到。"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return f"读取文件时出错: {e}"
    if key in data:
        del data[key]
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return f"键 '{key}' 已删除。"
        except IOError as e:
            return f"保存文件时出错: {e}"
    else:
        return f"键 '{key}' 未找到。"