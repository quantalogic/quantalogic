import ast
from typing import Any

from .exceptions import ReturnException
from .interpreter_core import ASTInterpreter

async def visit_With(self: ASTInterpreter, node: ast.With, wrap_exceptions: bool = True) -> Any:
    result = None
    contexts = []
    for item in node.items:
        ctx = await self.visit(item.context_expr, wrap_exceptions=wrap_exceptions)
        val = ctx.__enter__()
        contexts.append((ctx, val))
        if item.optional_vars:
            await self.assign(item.optional_vars, val)
    try:
        for stmt in node.body:
            result = await self.visit(stmt, wrap_exceptions=wrap_exceptions)
    except ReturnException as ret:
        for ctx, _ in reversed(contexts):
            ctx.__exit__(None, None, None)
        raise ret
    except Exception as e:
        exc_type, exc_value, tb = type(e), e, e.__traceback__
        for ctx, _ in reversed(contexts):
            if not ctx.__exit__(exc_type, exc_value, tb):
                raise
        raise
    else:
        for ctx, _ in reversed(contexts):
            ctx.__exit__(None, None, None)
    return result

async def visit_AsyncWith(self: ASTInterpreter, node: ast.AsyncWith, wrap_exceptions: bool = True) -> Any:
    result = None
    contexts = []
    for item in node.items:
        ctx = await self.visit(item.context_expr, wrap_exceptions=wrap_exceptions)
        val = await ctx.__aenter__()
        contexts.append((ctx, val))
        if item.optional_vars:
            await self.assign(item.optional_vars, val)
    try:
        for stmt in node.body:
            result = await self.visit(stmt, wrap_exceptions=wrap_exceptions)
    except ReturnException as ret:
        for ctx, _ in reversed(contexts):
            await ctx.__aexit__(None, None, None)
        raise ret
    except Exception as e:
        exc_type, exc_value, tb = type(e), e, e.__traceback__
        for ctx, _ in reversed(contexts):
            if not await ctx.__aexit__(exc_type, exc_value, tb):
                raise
        raise
    else:
        for ctx, _ in reversed(contexts):
            await ctx.__aexit__(None, None, None)
    return result