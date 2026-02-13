"""
数学计算技能 - 工具实现
提供表达式计算、方程求解和单位换算功能。
"""

from __future__ import annotations

import math


def calculate(expression: str) -> str:
    """
    计算数学表达式。

    参数:
        expression: 数学表达式字符串

    返回:
        计算结果的字符串。
    """
    # 允许使用的安全数学函数
    safe_globals = {"__builtins__": {}}
    safe_locals = {
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        "pow": pow, "int": int, "float": float,
        # math 模块常用函数
        "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "ceil": math.ceil, "floor": math.floor,
        "pi": math.pi, "e": math.e,
        "factorial": math.factorial, "gcd": math.gcd,
    }

    try:
        result = eval(expression, safe_globals, safe_locals)  # noqa: S307
        return f"计算结果: {expression} = {result}"
    except Exception as exc:
        return f"计算出错: {exc}"


def solve_equation(equation: str, variable: str = "x") -> str:
    """
    求解方程。

    参数:
        equation: 方程字符串（用 = 连接）
        variable: 未知数名称

    返回:
        方程的解。
    """
    try:
        from sympy import symbols, Eq, solve, sympify  # type: ignore[import-untyped]

        var = symbols(variable)
        # 拆分等号两边
        if "=" in equation:
            left_str, right_str = equation.split("=", 1)
            left = sympify(left_str.strip())
            right = sympify(right_str.strip())
            eq = Eq(left, right)
        else:
            # 如果没有等号，默认等于 0
            eq = Eq(sympify(equation), 0)

        solutions = solve(eq, var)
        if not solutions:
            return f"方程 {equation} 无解"
        sol_str = ", ".join(str(s) for s in solutions)
        return f"方程 {equation} 的解: {variable} = {sol_str}"

    except ImportError:
        return "错误: 需要安装 sympy 库 (pip install sympy)"
    except Exception as exc:
        return f"求解出错: {exc}"


def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
    """
    单位换算。

    参数:
        value:     数值
        from_unit: 原始单位
        to_unit:   目标单位

    返回:
        换算结果。
    """
    # 单位换算表（统一转换为基准单位）
    length_to_m = {
        "km": 1000, "m": 1, "cm": 0.01, "mm": 0.001,
        "mile": 1609.344, "yard": 0.9144, "foot": 0.3048, "ft": 0.3048,
        "inch": 0.0254, "in": 0.0254,
    }
    weight_to_kg = {
        "t": 1000, "kg": 1, "g": 0.001, "mg": 0.000001,
        "lb": 0.453592, "oz": 0.0283495,
    }
    # 温度需要特殊处理
    temp_units = {"celsius", "fahrenheit", "kelvin", "c", "f", "k"}

    from_lower = from_unit.lower().strip()
    to_lower = to_unit.lower().strip()

    try:
        # 温度换算
        if from_lower in temp_units or to_lower in temp_units:
            return _convert_temperature(value, from_lower, to_lower)

        # 长度换算
        if from_lower in length_to_m and to_lower in length_to_m:
            result = value * length_to_m[from_lower] / length_to_m[to_lower]
            return f"{value} {from_unit} = {result:.6g} {to_unit}"

        # 重量换算
        if from_lower in weight_to_kg and to_lower in weight_to_kg:
            result = value * weight_to_kg[from_lower] / weight_to_kg[to_lower]
            return f"{value} {from_unit} = {result:.6g} {to_unit}"

        return f"不支持的单位换算: {from_unit} → {to_unit}"

    except Exception as exc:
        return f"单位换算出错: {exc}"


def _convert_temperature(value: float, from_u: str, to_u: str) -> str:
    """温度单位换算。"""
    # 归一化单位名
    normalize = {"celsius": "c", "fahrenheit": "f", "kelvin": "k"}
    f = normalize.get(from_u, from_u)
    t = normalize.get(to_u, to_u)

    if f == t:
        return f"{value} {from_u} = {value} {to_u}"

    # 先转为摄氏度
    if f == "c":
        celsius = value
    elif f == "f":
        celsius = (value - 32) * 5 / 9
    elif f == "k":
        celsius = value - 273.15
    else:
        return f"不支持的温度单位: {from_u}"

    # 从摄氏度转为目标
    if t == "c":
        result = celsius
    elif t == "f":
        result = celsius * 9 / 5 + 32
    elif t == "k":
        result = celsius + 273.15
    else:
        return f"不支持的温度单位: {to_u}"

    return f"{value} {from_u} = {result:.4g} {to_u}"
