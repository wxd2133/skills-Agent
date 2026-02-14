---
name: draw-tools
description: "使用字符绘制简单图像、表格、方框和条形图"
tools:
  - name: draw_table
    function: draw_table
    parameters:
      type: object
      properties:
        headers:
          type: array
          items: { type: string }
          description: "表头列名列表"
        rows:
          type: array
          items:
            type: array
            items: { type: string }
          description: "数据行，每行是字符串列表"
      required:
        - headers
        - rows

  - name: draw_box
    function: draw_box
    parameters:
      type: object
      properties:
        width:
          type: integer
          description: "框的宽度（字符数）"
        height:
          type: integer
          description: "框的高度（行数）"
        title:
          type: string
          description: "可选，框内顶部标题"
      required:
        - width
        - height

  - name: draw_shape
    function: draw_shape
    parameters:
      type: object
      properties:
        shape:
          type: string
          enum: [rectangle, triangle, diamond]
          description: "形状类型"
        width:
          type: integer
          description: "宽度（字符数）"
        height:
          type: integer
          description: "高度（行数），triangle/diamond 时为一半高度"
        fill:
          type: string
          description: "填充字符，默认 *"
      required:
        - shape
        - width
        - height

  - name: draw_bar
    function: draw_bar
    parameters:
      type: object
      properties:
        items:
          type: array
          items:
            type: object
            properties:
              label: { type: string }
              value: { type: number }
          description: "标签与数值列表，用于横向条形图"
        bar_width:
          type: integer
          description: "条形图最大显示宽度（字符数），默认 20"
      required:
        - items
---

# 🎨 字符绘制技能 (draw-tools)

使用 ASCII/Unicode 字符在终端或文本中绘制简单图像、表格、方框和条形图，无需图片文件。

## 工具一览

### `draw_table` — 绘制表格

绘制带边框的文本表格，支持表头和多行数据。

**何时使用：** 需要展示结构化数据、对比多列多行时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `headers` | array of string | ✅ | 表头列名，如 `["姓名", "分数", "等级"]` |
| `rows` | array of array | ✅ | 数据行，每行与表头列数一致，如 `[["Alice", "95", "A"], ["Bob", "80", "B"]]` |

**调用示例：**
```
draw_table(
  headers=["项目", "数量", "单价"],
  rows=[["苹果", "3", "5.0"], ["香蕉", "2", "3.0"]]
)
```

**注意事项：**
- 每行单元格数量应与表头数量相同，不足可补空字符串
- 单元格内容会按列宽自动对齐（取该列最大长度）

---

### `draw_box` — 绘制方框

绘制矩形边框，可选框内标题。

**何时使用：** 需要突出某段文字、做分组展示时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `width` | integer | ✅ | 框的宽度（字符数），建议 ≥ 4 |
| `height` | integer | ✅ | 框的高度（行数），建议 ≥ 2 |
| `title` | string | ❌ | 框内第一行的标题文字 |

**调用示例：**
```
draw_box(width=20, height=5, title="提示")
```

---

### `draw_shape` — 绘制简单形状

绘制矩形、三角形、菱形等实心/空心形状。

**何时使用：** 需要简单示意图、流程图中的框或装饰时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `shape` | string | ✅ | 取值为 `rectangle`、`triangle`、`diamond` |
| `width` | integer | ✅ | 宽度（字符数） |
| `height` | integer | ✅ | 高度（行数） |
| `fill` | string | ❌ | 填充字符，默认 `*` |

**调用示例：**
```
draw_shape(shape="rectangle", width=10, height=4)
draw_shape(shape="triangle", width=9, height=5, fill="#")
draw_shape(shape="diamond", width=9, height=5)
```

---

### `draw_bar` — 绘制横向条形图

用字符绘制横向条形图，适合对比几项数值。

**何时使用：** 需要直观对比多个数值大小时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `items` | array | ✅ | 每项为 `{"label": "名称", "value": 数值}` |
| `bar_width` | integer | ❌ | 最长条对应的字符数，默认 20 |

**调用示例：**
```
draw_bar(items=[
  {"label": "A", "value": 80},
  {"label": "B", "value": 50},
  {"label": "C", "value": 100}
], bar_width=15)
```

**注意事项：**
- 数值会按最大值等比缩放显示
- 若所有 value 为 0，则只显示标签和空条

## 通用提示

- 输出为纯文本，可直接放入 Markdown 代码块或终端显示
- 宽度/高度不宜过大，否则在窄屏下换行混乱，建议宽度 ≤ 60、行数 ≤ 30
