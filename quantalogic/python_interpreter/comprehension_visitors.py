import ast
from typing import Any, Dict, List

from .interpreter_core import ASTInterpreter
from .exceptions import WrappedException

async def visit_ListComp(self: ASTInterpreter, node: ast.ListComp, wrap_exceptions: bool = True) -> List[Any]:
    result = []
    base_frame = self.env_stack[-1].copy()
    self.env_stack.append(base_frame)

    async def rec(gen_idx: int):
        if gen_idx == len(node.generators):
            element = await self.visit(node.elt, wrap_exceptions=wrap_exceptions)
            result.append(element)
        else:
            comp = node.generators[gen_idx]
            iterable = await self.visit(comp.iter, wrap_exceptions=wrap_exceptions)
            if hasattr(iterable, '__aiter__'):
                async for item in iterable:
                    new_frame = self.env_stack[-1].copy()
                    self.env_stack.append(new_frame)
                    await self.assign(comp.target, item)
                    conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                    if all(conditions):
                        await rec(gen_idx + 1)
                    self.env_stack.pop()
            else:
                try:
                    for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        await self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()
                except TypeError as e:
                    lineno = getattr(node, "lineno", 1)
                    col = getattr(node, "col_offset", 0)
                    context_line = self.source_lines[lineno - 1] if self.source_lines and lineno <= len(self.source_lines) else ""
                    raise WrappedException(f"Object {iterable} is not iterable", e, lineno, col, context_line) from e

    await rec(0)
    self.env_stack.pop()
    return result

async def visit_DictComp(self: ASTInterpreter, node: ast.DictComp, wrap_exceptions: bool = True) -> Dict[Any, Any]:
    result = {}
    base_frame = self.env_stack[-1].copy()
    self.env_stack.append(base_frame)

    async def rec(gen_idx: int):
        if gen_idx == len(node.generators):
            key = await self.visit(node.key, wrap_exceptions=True)
            val = await self.visit(node.value, wrap_exceptions=True)
            result[key] = val
        else:
            comp = node.generators[gen_idx]
            iterable = await self.visit(comp.iter, wrap_exceptions=wrap_exceptions)
            if hasattr(iterable, '__aiter__'):
                async for item in iterable:
                    new_frame = self.env_stack[-1].copy()
                    self.env_stack.append(new_frame)
                    await self.assign(comp.target, item)
                    conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                    if all(conditions):
                        await rec(gen_idx + 1)
                    self.env_stack.pop()
            else:
                try:
                    for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        await self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()
                except TypeError as e:
                    lineno = getattr(node, "lineno", 1)
                    col = getattr(node, "col_offset", 0)
                    context_line = self.source_lines[lineno - 1] if self.source_lines and lineno <= len(self.source_lines) else ""
                    raise WrappedException(f"Object {iterable} is not iterable", e, lineno, col, context_line) from e

    await rec(0)
    self.env_stack.pop()
    return result

async def visit_SetComp(self: ASTInterpreter, node: ast.SetComp, wrap_exceptions: bool = True) -> set:
    result = set()
    base_frame = self.env_stack[-1].copy()
    self.env_stack.append(base_frame)

    async def rec(gen_idx: int):
        if gen_idx == len(node.generators):
            result.add(await self.visit(node.elt, wrap_exceptions=True))
        else:
            comp = node.generators[gen_idx]
            iterable = await self.visit(comp.iter, wrap_exceptions=wrap_exceptions)
            if hasattr(iterable, '__aiter__'):
                async for item in iterable:
                    new_frame = self.env_stack[-1].copy()
                    self.env_stack.append(new_frame)
                    await self.assign(comp.target, item)
                    conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                    if all(conditions):
                        await rec(gen_idx + 1)
                    self.env_stack.pop()
            else:
                try:
                    for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        await self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()
                except TypeError as e:
                    lineno = getattr(node, "lineno", 1)
                    col = getattr(node, "col_offset", 0)
                    context_line = self.source_lines[lineno - 1] if self.source_lines and lineno <= len(self.source_lines) else ""
                    raise WrappedException(f"Object {iterable} is not iterable", e, lineno, col, context_line) from e

    await rec(0)
    self.env_stack.pop()
    return result

async def visit_GeneratorExp(self: ASTInterpreter, node: ast.GeneratorExp, wrap_exceptions: bool = True) -> Any:
    base_frame: Dict[str, Any] = self.env_stack[-1].copy()
    self.env_stack.append(base_frame)

    async def gen():
        async def rec(gen_idx: int):
            if gen_idx == len(node.generators):
                yield await self.visit(node.elt, wrap_exceptions=True)
            else:
                comp = node.generators[gen_idx]
                iterable = await self.visit(comp.iter, wrap_exceptions=wrap_exceptions)
                if hasattr(iterable, '__aiter__'):
                    async for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        await self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                        if all(conditions):
                            async for val in rec(gen_idx + 1):
                                yield val
                        self.env_stack.pop()
                else:
                    try:
                        for item in iterable:
                            new_frame = self.env_stack[-1].copy()
                            self.env_stack.append(new_frame)
                            await self.assign(comp.target, item)
                            conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                            if all(conditions):
                                async for val in rec(gen_idx + 1):
                                    yield val
                            self.env_stack.pop()
                    except TypeError as e:
                        lineno = getattr(node, "lineno", 1)
                        col = getattr(node, "col_offset", 0)
                        context_line = self.source_lines[lineno - 1] if self.source_lines and lineno <= len(self.source_lines) else ""
                        raise WrappedException(f"Object {iterable} is not iterable", e, lineno, col, context_line) from e

        async for val in rec(0):
            yield val

    self.env_stack.pop()
    return gen()