---
name: learn-tools
description: "自我升级：保存新技能到本地并加载，使 Agent 学会新能力后持久化并在本会话中可用"
tools:
  - name: save_skill
    function: save_skill
    needs_confirmation: true
    parameters:
      type: object
      properties:
        name:
          type: string
          description: "技能目录名，英文/数字/连字符，如 my-helper"
        description:
          type: string
          description: "技能简短描述"
        tools_spec:
          type: string
          description: "JSON 数组，每项含 name、function、parameters、可选 needs_confirmation"
        manual_content:
          type: string
          description: "SKILL.md 的 Markdown 正文（不含 YAML）"
        tool_py_content:
          type: string
          description: "tool.py 的完整 Python 源码"
        overwrite:
          type: boolean
          description: "为 true 时允许覆盖已存在的同名技能（升级技能）"
      required:
        - name
        - description
        - tools_spec
        - manual_content
        - tool_py_content
---

# 📚 学习/自我升级技能 (learn-tools)

Agent 可以**学会新技能并保存**：根据用户需求或已有能力，生成新技能的 SKILL.md 与 tool.py，保存到 `skills/user/` 目录；保存后调用系统工具 **load_new_skill** 即可在本会话中立即使用。下次启动时会自动加载已保存的用户技能。

## 创建技能规范（必读，否则易导致工具失效）

1. **技能名唯一**：默认不能与 `skills/user/` 下已有目录同名。**升级已有技能**时设置 `overwrite=True` 可覆盖保存（如升级 git-tools）。
2. **工具名唯一**：同一技能内 `tools_spec` 里每个工具的 `name` 不可重复。
3. **function 与 tool.py 一致**：`tools_spec` 中每个 `function` 必须在 `tool_py_content` 里**有对应定义**（即存在 `def 函数名(`），否则保存时会报错；未定义会导致加载时该工具失效。
4. **先设计再保存**：确定 name、各工具 name/function/parameters、manual_content、tool_py_content 后再调用 save_skill。

## 必须遵守的流程

1. **先设计再保存**：确定技能名称、要提供的工具（名称、参数 JSON Schema）、操作手册正文和 tool.py 源码。
2. **保存**：调用 `save_skill`（会要求用户确认），写入 `skills/user/<name>/`。
3. **加载**：保存成功后**必须**调用 **load_new_skill(name="...")**，新技能才会在本会话中可用；load_new_skill 由系统提供，无需 view_skill 其他技能即可调用。

## 工具一览

### `save_skill` — 保存新技能（需用户确认）

将新技能写入 `skills/user/<name>/`（SKILL.md + tool.py）。执行前会要求用户确认。

**何时使用：** 用户要求「加一个 XX 技能」「学会做 XX 并保存」；或你发现可复用能力且用户同意保存时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 技能目录名，仅英文、数字、连字符、下划线，如 `my-helper` |
| `description` | string | ✅ | 简短描述，会出现在「可用技能」列表 |
| `tools_spec` | string | ✅ | JSON 数组，每项：`{"name":"工具名","function":"函数名","parameters":{...}, "needs_confirmation":false}` |
| `manual_content` | string | ✅ | SKILL.md 的 Markdown 正文（不含 ---YAML---） |
| `tool_py_content` | string | ✅ | tool.py 的完整 Python 源码，须包含 tools_spec 中声明的函数 |
| `overwrite` | boolean | ❌ | 为 true 时覆盖已存在的同名技能（用于升级） |

**parameters 格式**：与其它技能 SKILL.md 一致，如 `{"type":"object","properties":{"x":{"type":"string","description":"..."}},"required":["x"]}`。

**调用示例：**
```
save_skill(
  name="greet",
  description="根据名字打招呼",
  tools_spec='[{"name":"greet","function":"greet","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}]',
  manual_content="# greet\n\n调用 greet(name) 返回问候语。",
  tool_py_content="def greet(name: str) -> str:\n    return f\"Hello, {name}!\""
)
```
保存成功后，**务必**再调用 **load_new_skill(name="greet")**。

---

### `load_new_skill` — 加载刚保存的技能（系统工具）

由系统提供，不在本技能目录中实现。保存新技能后调用此工具，传入 `name`（与 save_skill 的 name 一致），即可在本会话中立即使用新技能，无需重启。

**调用示例：**
```
load_new_skill(name="greet")
```

**注意：** 仅能加载已通过 save_skill 保存到 `skills/user/<name>/` 的技能；内置技能无需也不应通过此工具加载。
