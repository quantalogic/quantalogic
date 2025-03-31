#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sympy>=1.12",
#     "numpy>=1.24",
# ]
# ///

"""Advanced math toolbox for Quantalogic Agent with symbolic and numerical operations."""

from typing import Dict, List, Optional, Union, Tuple
import asyncio
import numpy as np
from sympy import (Integral, SympifyError, diff, expand, integrate, latex, 
                 limit, oo, simplify, solve, symbols, sympify, series,
                 Matrix, factor, dsolve, Function)

from quantalogic.tools import create_tool

# Constants
INFINITY = "oo"
NEGATIVE_INFINITY = "-oo"
VALID_DOMAINS = {"reals", "complexes", "positive", "integers"}

# Helper functions
def preprocess_equation(expr_str: str, for_solving: bool = False) -> Tuple[str, bool]:
    """Convert equation with '=' into appropriate form based on operation."""
    expr_str = expr_str.strip()
    if not expr_str:
        raise ValueError("Empty expression provided")
    if '=' in expr_str:
        parts = [p.strip() for p in expr_str.split('=')]
        if len(parts) != 2:
            raise ValueError("Invalid equation: multiple '=' signs detected")
        if not all(parts):
            raise ValueError("Invalid equation: empty side")
        return f"Eq({parts[0]}, {parts[1]})" if for_solving else f"({parts[0]}) - ({parts[1]})", True
    return expr_str, False

def validate_variables(variable: str, variables: str) -> None:
    """Validate variable presence in variables list."""
    vars_list = variables.split()
    if variable not in vars_list:
        raise ValueError(f"Variable '{variable}' not in variables: {variables}")

def parse_bound(bound: Union[float, str, None]) -> Union[float, str, None]:
    """Parse integration/limit bounds with infinity handling."""
    if bound is None:
        return None
    return sympify(str(bound).replace(INFINITY, "oo").replace(NEGATIVE_INFINITY, "-oo"))

# Enhanced symbolic functions
@create_tool
async def symbolic_simplify(
    expression: str,
    variables: str = "x",
    latex_output: bool = False,
    full_simplify: bool = True,
    factor_output: bool = False
) -> str:
    """Simplifies a symbolic expression with factoring option."""
    try:
        syms = symbols(variables.split())
        expr_str, _ = preprocess_equation(expression)
        expr = sympify(expr_str)
        result = simplify(expr) if full_simplify else expr.simplify()
        if factor_output:
            result = factor(result)
        return latex(result) if latex_output else str(result)
    except (SympifyError, ValueError) as e:
        return f"Error: Invalid expression - {str(e)}"
    except Exception as e:
        return f"Error: Simplification failed - {str(e)}"

@create_tool
async def symbolic_solve(
    expression: str,
    variable: str = "x",
    variables: str = "x",
    domain: str = "reals",
    check_solutions: bool = True
) -> List[str]:
    """Solves equations with solution verification."""
    try:
        if domain not in VALID_DOMAINS:
            raise ValueError(f"Domain must be one of {VALID_DOMAINS}")
        validate_variables(variable, variables)
        syms = symbols(variables.split())
        var = symbols(variable)
        expr_str, _ = preprocess_equation(expression, for_solving=True)
        expr = sympify(expr_str)
        solutions = solve(expr, var, domain=domain)
        if check_solutions and solutions:
            original = expr.lhs - expr.rhs if expr.is_Equality else expr
            verified = [sol for sol in solutions if original.subs(var, sol).simplify() == 0]
            solutions = verified if verified else solutions
        return [str(sol) for sol in solutions] if solutions else ["No solutions in specified domain"]
    except (SympifyError, ValueError) as e:
        return [f"Error: Invalid input - {str(e)}"]
    except Exception as e:
        return [f"Error: Solving failed - {str(e)}"]

@create_tool
async def symbolic_diff(
    expression: str,
    variable: str = "x",
    variables: str = "x",
    order: int = 1,
    latex_output: bool = False,
    evaluate: bool = True
) -> str:
    """Computes derivative with evaluation option."""
    try:
        if order < 0:
            raise ValueError("Derivative order must be non-negative")
        validate_variables(variable, variables)
        syms = symbols(variables.split())
        var = symbols(variable)
        expr_str, _ = preprocess_equation(expression)
        expr = sympify(expr_str)
        result = diff(expr, var, order, evaluate=evaluate)
        return latex(result) if latex_output else str(result)
    except (SympifyError, ValueError) as e:
        return f"Error: Invalid input - {str(e)}"
    except Exception as e:
        return f"Error: Differentiation failed - {str(e)}"

