---
name: git-tools
description: 提供完整的git操作功能，包括状态检查、添加、提交、推送、拉取等，支持提交时自动生成更改总结作为消息
tools:
- name: git_status
  function: git_status
  parameters:
    type: object
    properties:
      repo_path:
        type: string
        description: git仓库的路径
    required:
    - repo_path
- name: git_diff
  function: git_diff
  parameters:
    type: object
    properties:
      repo_path:
        type: string
        description: git仓库的路径
      staged:
        type: boolean
        description: true=暂存区diff(默认)，false=工作区diff
    required:
    - repo_path
- name: git_add
  function: git_add
  parameters:
    type: object
    properties:
      repo_path:
        type: string
        description: git仓库的路径
      files:
        type: string
        description: 要添加的文件路径，多个文件用空格分隔，或使用通配符如'.'表示所有更改
    required:
    - repo_path
    - files
- name: git_commit
  function: git_commit
  parameters:
    type: object
    properties:
      repo_path:
        type: string
        description: git仓库的路径
      commit_message:
        type: string
        description: 提交消息，当auto_message为true时可省略
      summarize:
        type: boolean
        description: 是否在提交消息中附加详细更改总结，默认为false
      auto_message:
        type: boolean
        description: 是否自动生成提交消息作为更改的简单总结，默认为false
    required:
    - repo_path
- name: git_push
  function: git_push
  needs_confirmation: true
  parameters:
    type: object
    properties:
      repo_path:
        type: string
        description: git仓库的路径
      remote:
        type: string
        description: 远程仓库名称，默认为'origin'
      branch:
        type: string
        description: 要推送的分支，默认为当前分支
    required:
    - repo_path
- name: git_pull
  function: git_pull
  parameters:
    type: object
    properties:
      repo_path:
        type: string
        description: git仓库的路径
      remote:
        type: string
        description: 远程仓库名称，默认为'origin'
      branch:
        type: string
        description: 要拉取的分支，默认为当前分支
    required:
    - repo_path
---

# git-tools

## 概述
此技能提供完整的 git 操作功能，支持查看 diff、状态检查、添加、提交、推送和拉取等。

## 推荐提交流程（先读 diff 再总结再提交）
1. **git_add** 将修改加入暂存区。
2. **git_diff(repo_path, staged=True)** 获取暂存区完整 diff，阅读修改内容。
3. **根据 diff 内容思考**，总结「改了什么」写成一句提交信息（不要用「2 files changed」这类统计，要写具体改动）。
4. **git_commit(commit_message="你的总结")** 提交。
5. **git_push** 推送。

`auto_message` 仅作兜底（会列出涉及文件），建议以 git_diff + 手写 commit_message 为主。

## 安全与限制
- **路径限制**：所有操作的 `repo_path` 必须在**当前项目根目录内**（SkillAgent 及其子目录），不能操作项目外的路径，否则会返回错误。

## 工具

### `git_status` — 检查 git 仓库状态
显示工作目录和暂存区的状态。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_path` | string | ✅ | git仓库的路径 |

**调用示例：**
```
git_status(repo_path="/path/to/repo")
```

**返回：** 字符串，显示状态信息或错误。

### `git_diff` — 获取 diff 内容（供撰写提交信息）
返回暂存区或工作区的完整 diff 文本，供阅读后撰写有意义的提交信息。**提交前应先调用此工具查看修改内容，再根据内容写 commit_message。**

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_path` | string | ✅ | git 仓库的路径 |
| `staged` | boolean | ❌ | true=暂存区 diff（默认），false=工作区 diff |

**返回：** diff 全文；无差异时返回提示。

### `git_add` — 添加文件到暂存区
将文件更改添加到暂存区。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_path` | string | ✅ | git仓库的路径 |
| `files` | string | ✅ | 要添加的文件路径，多个文件用空格分隔，或使用通配符如'.'表示所有更改 |

**调用示例：**
```
git_add(repo_path="/path/to/repo", files=".")
```

**返回：** 字符串，表示添加结果或错误。

### `git_commit` — 提交更改到本地仓库
提交暂存区的更改到本地仓库。支持自动生成提交消息作为更改的简单总结，并可选择附加详细总结。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_path` | string | ✅ | git仓库的路径 |
| `commit_message` | string | ❌ | 提交消息，当auto_message为true时可省略 |
| `summarize` | boolean | ❌ | 是否在提交消息中附加详细更改总结，默认为false |
| `auto_message` | boolean | ❌ | 是否自动生成提交消息作为更改的简单总结，默认为false |

**调用示例：**
```
git_commit(repo_path="/path/to/repo", auto_message=true)
git_commit(repo_path="/path/to/repo", commit_message="Fix bug", summarize=true)
```

**返回：** 字符串，表示提交结果或错误。当auto_message为true时，提交消息会自动基于更改生成。

### `git_push` — 推送提交到远程仓库（需用户确认）
将本地提交推送到远程仓库。**执行前会要求用户确认**，未确认则不执行。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_path` | string | ✅ | git仓库的路径 |
| `remote` | string | ❌ | 远程仓库名称，默认为'origin' |
| `branch` | string | ❌ | 要推送的分支，默认为当前分支 |

**调用示例：**
```
git_push(repo_path="/path/to/repo", remote="origin", branch="main")
```

**返回：** 字符串，表示推送结果或错误。

### `git_pull` — 从远程仓库拉取更新
从远程仓库拉取最新更改到本地。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_path` | string | ✅ | git仓库的路径 |
| `remote` | string | ❌ | 远程仓库名称，默认为'origin' |
| `branch` | string | ❌ | 要拉取的分支，默认为当前分支 |

**调用示例：**
```
git_pull(repo_path="/path/to/repo", remote="origin", branch="main")
```

**返回：** 字符串，表示拉取结果或错误。