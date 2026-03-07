---
name: web-search
description: "在网页上搜索信息、获取当前日期时间、根据 URL 获取网页内容"
tools:
  - name: get_time
    function: get_time
    parameters:
      type: object
      properties:
        timezone:
          type: string
          description: "时区名称，如 Asia/Shanghai、UTC；空则使用本机本地时间"
      required: []

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

  - name: get_webpage
    function: get_webpage
    parameters:
      type: object
      properties:
        url:
          type: string
          description: "网页 URL，须为 http 或 https"
        max_chars:
          type: integer
          description: "最多返回字符数，默认 12000"
      required:
        - url
---

# 🔍 网页搜索技能 (web-search)

在互联网上搜索信息，返回与关键词相关的网页标题、摘要和链接；可获取当前日期时间；可根据 URL 获取网页正文内容（去标签文本）。

## 工具一览

### `get_time` — 获取当前日期时间

返回当前日期、时间和星期（可指定时区）。

**何时使用：** 用户问「今天几号」「现在几点」「今年是哪年」；或在做网页搜索前需要先确认当前日期/时间以缩小范围、避免过期信息时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `timezone` | string | ❌ | 时区名，如 `Asia/Shanghai`、`UTC`、`America/New_York`；不传则使用本机本地时间 |

**调用示例：**
```
get_time()
get_time(timezone="Asia/Shanghai")
get_time(timezone="UTC")
```

---

### `get_webpage` — 获取网页内容

根据 URL 拉取网页，去除 HTML 标签后返回正文文本片段（UTF-8），便于归纳或引用。

**何时使用：** 用户给了一个链接要「打开看看」「抓取内容」「总结这个页面」；或 web_search 返回某条链接后需要进一步读取该页正文时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ✅ | 网页 URL，须为 http 或 https |
| `max_chars` | integer | ❌ | 最多返回字符数，默认 12000 |

**调用示例：**
```
get_webpage(url="https://example.com/article")
```

**注意：** 仅支持公开可访问的 http/https 链接；若页面需登录或反爬较严，可能无法获取完整内容。

---

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
