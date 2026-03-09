---
name: persistent-memory
description: "持久记忆：保存并读取用户偏好（位置、姓名、习惯等），下次对话可直接使用，避免重复询问"
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

# persistent-memory — 持久记忆

跨会话记住用户的个人信息与偏好（位置、姓名、语言、习惯设定等），避免每次重复询问。

## 何时应该使用本技能

- **用户主动告知个人信息时** → 立即 `save_info` 存储（如"我在北京" → `save_info(key="user_location", value="北京")`）
- **任务需要用户上下文但用户未提供时** → 先 `read_info` 查询记忆，再决定是否询问用户（如查天气前先 `read_info(key="user_location")`，有值就直接用）
- **用户要求"记住/忘掉某事"时** → 对应 `save_info` / `delete_info`

## 常用键名约定

| 键 | 含义 | 示例值 |
|---|---|---|
| `user_name` | 用户姓名/昵称 | `Alice` |
| `user_location` | 用户所在城市/地区 | `北京` |
| `user_language` | 偏好语言 | `zh-CN` |
| `user_timezone` | 时区 | `Asia/Shanghai` |

可根据实际需求自定义其他键名。

## 工具一览

### `save_info` — 保存/更新记忆

将键值对保存到持久文件中。键已存在则覆盖。

**参数说明：**
- `key` (string, 必填): 键名，建议用 `user_` 前缀归类用户信息。
- `value` (string, 必填): 值。

**调用示例：**
```
save_info(key="user_location", value="北京")
save_info(key="user_name", value="Alice")
```

### `read_info` — 读取记忆

读取指定键的值。键不存在时返回"未找到"。

**参数说明：**
- `key` (string, 必填): 要读取的键。

**调用示例：**
```
read_info(key="user_location")
```

### `delete_info` — 删除记忆

删除指定键及其值。

**参数说明：**
- `key` (string, 必填): 要删除的键。

**调用示例：**
```
delete_info(key="user_name")
```

## 注意事项
- 数据保存在工作区的 `persistent_data.json` 文件中（JSON 格式、UTF-8 编码）。
- **优先查记忆再提问**：涉及用户位置、姓名等上下文时，先 read_info 查看是否已有存储，避免重复询问用户。