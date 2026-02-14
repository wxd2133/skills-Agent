---
name: web-search
description: "在网页上搜索信息，返回标题、摘要和链接"
tools:
  - name: web_search
    function: web_search
    parameters:
      type: object
      properties:
        query:
          type: string
          description: "搜索关键词或问句，支持中文和英文"
        max_results:
          type: integer
          description: "返回结果数量，默认 5，建议 3-10"
      required:
        - query
---

# 🔍 网页搜索技能 (web-search)

在互联网上搜索信息，返回与关键词相关的网页标题、摘要和链接，供 Agent 归纳后回答用户。

## 工具一览

### `web_search` — 网页搜索

使用搜索引擎进行文本搜索，返回若干条结果的标题、摘要和 URL。

**何时使用：** 用户询问实时信息、事实、新闻、概念解释，或需要“查一下”“搜一下”时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 搜索关键词或完整问句，如「Python 3.12 新特性」「北京今天天气」 |
| `max_results` | integer | ❌ | 返回条数，默认 5，建议 3～10 |

**调用示例：**
```
web_search(query="Python asyncio 入门教程", max_results=5)
web_search(query="2024 诺贝尔物理学奖")
```

**返回格式：** 每条结果包含标题、摘要（body）、链接（href），工具会格式化为易读文本。

**注意事项：**
- 依赖网络，若搜索失败会返回错误提示
- 结果来自公开搜索引擎，请结合摘要判断是否引用、并提醒用户核实
- 不宜用敏感词或违法内容进行搜索
