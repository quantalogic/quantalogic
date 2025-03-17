import ast
from typing import Any

from .interpreter_core import ASTInterpreter

async def visit_BinOp(self: ASTInterpreter, node: ast.BinOp, wrap_exceptions: bool = True) -> Any:
    left: Any = await self.visit(node.left, wrap_exceptions=wrap_exceptions)
    right: Any = await self.visit(node.right, wrap_exceptions=wrap_exceptions)
    op = node.op
    if isinstance(op, ast.Add):
        return left + right
    elif isinstance(op, ast.Sub):
        if isinstance(left, set) and isinstance(right, set):
            return left - right
        return left - right
    elif isinstance(op, ast.Mult):
        return left * right
    elif isinstance(op, ast.Div):
        return left / right
    elif isinstance(op, ast.FloorDiv):
        return left // right
    elif isinstance(op, ast.Mod):
        return left % right
    elif isinstance(op, ast.Pow):
        return left**right
    elif isinstance(op, ast.LShift):
        return left << right
    elif isinstance(op, ast.RShift):
        return left >> right
    elif isinstance(op, ast.BitOr):
        if isinstance(left, set) and isinstance(right, set):
            return left | right
        return left | right
    elif isinstance(op, ast.BitXor):
        return left ^ right
    elif isinstance(op, ast.BitAnd):
        if isinstance(left, set) and isinstance(right, set):
            return left & right
        return left & right
    else:
        raise Exception("Unsupported binary operator: " + str(op))

async def visit_UnaryOp(self: ASTInterpreter, node: ast.UnaryOp, wrap_exceptions: bool = True) -> Any:
    operand: Any = await self.visit(node.operand, wrap_exceptions=wrap_exceptions)
    op = node.op
    if isinstance(op, ast.UAdd):
        return +operand
    elif isinstance(op, ast.USub):
        return -operand
    elif isinstance(op, ast.Not):
        return not operand
    elif isinstance(op, ast.Invert):
        return ~operand
    else:
        raise Exception("Unsupported unary operator: " + str(op))

async def visit_Compare(self: ASTInterpreter, node: ast.Compare, wrap_exceptions: bool = True) -> bool:
    left: Any = await self.visit(node.left, wrap_exceptions=wrap_exceptions)
    for op, comparator in zip(node.ops, node.comparators):
        right: Any = await self.visit(comparator, wrap_exceptions=wrap_exceptions)
        if isinstance(op, ast.Eq):
            if not (left == right):
                return False
        elif isinstance(op, ast.NotEq):
            if not (left != right):
                return False
        elif isinstance(op, ast.Lt):
            if not (left < right):
                return False
        elif isinstance(op, ast.LtE):
            if not (left <= right):
                return False
        elif isinstance(op, ast.Gt):
            if not (left > right):
                return False
        elif isinstance(op, ast.GtE):
            if not (left >= right):
                return False
        elif isinstance(op, ast.Is):
            if left is not right:
                return False
        elif isinstance(op, ast.IsNot):
            if not (left is not right):
                return False
        elif isinstance(op, ast.In):
            if left not in right:
                return False
        elif isinstance(op, ast.NotIn):
            if not (left not in right):
                return False
        else:
            raise Exception("Unsupported comparison operator: " + str(op))
        left = right
    return True

async def visit_BoolOp(self: ASTInterpreter, node: ast.BoolOp, wrap_exceptions: bool = True) -> bool:
    if isinstance(node.op, ast.And):
        for value in node.values:
            if not await self.visit(value, wrap_exceptions=wrap_exceptions):
                return False
        return True
    elif isinstance(node.op, ast.Or):
        for value in node.values:
            if await self.visit(value, wrap_exceptions=wrap_exceptions):
                return True
        return False
    else:
        raise Exception("Unsupported boolean operator: " + str(node.op))