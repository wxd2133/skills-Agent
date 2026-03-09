---
name: persistent-memory
description: 保存、读取和删除信息以实现持久化存储
tools:
- name: save_info
  function: save_info
  parameters:
    type: object
    properties:
      key:
        type: string
        description: 信息的键
      value:
        type: string
        description: 信息的值
    required:
    - key
    - value
- name: read_info
  function: read_info
  parameters:
    type: object
    properties:
      key:
        type: string
        description: 要读取的键
    required:
    - key
- name: delete_info
  function: delete_info
  parameters:
    type: object
    properties:
      key:
        type: string
        description: 要删除的键
    required:
    - key
---

# persistent-memory

本技能提供简单的键值对持久化存储功能，允许保存、读取和删除信息到本地文件。

## 工具一览

### `save_info` — 保存信息

将键值对保存到文件 `persistent_data.json` 中。如果键已存在，则覆盖其值。

**参数说明：**
- `key` (string, 必填): 信息的键，用于后续读取。
- `value` (string, 必填): 信息的值。

**调用示例：**
```
save_info(key="user_name", value="Alice")
```

### `read_info` — 读取信息

从文件 `persistent_data.json` 中读取指定键的值。如果键不存在，返回错误信息。

**参数说明：**
- `key` (string, 必填): 要读取的键。

**调用示例：**
```
read_info(key="user_name")
```

### `delete_info` — 删除信息

从文件 `persistent_data.json` 中删除指定键及其值。如果键不存在，返回错误信息。

**参数说明：**
- `key` (string, 必填): 要删除的键。

**调用示例：**
```
delete_info(key="user_name")
```

## 注意事项
- 数据保存在工作区的 `persistent_data.json` 文件中，使用 JSON 格式。
- 文件使用 UTF-8 编码，确保中文字符正确处理。
- 此技能提供基本的持久化存储，适用于简单信息管理。