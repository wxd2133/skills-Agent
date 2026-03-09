import json
import os
from pathlib import Path

def save_info(key: str, value: str) -> str:
    """
    保存键值对到 persistent_data.json 文件。
    """
    file_path = Path("persistent_data.json")
    data = {}
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return f"读取现有文件时出错: {e}"
    data[key] = value
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"信息已保存: key='{key}', value='{value}'"
    except IOError as e:
        return f"保存文件时出错: {e}"

def read_info(key: str) -> str:
    """
    从 persistent_data.json 文件读取指定键的值。
    """
    file_path = Path("persistent_data.json")
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
    从 persistent_data.json 文件删除指定键。
    """
    file_path = Path("persistent_data.json")
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