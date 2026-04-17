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
        requirements:
          oneOf:
            - type: string
            - type: array
              items:
                type: string
          description: "可选依赖（字符串或字符串数组）。保存技能后会自动写入 requirements.txt 并尝试安装"
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

## 创建前必做（否则易冲突或失效）

1. **先查看已有技能与工具名**：设计新技能前**必须先调用 list_available_tools**（系统工具），查看当前已加载的技能及每个技能下的工具名，避免新工具名与已有工具名重复。重名会导致后者覆盖前者、部分工具失效。
2. **再设计再保存**：根据 list_available_tools 的结果，为新区块起不与现有工具同名的 name，再编写 tools_spec、manual_content、tool_py_content，最后调用 save_skill。

## 创建技能规范（必读，否则易导致工具失效）

1. **技能名唯一**：默认不能与 `skills/user/` 下已有目录同名。**升级已有技能**时设置 `overwrite=True` 可覆盖保存（如升级 git-tools）。
2. **工具名同一技能内唯一**：同一技能内 `tools_spec` 里每个工具的 `name` 不可重复。
3. **工具名全局唯一**：新技能中的工具名（`name`）**不能与任何已有技能中的工具名相同**，否则 save_skill 会报错。创建前务必 list_available_tools 核对。
4. **function 与 tool.py 一致**：`tools_spec` 中每个 `function` 必须在 `tool_py_content` 里**有对应定义**（即存在 `def 函数名(`），否则保存时会报错；未定义会导致加载时该工具失效。
5. **编码规范**：若 tool.py 里使用 `subprocess.run(..., text=True)` 或读写文件，须**显式指定 `encoding="utf-8"`**（及可选 `errors="replace"`），否则在 Windows 下会按系统默认编码（如 gbk）解码，导致 UnicodeDecodeError 或中文乱码。
6. **依赖声明**：若新技能依赖第三方包，务必在 `requirements` 参数中声明（如 `openpyxl>=3.1.5`）。保存时会自动更新 `requirements.txt` 并执行安装；安装失败会返回错误。
7. **执行过程注意**：tool.py 中的函数会被 Agent 在不确定时机调用，建议：子进程调用加合理 **timeout**；异常尽量捕获并返回可读错误信息，避免未处理异常导致工具报错。

## 必须遵守的流程

1. **list_available_tools**：先调用此系统工具，查看已有技能与工具名。
2. **设计**：确定技能名称、工具名（不与已有重复）、参数 Schema、操作手册正文、tool.py 源码。
3. **保存并安装依赖**：调用 `save_skill`（会要求用户确认），写入 `skills/user/<name>/`，并自动处理 `requirements`。
4. **加载**：保存成功后**必须**调用 **load_new_skill(name="...")**，新技能才会在本会话中可用。

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
| `requirements` | string / string[] | ❌ | 技能依赖列表；保存时自动写入 `requirements.txt` 并执行安装 |
| `overwrite` | boolean | ❌ | 为 true 时覆盖已存在的同名技能（用于升级） |

**parameters 格式**：与其它技能 SKILL.md 一致，如 `{"type":"object","properties":{"x":{"type":"string","description":"..."}},"required":["x"]}`。

**调用示例：**
```
save_skill(
  name="greet",
  description="根据名字打招呼",
  tools_spec='[{"name":"greet","function":"greet","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}]',
  manual_content="# greet\n\n调用 greet(name) 返回问候语。",
  tool_py_content="def greet(name: str) -> str:\n    return f\"Hello, {name}!\"",
  requirements=[]
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

---

### `list_available_tools` — 列出已加载技能与工具名（系统工具）

由系统提供。返回当前已加载的所有技能及其工具名列表。**创建新技能前必须先调用**，确保新技能中的工具名与已有工具名不重复，否则会冲突或覆盖导致失效。

**调用示例：**
```
list_available_tools()
```

**返回示例：** 当前已加载技能及工具名（…）\n  • draw-tools: draw_table, draw_box, …\n  • learn-tools: save_skill\n  …
