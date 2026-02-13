# 🤖 Skill Agent

基于 **ReAct**（Reasoning + Acting）的本地技能 Agent：通过自然语言与 AI 对话，Agent 自动规划并调用技能工具完成任务。支持 **CLI** 与 **GUI** 两种入口，技能以插件形式放在 `skills/` 目录，按需扩展。

## 特性

- **ReAct 推理引擎**：Thought → Action → Observation 循环，自动决定何时调用工具、何时给出答案
- **技能插件化**：每个技能一个目录，包含 `SKILL.md`（YAML 元数据 + Markdown 操作手册）和 `tool.py`，无需改核心代码即可扩展
- **OpenAI 兼容 API**：仅用 `httpx` 发 HTTP 请求，可对接 OpenAI、Azure、本地兼容服务等
- **双入口**：`main_cmd.py` 终端交互，`main_gui.py` 图形界面（tkinter）

## 项目结构

```
.
├── main_cmd.py          # CLI 入口
├── main_gui.py          # GUI 入口
├── requirements.txt     # 依赖
├── .env.example         # 配置示例（复制为 .env 后修改）
├── core/                # 核心引擎
│   ├── config.py        # 配置管理
│   ├── llm.py           # LLM API（OpenAI 兼容）
│   ├── skills.py        # 技能加载器
│   ├── handlers.py      # 事件处理接口
│   └── kernel.py        # ReAct 推理引擎
├── skills/              # 技能插件
│   └── math-tools/      # 示例：数学计算
│       ├── SKILL.md     # 技能定义 + 操作手册
│       └── tool.py      # 工具实现
└── workspace/           # 沙箱工作区
```

## 快速开始

### 1. 环境与依赖

- Python 3.10+
- 安装依赖：`pip install -r requirements.txt`

### 2. 配置

复制配置示例并填写 API 密钥：

```bash
copy .env.example .env    # Windows
# 或
cp .env.example .env      # Linux / macOS
```

编辑 `.env`，至少设置：

- `OPENAI_API_KEY`：你的 API 密钥（必填）
- `OPENAI_BASE_URL`：默认 `https://api.openai.com/v1`，可改为兼容该协议的其他地址
- `OPENAI_MODEL`：模型名，如 `gpt-4o`

可选：`MAX_REACT_STEPS`、`TEMPERATURE`、`WORKSPACE_DIR` 等见 `.env.example`。

### 3. 运行

**命令行：**

```bash
python main_cmd.py
```

支持命令：`/help`、`/skills`、`/config`、`/reset`、`/quit`。

**图形界面：**

```bash
python main_gui.py
```

## 如何添加新技能

在 `skills/` 下新建一个目录（如 `my-skill/`），包含两个文件即可。

### 1. `SKILL.md`

- **YAML Frontmatter**（`---` 包裹）：给程序读的元数据
  - `name`、`description`
  - `tools`：工具列表，每项含 `name`、`function`（对应 `tool.py` 中的函数名）、`parameters`（JSON Schema）
- **Markdown 正文**：给 Agent 读的操作手册（何时用、参数说明、示例、注意事项）

示例片段：

```yaml
---
name: my-skill
description: "简短描述"
tools:
  - name: my_tool
    function: my_tool
    parameters:
      type: object
      properties:
        query: { type: string, description: "查询内容" }
      required: [query]
---

# 操作手册（Agent 会读）

## my_tool
用于…… 参数说明、示例、注意事项……
```

### 2. `tool.py`

实现 Frontmatter 里声明的函数，签名与 `parameters` 对应，返回字符串即可：

```python
def my_tool(query: str) -> str:
    # 实现逻辑
    return "结果文本"
```

保存后重启 Agent，新技能会被自动加载；操作手册会注入系统提示词，引导 Agent 正确调用工具。

## 依赖说明

| 依赖 | 用途 |
|------|------|
| httpx | 调用 LLM API（OpenAI 兼容协议，无 openai SDK） |
| python-dotenv | 加载 .env |
| pyyaml | 解析 SKILL.md Frontmatter |
| rich | 终端美化（CLI） |
| sympy | 数学技能中的方程求解（仅 math-tools 需要） |

## 许可证

按项目需要自行选择。
