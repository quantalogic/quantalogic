import ast
from typing import Any

from .exceptions import BreakException, ContinueException, ReturnException
from .interpreter_core import ASTInterpreter

async def visit_If(self: ASTInterpreter, node: ast.If, wrap_exceptions: bool = True) -> Any:
    if await self.visit(node.test, wrap_exceptions=wrap_exceptions):
        branch = node.body
    else:
        branch = node.orelse
    result = None
    if branch:
        for stmt in branch[:-1]:
            await self.visit(stmt, wrap_exceptions=wrap_exceptions)
        result = await self.visit(branch[-1], wrap_exceptions=wrap_exceptions)
    return result

async def visit_While(self: ASTInterpreter, node: ast.While, wrap_exceptions: bool = True) -> None:
    while await self.visit(node.test, wrap_exceptions=wrap_exceptions):
        try:
            for stmt in node.body:
                await self.visit(stmt, wrap_exceptions=wrap_exceptions)
        except BreakException:
            break
        except ContinueException:
            continue
    for stmt in node.orelse:
        await self.visit(stmt, wrap_exceptions=wrap_exceptions)

async def visit_For(self: ASTInterpreter, node: ast.For, wrap_exceptions: bool = True) -> None:
    iter_obj: Any = await self.visit(node.iter, wrap_exceptions=wrap_exceptions)
    broke = False
    if hasattr(iter_obj, '__aiter__'):
        async for item in iter_obj:
            await self.assign(node.target, item)
            try:
                for stmt in node.body:
                    await self.visit(stmt, wrap_exceptions=wrap_exceptions)
            except BreakException:
                broke = True
                break
            except ContinueException:
                continue
    else:
        for item in iter_obj:
            await self.assign(node.target, item)
            try:
                for stmt in node.body:
                    await self.visit(stmt, wrap_exceptions=wrap_exceptions)
            except BreakException:
                broke = True
                break
            except ContinueException:
                continue
    if not broke:
        for stmt in node.orelse:
            await self.visit(stmt, wrap_exceptions=wrap_exceptions)

async def visit_AsyncFor(self: ASTInterpreter, node: ast.AsyncFor, wrap_exceptions: bool = True) -> None:
    iterable = await self.visit(node.iter, wrap_exceptions=wrap_exceptions)
    broke = False
    async for value in iterable:
        await self.assign(node.target, value)
        try:
            for stmt in node.body:
                await self.visit(stmt, wrap_exceptions=wrap_exceptions)
        except BreakException:
            broke = True
            break
        except ContinueException:
            continue
    if not broke:
        for stmt in node.orelse:
            await self.visit(stmt, wrap_exceptions=wrap_exceptions)

async def visit_Break(self: ASTInterpreter, node: ast.Break, wrap_exceptions: bool = True) -> None:
    raise BreakException()

async def visit_Continue(self: ASTInterpreter, node: ast.Continue, wrap_exceptions: bool = True) -> None:
    raise ContinueException()

async def visit_Return(self: ASTInterpreter, node: ast.Return, wrap_exceptions: bool = True) -> None:
    value: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions) if node.value is not None else None
    raise ReturnException(value)

async def visit_IfExp(self: ASTInterpreter, node: ast.IfExp, wrap_exceptions: bool = True) -> Any:
    return await self.visit(node.body, wrap_exceptions=wrap_exceptions) if await self.visit(node.test, wrap_exceptions=wrap_exceptions) else await self.visit(node.orelse, wrap_exceptions=wrap_exceptions)