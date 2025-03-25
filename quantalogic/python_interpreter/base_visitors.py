import ast
from typing import Any

from .exceptions import WrappedException
from .interpreter_core import ASTInterpreter

async def visit_Module(self: ASTInterpreter, node: ast.Module, wrap_exceptions: bool = True) -> Any:
    last_value = None
    for stmt in node.body:
        last_value = await self.visit(stmt, wrap_exceptions=True)
    return last_value

async def visit_Expr(self: ASTInterpreter, node: ast.Expr, wrap_exceptions: bool = True) -> Any:
    return await self.visit(node.value, wrap_exceptions=wrap_exceptions)

async def visit_Pass(self: ASTInterpreter, node: ast.Pass, wrap_exceptions: bool = True) -> None:
    return None

async def visit_TypeIgnore(self: ASTInterpreter, node: ast.TypeIgnore, wrap_exceptions: bool = True) -> None:
    pass