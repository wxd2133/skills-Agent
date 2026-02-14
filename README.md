# 🤖 Skill Agent

基于 **ReAct**（Reasoning + Acting）的本地技能 Agent：通过自然语言与 AI 对话，Agent 自动规划并调用技能工具完成任务。支持 **CLI** 与 **GUI** 两种入口，技能以插件形式放在 `skills/` 目录，按需扩展。

## 特性

- **JSON 状态驱动**：LLM 每轮输出结构化 JSON（`state` + 参数），支持 `thinking` / `view_skill` / `tool_call` / `answer` 四种状态，循环清晰可扩展
- **渐进式披露**：系统提示词只注入技能名称与简短描述；使用某技能前通过 `view_skill` 按需加载完整操作手册，减少 token 占用、提升响应质量
- **技能插件化**：每个技能一个目录，包含 `SKILL.md`（YAML 元数据 + Markdown 操作手册）和 `tool.py`，无需改核心代码即可扩展
- **OpenAI 兼容 API**：仅用 `httpx` 发 HTTP 请求、`response_format: json_object` 强制 JSON 输出，可对接 OpenAI、Azure、本地兼容服务等
- **双入口**：`main_cmd.py` 终端交互（Rich 美化），`main_gui.py` 图形界面（tkinter，黑白色系 + 等宽字体便于表格对齐）

## 项目结构

```
.
├── main_cmd.py          # CLI 入口
├── main_gui.py          # GUI 入口
├── requirements.txt    # 依赖
├── .env.example         # 配置示例（复制为 .env 后修改）
├── core/                # 核心引擎
│   ├── config.py        # 配置管理
│   ├── llm.py           # LLM API（JSON 输出）
│   ├── skills.py        # 技能加载器
│   ├── handlers.py      # 事件处理接口
│   └── kernel.py        # ReAct 推理引擎（感知→思考→执行）
├── skills/              # 技能插件
│   ├── math-tools/      # 数学计算（表达式、方程、单位换算）
│   ├── draw-tools/      # 字符绘制（表格、方框、形状、条形图）
│   ├── shell-tools/     # 命令行/文件操作（列出、读/写、搜索、删除；范围限 workspace，删除需确认）
│   └── web-search/      # 网页搜索
│       ├── SKILL.md     # 技能定义 + 操作手册
│       └── tool.py      # 工具实现
└── workspace/           # 沙箱工作区（shell-tools 仅在此目录内操作）
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

可选配置（见 `.env.example`）：

| 变量 | 说明 | 默认 |
|------|------|------|
| MAX_REACT_STEPS | 最大推理步数 | 10 |
| TEMPERATURE | 采样温度 | 0.7 |
| MAX_COMPLETION_TOKENS | 单轮最大输出 token 数（防截断） | 4096 |
| OBSERVATION_DISPLAY_MAX_LENGTH | 观察结果在界面展示的最大字符数，0=不截断 | 2000 |
| WORKSPACE_DIR | 工作区目录 | workspace |

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

## 工作流程简述

1. **系统提示**：仅包含「可用技能」的简短列表（名称 + 一两句描述）。
2. **每轮循环**：LLM 根据当前历史输出一个 JSON（`state` + `thought` / `skill` / `tool`+`args` / `answer`）。
3. **view_skill**：当 Agent 决定使用某技能时，先通过 `state: "view_skill"` 加载该技能的完整 SKILL.md 说明，再根据说明调用工具。
4. **tool_call**：执行技能中的工具，将观察结果写入历史，进入下一轮。
5. **answer**：Agent 输出 `state: "answer"` 并提交最终回答，结束本轮。

## 如何添加新技能

在 `skills/` 下新建一个目录（如 `my-skill/`），包含两个文件即可。

### 1. `SKILL.md`

- **YAML Frontmatter**（`---` 包裹）：给程序读的元数据  
  - `name`、`description`  
  - `tools`：工具列表，每项含 `name`、`function`（对应 `tool.py` 中的函数名）、`parameters`（JSON Schema）
- **Markdown 正文**：给 Agent 读的操作手册（何时用、参数说明、示例、注意事项）。  
  通过 `view_skill` 加载后，Agent 会据此调用工具。

### 2. `tool.py`

实现 Frontmatter 里声明的函数，签名与 `parameters` 对应，返回字符串即可：

```python
def my_tool(query: str) -> str:
    return "结果文本"
```

保存后重启 Agent，新技能会被自动加载；系统提示中会出现该技能的摘要，完整说明在 Agent 执行 `view_skill` 时按需加载。

## 依赖说明

| 依赖 | 用途 |
|------|------|
| httpx | 调用 LLM API（OpenAI 兼容，JSON 输出） |
| python-dotenv | 加载 .env |
| pyyaml | 解析 SKILL.md Frontmatter |
| rich | 终端美化（CLI） |
| tabulate | 表格绘制（draw-tools） |
| ddgs | 网页搜索（web-search，无需 API Key） |
| sympy | 数学技能中的方程求解（math-tools） |