@create_tool
async def symbolic_integrate(
    expression: str,
    variable: str = "x",
    variables: str = "x",
    lower_bound: Optional[Union[float, str]] = None,
    upper_bound: Optional[Union[float, str]] = None,
    latex_output: bool = False,
    explain: bool = False,
    method: Optional[str] = None,
    numerical: bool = False
) -> str:
    """Computes integral with numerical option."""
    try:
        validate_variables(variable, variables)
        syms = symbols(variables.split())
        var = symbols(variable)
        expr_str, _ = preprocess_equation(expression)
        expr = sympify(expr_str)
        
        if numerical and lower_bound is not None and upper_bound is not None:
            lb, ub = float(parse_bound(lower_bound)), float(parse_bound(upper_bound))
            if not np.isfinite([lb, ub]).all():
                raise ValueError("Numerical integration requires finite bounds")
            result = str(np.trapz([float(expr.subs(var, x)) for x in np.linspace(lb, ub, 1000)], 
                                dx=(ub-lb)/1000))
        elif lower_bound is not None and upper_bound is not None:
            lb, ub = parse_bound(lower_bound), parse_bound(upper_bound)
            kwargs = {'method': method} if method else {}
            result = integrate(expr, (var, lb, ub), **kwargs)
            if explain:
                indef_kwargs = {'method': method} if method else {}
                indef = integrate(expr, var, **indef_kwargs)
                steps = (f"1. Indefinite integral: {indef}\n"
                        f"2. Upper bound ({ub}): {indef.subs(var, ub)}\n"
                        f"3. Lower bound ({lb}): {indef.subs(var, lb)}\n"
                        f"4. Result: {result}")
                return steps
        else:
            kwargs = {'method': method} if method else {}
            result = integrate(expr, var, **kwargs)
            if explain:
                return f"Indefinite integral: {result} (+C for general solution)"
        
        return latex(result) if latex_output else str(result)
    except (SympifyError, ValueError) as e:
        return f"Error: Invalid input - {str(e)}"
    except Exception as e:
        return f"Error: Integration failed - {str(e)}"

@create_tool
async def symbolic_series(
    expression: str,
    variable: str = "x",
    variables: str = "x",
    point: Union[float, str] = "0",
    order: int = 6,
    latex_output: bool = False,
    direction: str = "+"
) -> str:
    """Computes series expansion with direction control."""
    try:
        if order < 0:
            raise ValueError("Series order must be non-negative")
        validate_variables(variable, variables)
        syms = symbols(variables.split())
        var = symbols(variable)
        expr_str, _ = preprocess_equation(expression)
        expr = sympify(expr_str)
        pt = parse_bound(point)
        result = series(expr, var, pt, order + 1, dir=direction).removeO()
        return latex(result) if latex_output else str(result)
    except (SympifyError, ValueError) as e:
        return f"Error: Invalid input - {str(e)}"
    except Exception as e:
        return f"Error: Series expansion failed - {str(e)}"

@create_tool
async def symbolic_matrix(
    matrix: List[List[str]],
    operation: str = "det",
    latex_output: bool = False
) -> str:
    """Performs matrix operations (determinant, inverse, eigenvalues)."""
    try:
        mat = Matrix([[sympify(elem) for elem in row] for row in matrix])
        operations = {
            "det": mat.det,
            "inv": lambda: mat.inv(),
            "eig": lambda: mat.eigenvals()
        }
        if operation not in operations:
            raise ValueError(f"Operation must be one of {list(operations.keys())}")
        result = operations[operation]()
        return latex(result) if latex_output else str(result)
    except (SympifyError, ValueError) as e:
        return f"Error: Invalid matrix or operation - {str(e)}"
    except Exception as e:
        return f"Error: Matrix operation failed - {str(e)}"

@create_tool
async def symbolic_ode(
    equation: str,
    function: str = "y(x)",
    variables: str = "x",
    initial_conditions: Optional[Dict[str, str]] = None
) -> str:
    """Solves ordinary differential equations."""
    try:
        x = symbols(variables.split()[0])
        y = Function(function.split('(')[0])(x)
        expr_str, _ = preprocess_equation(equation, for_solving=True)
        expr = sympify(expr_str)
        if initial_conditions:
            ics = {sympify(k): sympify(v) for k, v in initial_conditions.items()}
            result = dsolve(expr, y, ics=ics)
        else:
            result = dsolve(expr, y)
        return str(result)
    except (SympifyError, ValueError) as e:
        return f"Error: Invalid ODE or conditions - {str(e)}"
    except Exception as e:
        return f"Error: ODE solving failed - {str(e)}"

# Extended test suite
if __name__ == "__main__":
    async def test_tools():
        test_cases = [
            # Basic functionality
            ("sin(x) + cos(x) = 1", symbolic_solve, {"domain": "reals"}),
            ("x^2 + 2x + 1", symbolic_simplify, {"factor_output": True}),
            ("x^3", symbolic_diff, {"order": 2, "evaluate": False}),
            ("x^2", symbolic_integrate, {"explain": True, "numerical": False}),
            # Advanced features
            ("exp(x)", symbolic_series, {"point": "0", "order": 4, "direction": "+"}),
            ("1/x", symbolic_integrate, {"lower_bound": "1", "upper_bound": "2", "numerical": True}),
            ("x*y = 1", symbolic_solve, {"variable": "y", "variables": "x y", "check_solutions": True}),
            # New features
            ([["1", "2"], ["3", "4"]], symbolic_matrix, {"operation": "det"}),
            ("diff(y(x), x, 2) + y(x) = 0", symbolic_ode, {"initial_conditions": {"y(0)": "1", "diff(y(x), x)(0)": "0"}}),
            ("x^2 - 1", symbolic_simplify, {"latex_output": True, "factor_output": True}),
            # Edge cases
            ("x^2 + 1 = 0", symbolic_solve, {"domain": "integers"}),
            ("sin(x)", symbolic_series, {"point": "oo", "order": 3}),
        ]
        
        for expr, func, kwargs in test_cases:
            result = await func(expr, **kwargs)
            print(f"\nFunction: {func.__name__}")
            print(f"Input: {expr}")
            print(f"Kwargs: {kwargs}")
            print(f"Result: {result}")

    asyncio.run(test_tools())