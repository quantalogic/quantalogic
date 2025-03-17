import ast
from typing import Any

from .exceptions import ReturnException
from .interpreter_core import ASTInterpreter

async def visit_With(self: ASTInterpreter, node: ast.With, wrap_exceptions: bool = True) -> Any:
    result = None
    for item in node.items:
        ctx = await self.visit(item.context_expr, wrap_exceptions=wrap_exceptions)
        val = ctx.__enter__()
        if item.optional_vars:
            await self.assign(item.optional_vars, val)
        try:
            for stmt in node.body:
                result = await self.visit(stmt, wrap_exceptions=wrap_exceptions)
        except ReturnException as ret:
            ctx.__exit__(None, None, None)
            raise ret
        except Exception as e:
            if not ctx.__exit__(type(e), e, None):
                raise
        else:
            ctx.__exit__(None, None, None)
    return result

async def visit_AsyncWith(self: ASTInterpreter, node: ast.AsyncWith, wrap_exceptions: bool = True):
    for item in node.items:
        ctx = await self.visit(item.context_expr, wrap_exceptions=wrap_exceptions)
        val = await ctx.__aenter__()
        if item.optional_vars:
            await self.assign(item.optional_vars, val)
        try:
            for stmt in node.body:
                try:
                    await self.visit(stmt, wrap_exceptions=wrap_exceptions)
                except ReturnException as ret:
                    await ctx.__aexit__(None, None, None)
                    raise ret
        except ReturnException as ret:
            raise ret
        except Exception as e:
            if not await ctx.__aexit__(type(e), e, None):
                raise
        else:
            await ctx.__aexit__(None, None, None)