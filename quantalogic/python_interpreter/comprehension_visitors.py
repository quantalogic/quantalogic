import ast
from typing import Any, Dict, List

from .interpreter_core import ASTInterpreter

async def visit_ListComp(self: ASTInterpreter, node: ast.ListComp, wrap_exceptions: bool = True) -> List[Any]:
    """
    Handle list comprehensions with support for multiple generators and conditional filters.
    Updated to use recursive approach for consistency with other comprehensions.
    """
    result = []
    base_frame = self.env_stack[-1].copy()
    self.env_stack.append(base_frame)

    async def rec(gen_idx: int):
        if gen_idx == len(node.generators):
            # Base case: evaluate the element and append to results
            element = await self.visit(node.elt, wrap_exceptions=wrap_exceptions)
            result.append(element)
        else:
            # Recursive case: process the current generator
            comp = node.generators[gen_idx]
            iterable = await self.visit(comp.iter, wrap_exceptions=wrap_exceptions)
            # Handle both async and sync iterables
            if hasattr(iterable, '__aiter__'):
                async for item in iterable:
                    new_frame = self.env_stack[-1].copy()
                    self.env_stack.append(new_frame)
                    await self.assign(comp.target, item)
                    # Evaluate all if clauses for this generator
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
                    # Re-raise with context if iterable is not valid
                    raise TypeError(f"Object {iterable} is not iterable") from e

    await rec(0)
    self.env_stack.pop()
    return result

async def visit_DictComp(self: ASTInterpreter, node: ast.DictComp, wrap_exceptions: bool = True) -> Dict[Any, Any]:
    """
    Handle dictionary comprehensions with multiple generators and conditions.
    Original implementation preserved with minor style alignment.
    """
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
                    raise TypeError(f"Object {iterable} is not iterable") from e

    await rec(0)
    self.env_stack.pop()
    return result

async def visit_SetComp(self: ASTInterpreter, node: ast.SetComp, wrap_exceptions: bool = True) -> set:
    """
    Handle set comprehensions with multiple generators and conditions.
    Original implementation preserved with minor style alignment.
    """
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
                    raise TypeError(f"Object {iterable} is not iterable") from e

    await rec(0)
    self.env_stack.pop()
    return result

async def visit_GeneratorExp(self: ASTInterpreter, node: ast.GeneratorExp, wrap_exceptions: bool = True) -> Any:
    """
    Handle generator expressions by returning a lazy async generator.
    Updated to yield values one at a time instead of collecting into a list.
    """
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
                        raise TypeError(f"Object {iterable} is not iterable") from e

        async for val in rec(0):
            yield val

    self.env_stack.pop()
    return gen()