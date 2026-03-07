---
name: web-browse
description: 提供网页浏览功能，包括搜索和获取网页内容
tools:
- name: web_search
  function: web_search
  parameters:
    type: object
    properties:
      query:
        type: string
        description: 搜索查询词
    required:
    - query
- name: get_webpage
  function: get_webpage
  parameters:
    type: object
    properties:
      url:
        type: string
        description: 网页URL
    required:
    - url
---

# web-browse

## 概述
此技能提供网页浏览功能，支持搜索和获取网页内容。

## 工具

### `web_search` — 在网页上搜索信息
返回搜索结果的标题、摘要和链接。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 搜索查询词 |

**调用示例：**
```
web_search(query="人工智能")
```

### `get_webpage` — 获取网页内容
返回指定URL的网页内容。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ✅ | 网页URL |

**调用示例：**
```
get_webpage(url="https://example.com")
```