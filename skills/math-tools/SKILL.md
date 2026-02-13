---
name: math-tools
description: "提供基础数学运算和符号计算能力"
tools:
  - name: calculate
    function: calculate
    parameters:
      type: object
      properties:
        expression:
          type: string
          description: "数学表达式"
      required:
        - expression

  - name: solve_equation
    function: solve_equation
    parameters:
      type: object
      properties:
        equation:
          type: string
          description: "方程表达式，用 = 连接左右两边"
        variable:
          type: string
          description: "要求解的变量名，默认 x"
      required:
        - equation

  - name: unit_convert
    function: unit_convert
    parameters:
      type: object
      properties:
        value:
          type: number
          description: "要转换的数值"
        from_unit:
          type: string
          description: "原始单位"
        to_unit:
          type: string
          description: "目标单位"
      required:
        - value
        - from_unit
        - to_unit
---

# 🧮 数学计算技能 (math-tools)

本技能提供三个数学工具，帮助你完成数值计算、方程求解和单位换算任务。

## 工具一览

### `calculate` — 表达式计算

计算任意数学表达式，返回精确结果。

**何时使用：** 用户要求算数、做数学运算、求值时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `expression` | string | ✅ | 数学表达式字符串 |

**支持的函数和常量：**
- 基础运算：`+` `-` `*` `/` `**`（幂）、`%`（取模）
- 数学函数：`sqrt()`, `log()`, `log2()`, `log10()`, `sin()`, `cos()`, `tan()`, `asin()`, `acos()`, `atan()`
- 取整函数：`ceil()`, `floor()`, `round()`, `abs()`
- 常量：`pi`（圆周率）, `e`（自然底数）
- 组合函数：`factorial()`, `gcd()`, `min()`, `max()`

**调用示例：**
```
calculate(expression="2 + 3 * 4")        → 14
calculate(expression="sqrt(144)")         → 12.0
calculate(expression="sin(pi / 2)")       → 1.0
calculate(expression="log2(1024)")        → 10.0
calculate(expression="factorial(10)")     → 3628800
```

**注意事项：**
- 幂运算用 `**`，不要用 `^`
- 三角函数的参数单位是**弧度**，不是角度。如用户说"sin(90°)"，你需要转为 `sin(pi/2)`
- 不支持赋值语句，仅支持纯计算表达式

---

### `solve_equation` — 方程求解

对代数方程进行符号求解，返回变量的所有解。

**何时使用：** 用户要求解方程、求未知数的值时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `equation` | string | ✅ | 等式字符串，用 `=` 分隔左右两边 |
| `variable` | string | ❌ | 求解的未知数，默认 `"x"` |

**调用示例：**
```
solve_equation(equation="x**2 - 4 = 0")                → x = -2, 2
solve_equation(equation="2*x + 3 = 7")                 → x = 2
solve_equation(equation="a**2 + 2*a - 8 = 0", variable="a")  → a = -4, 2
```

**注意事项：**
- 乘法必须显式写 `*`，即 `2*x` 而非 `2x`
- 等号两边都可以有表达式，如 `x**2 + 1 = 2*x`
- 如果方程无解会明确提示
- 依赖 sympy 库进行符号运算

---

### `unit_convert` — 单位换算

在常用度量单位之间进行转换。

**何时使用：** 用户要求单位转换、换算时。

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `value` | number | ✅ | 要转换的数值 |
| `from_unit` | string | ✅ | 原始单位 |
| `to_unit` | string | ✅ | 目标单位 |

**支持的单位：**

| 类别 | 支持的单位 |
|------|-----------|
| 长度 | `km`, `m`, `cm`, `mm`, `mile`, `yard`, `foot`/`ft`, `inch`/`in` |
| 重量 | `t`, `kg`, `g`, `mg`, `lb`, `oz` |
| 温度 | `celsius`/`c`, `fahrenheit`/`f`, `kelvin`/`k` |

**调用示例：**
```
unit_convert(value=5, from_unit="km", to_unit="mile")         → 3.10686
unit_convert(value=100, from_unit="celsius", to_unit="fahrenheit") → 212
unit_convert(value=72, from_unit="kg", to_unit="lb")           → 158.733
```

**注意事项：**
- 单位名称不区分大小写
- 不支持跨类别换算（如长度→重量），遇到此类请求请告知用户不支持
- 温度换算涉及偏移公式，不是简单的比例关系

## 通用提示

- 如果用户的问题同时涉及计算和方程求解，请根据具体情况选择合适的工具
- 遇到纯文字数学题，先自己理解题意并建立表达式，再调用工具求解
- 如果表达式较为复杂，可以拆成多步分别计算
