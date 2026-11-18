"""
数学计算技能 - 工具实现
提供表达式计算、方程求解和单位换算功能。
"""

from __future__ import annotations

import ast
import math
import operator


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_MAX_EXPR_LEN = 500
_MAX_ABS_EXPONENT = 1000
_MAX_FACTORIAL = 1000


def _safe_calculate(expression: str):
    """只允许数字、白名单函数和四则运算，拒绝属性访问与任意代码。"""
    if len(expression) > _MAX_EXPR_LEN:
        raise ValueError(f"表达式过长（上限 {_MAX_EXPR_LEN} 字符）")

    env = {
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        "pow": pow, "int": int, "float": float,
        "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "ceil": math.ceil, "floor": math.floor,
        "pi": math.pi, "e": math.e,
        "factorial": math.factorial, "gcd": math.gcd,
    }

    def walk(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError("只允许数字常量")
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise ValueError(f"不允许的名称: {node.id}")
            return env[node.id]
        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError("不允许的运算符")
            return op(walk(node.operand))
        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise ValueError("不允许的运算符")
            left = walk(node.left)
            right = walk(node.right)
            if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > _MAX_ABS_EXPONENT:
                raise ValueError("指数过大")
            return op(left, right)
        if isinstance(node, (ast.List, ast.Tuple)):
            return [walk(item) for item in node.elts]
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise ValueError("不允许的函数调用")
            fn = env.get(node.func.id)
            if not callable(fn):
                raise ValueError(f"不允许的函数: {node.func.id}")
            args = [walk(arg) for arg in node.args]
            if node.func.id == "factorial":
                if len(args) != 1 or isinstance(args[0], bool) or not isinstance(args[0], int):
                    raise ValueError("factorial 只接受一个整数")
                if args[0] < 0 or args[0] > _MAX_FACTORIAL:
                    raise ValueError(f"factorial 参数需在 0 到 {_MAX_FACTORIAL} 之间")
            return fn(*args)
        raise ValueError("表达式包含不允许的语法")

    tree = ast.parse(expression, mode="eval")
    return walk(tree.body)


def calculate(expression: str) -> str:
    """
    计算数学表达式。

    参数:
        expression: 数学表达式字符串

    返回:
        计算结果的字符串。
    """
    try:
        result = _safe_calculate(expression)
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
        from sympy import (  # type: ignore[import-untyped]
            E, Eq, Float, Function, Integer, Rational, Symbol,
            cos, exp, factorial, log, pi, sin, solve, sqrt, symbols, tan,
        )
        from sympy.parsing.sympy_parser import (  # type: ignore[import-untyped]
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
            stringify_expr,
        )

        if not variable.isidentifier():
            return f"求解出错: 未知数名称不合法: {variable}"

        var = symbols(variable)
        transformations = standard_transformations + (implicit_multiplication_application,)
        local_dict = {
            "sin": sin, "cos": cos, "tan": tan,
            "exp": exp, "log": log, "sqrt": sqrt,
            "factorial": factorial,
            "pi": pi, "E": E,
        }
        local_dict[variable] = var
        safe_globals = {
            "__builtins__": {},
            "Integer": Integer, "Float": Float, "Rational": Rational,
            "Symbol": Symbol, "Function": Function, "factorial": factorial,
        }

        def _parse(text: str):
            code = stringify_expr(text, local_dict, safe_globals, transformations)
            if "__" in code:
                raise ValueError("表达式包含不允许的语法")
            tree = ast.parse(code, mode="eval")
            allowed = set(safe_globals) | set(local_dict)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Attribute, ast.Subscript, ast.Lambda)):
                    raise ValueError("表达式包含不允许的语法")
                if isinstance(node, ast.Name) and node.id not in allowed:
                    raise ValueError(f"不允许的名称: {node.id}")
                if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name):
                    raise ValueError("表达式包含不允许的语法")
            return parse_expr(
                text,
                local_dict=local_dict,
                global_dict=safe_globals,
                transformations=transformations,
            )

        # 拆分等号两边。解析器只接受数学表达式，不执行任意代码。
        if "=" in equation:
            left_str, right_str = equation.split("=", 1)
            eq = Eq(_parse(left_str.strip()), _parse(right_str.strip()))
        else:
            eq = Eq(_parse(equation), 0)

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
