import ast
from typing import Any

from .interpreter_core import ASTInterpreter

async def visit_Assign(self: ASTInterpreter, node: ast.Assign, wrap_exceptions: bool = True) -> None:
    value: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    for target in node.targets:
        if isinstance(target, ast.Subscript):
            obj = await self.visit(target.value, wrap_exceptions=wrap_exceptions)
            key = await self.visit(target.slice, wrap_exceptions=wrap_exceptions)
            obj[key] = value
        else:
            await self.assign(target, value)

async def visit_AugAssign(self: ASTInterpreter, node: ast.AugAssign, wrap_exceptions: bool = True) -> Any:
    if isinstance(node.target, ast.Name):
        current_val: Any = self.get_variable(node.target.id)
    else:
        current_val: Any = await self.visit(node.target, wrap_exceptions=wrap_exceptions)
    right_val: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    op = node.op
    if isinstance(op, ast.Add):
        result: Any = current_val + right_val
    elif isinstance(op, ast.Sub):
        result = current_val - right_val
    elif isinstance(op, ast.Mult):
        result = current_val * right_val
    elif isinstance(op, ast.Div):
        result = current_val / right_val
    elif isinstance(op, ast.FloorDiv):
        result = current_val // right_val
    elif isinstance(op, ast.Mod):
        result = current_val % right_val
    elif isinstance(op, ast.Pow):
        result = current_val**right_val
    elif isinstance(op, ast.BitAnd):
        result = current_val & right_val
    elif isinstance(op, ast.BitOr):
        result = current_val | right_val
    elif isinstance(op, ast.BitXor):
        result = current_val ^ right_val
    elif isinstance(op, ast.LShift):
        result = current_val << right_val
    elif isinstance(op, ast.RShift):
        result = current_val >> right_val
    else:
        raise Exception("Unsupported augmented operator: " + str(op))
    await self.assign(node.target, result)
    return result

async def visit_AnnAssign(self: ASTInterpreter, node: ast.AnnAssign, wrap_exceptions: bool = True) -> None:
    value = await self.visit(node.value, wrap_exceptions=wrap_exceptions) if node.value else None
    annotation = await self.visit(node.annotation, wrap_exceptions=True)
    if isinstance(node.target, ast.Name):
        self.type_hints[node.target.id] = annotation
    if value is not None or node.simple:
        await self.assign(node.target, value)

async def visit_NamedExpr(self: ASTInterpreter, node: ast.NamedExpr, wrap_exceptions: bool = True) -> Any:
    value = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    await self.assign(node.target, value)
    return value