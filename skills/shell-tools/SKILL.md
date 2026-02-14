---
name: shell-tools
description: "在工作区内安全地执行文件与目录操作：列出、读/写文件、创建目录、搜索、删除（删除需用户确认）"
tools:
  - name: list_dir
    function: list_dir
    parameters:
      type: object
      properties:
        path:
          type: string
          description: "相对工作区的路径，默认 . 表示工作区根"
      required: []

  - name: read_file
    function: read_file
    parameters:
      type: object
      properties:
        path:
          type: string
          description: "相对工作区的文件路径"
        encoding:
          type: string
          description: "编码，默认 utf-8"
        max_lines:
          type: integer
          description: "最多返回行数，默认 2000"
      required:
        - path

  - name: write_file
    function: write_file
    parameters:
      type: object
      properties:
        path:
          type: string
          description: "相对工作区的文件路径"
        content:
          type: string
          description: "要写入的文本内容"
        encoding:
          type: string
          description: "编码，默认 utf-8"
      required:
        - path
        - content

  - name: create_dir
    function: create_dir
    parameters:
      type: object
      properties:
        path:
          type: string
          description: "相对工作区的目录路径"
      required:
        - path

  - name: search_files
    function: search_files
    parameters:
      type: object
      properties:
        query:
          type: string
          description: "搜索关键词（匹配文件名或文件内容）"
        path:
          type: string
          description: "相对工作区的起始目录，默认 ."
        file_pattern:
          type: string
          description: "文件名通配符，默认 *"
        case_sensitive:
          type: boolean
          description: "是否区分大小写，默认 false"
        max_results:
          type: integer
          description: "最多返回条数，默认 100"
      required:
        - query

  - name: delete_path
    function: delete_path
    needs_confirmation: true
    parameters:
      type: object
      properties:
        path:
          type: string
          description: "相对工作区的文件或空目录路径"
      required:
        - path
---

# 📁 命令行/文件操作技能 (shell-tools)

在工作区（workspace）内安全地执行文件与目录操作，所有路径均限制在工作区根目录之下；删除操作需用户确认后才执行。

## 必须遵守的流程

- **操作文件前先查看目录**：在执行 `read_file`、`write_file`、`delete_path` 等涉及具体文件路径的操作之前，**必须先调用 `list_dir`** 查看该目录下的内容，确认目标文件或路径的真实名称与所在位置后再操作，避免路径写错或误删。
- 例如：用户说「删除旧文件」时，先 `list_dir(path=".")` 或对应子目录，根据列出的文件名确认要删除的是哪一个，再调用 `delete_path(path="确认后的路径")`。

## 安全规则

- **路径范围**：仅允许操作工作区内的路径。相对路径视为相对于工作区根；绝对路径若指向工作区外则会被拒绝。
- **危险操作**：`delete_path` 执行前会要求用户确认（如 CLI 会提示「确认删除? (y/n)」），用户未确认则不会执行。

## 工具一览

### `list_dir` — 列出目录内容

列出指定目录下的文件和子目录。

**何时使用：** 用户要查看某目录下有什么文件、浏览工作区结构时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | ❌ | 相对工作区的路径，默认 `.` 表示工作区根 |

**调用示例：**
```
list_dir()
list_dir(path="docs")
```

---

### `read_file` — 读取文件

读取工作区内的文本文件内容。

**何时使用：** 用户要查看、分析某文件内容时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | ✅ | 相对工作区的文件路径 |
| `encoding` | string | ❌ | 编码，默认 utf-8 |
| `max_lines` | integer | ❌ | 最多返回行数，默认 2000，防止过大文件 |

**调用示例：**
```
read_file(path="README.md")
read_file(path="src/main.py", max_lines=500)
```

---

### `write_file` — 写入文件

在工作区内创建或覆盖写入文本文件；若父目录不存在会自动创建。

**何时使用：** 用户要创建新文件、保存内容、覆盖已有文件时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | ✅ | 相对工作区的文件路径 |
| `content` | string | ✅ | 要写入的文本内容 |
| `encoding` | string | ❌ | 编码，默认 utf-8 |

**调用示例：**
```
write_file(path="notes.txt", content="Hello, World!")
write_file(path="subdir/config.json", content="{}")
```

---

### `create_dir` — 创建目录

在工作区内创建目录（含多级父目录）。

**何时使用：** 用户要新建文件夹、确保某路径存在时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | ✅ | 相对工作区的目录路径 |

**调用示例：**
```
create_dir(path="output")
create_dir(path="data/2024/01")
```

---

### `search_files` — 搜索文件

在工作区内按关键词搜索：可匹配文件名，也可匹配文件内容（文本文件）。

**何时使用：** 用户要查找包含某关键词的文件、或按名称找文件时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 搜索关键词 |
| `path` | string | ❌ | 起始目录，默认 `.` |
| `file_pattern` | string | ❌ | 文件名通配符，默认 `*` |
| `case_sensitive` | boolean | ❌ | 是否区分大小写，默认 false |
| `max_results` | integer | ❌ | 最多返回条数，默认 100 |

**调用示例：**
```
search_files(query="TODO")
search_files(query="config", path="src", file_pattern="*.py")
search_files(query="password", case_sensitive=True)
```

---

### `delete_path` — 删除文件或空目录（需用户确认）

删除工作区内的文件或空目录。**执行前会要求用户确认，用户未确认则不会执行。**

**何时使用：** 用户明确要求删除某文件或空目录时。非空目录需用户先自行清空或分步删除。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | ✅ | 相对工作区的文件或空目录路径 |

**调用示例：**
```
delete_path(path="temp.txt")
delete_path(path="empty_folder")
```

**注意：** 不能删除工作区根目录；不能直接删除非空目录，需先删除其内容。
