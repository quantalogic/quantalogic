import ast
from typing import Any

from .interpreter_core import ASTInterpreter

async def visit_Global(self: ASTInterpreter, node: ast.Global, wrap_exceptions: bool = True) -> None:
    self.env_stack[-1].setdefault("__global_names__", set()).update(node.names)

async def visit_Nonlocal(self: ASTInterpreter, node: ast.Nonlocal, wrap_exceptions: bool = True) -> None:
    self.env_stack[-1].setdefault("__nonlocal_names__", set()).update(node.names)

async def visit_Delete(self: ASTInterpreter, node: ast.Delete, wrap_exceptions: bool = True):
    for target in node.targets:
        if isinstance(target, ast.Name):
            del self.env_stack[-1][target.id]
        elif isinstance(target, ast.Subscript):
            obj = await self.visit(target.value, wrap_exceptions=wrap_exceptions)
            key = await self.visit(target.slice, wrap_exceptions=wrap_exceptions)
            del obj[key]
        else:
            raise Exception(f"Unsupported del target: {type(target).__name__}")

async def visit_Assert(self: ASTInterpreter, node: ast.Assert, wrap_exceptions: bool = True) -> None:
    test = await self.visit(node.test, wrap_exceptions=wrap_exceptions)
    if not test:
        msg = await self.visit(node.msg, wrap_exceptions=wrap_exceptions) if node.msg else "Assertion failed"
        raise AssertionError(msg)

async def visit_Yield(self: ASTInterpreter, node: ast.Yield, wrap_exceptions: bool = True) -> Any:
    value = await self.visit(node.value, wrap_exceptions=wrap_exceptions) if node.value else None
    self.recursion_depth += 1  # Treat yields as recursion for loop detection
    if self.recursion_depth > self.max_recursion_depth:
        raise RecursionError(f"Maximum recursion depth exceeded in yield ({self.max_recursion_depth})")
    self.recursion_depth -= 1
    return value

async def visit_YieldFrom(self: ASTInterpreter, node: ast.YieldFrom, wrap_exceptions: bool = True) -> Any:
    iterable = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    if hasattr(iterable, '__aiter__'):
        async def async_gen():
            async for value in iterable:
                yield value
        return async_gen()
    else:
        def sync_gen():
            for value in iterable:
                yield value
        return sync_gen()

async def visit_Match(self: ASTInterpreter, node: ast.Match, wrap_exceptions: bool = True) -> Any:
    subject = await self.visit(node.subject, wrap_exceptions=wrap_exceptions)
    result = None
    base_frame = self.env_stack[-1].copy()
    for case in node.cases:
        self.env_stack.append(base_frame.copy())
        try:
            if await self._match_pattern(subject, case.pattern):
                if case.guard and not await self.visit(case.guard, wrap_exceptions=True):
                    continue
                for stmt in case.body[:-1]:
                    await self.visit(stmt, wrap_exceptions=wrap_exceptions)
                result = await self.visit(case.body[-1], wrap_exceptions=wrap_exceptions)
                break
        finally:
            self.env_stack.pop()
    return result

async def _match_pattern(self: ASTInterpreter, subject: Any, pattern: ast.AST) -> bool:
    if isinstance(pattern, ast.MatchValue):
        value = await self.visit(pattern.value, wrap_exceptions=True)
        return subject == value
    elif isinstance(pattern, ast.MatchSingleton):
        return subject is pattern.value
    elif isinstance(pattern, ast.MatchSequence):
        if not isinstance(subject, (list, tuple)):
            return False
        if len(pattern.patterns) != len(subject) and not any(isinstance(p, ast.MatchStar) for p in pattern.patterns):
            return False
        star_idx = None
        for i, pat in enumerate(pattern.patterns):
            if isinstance(pat, ast.MatchStar):
                if star_idx is not None:
                    return False
                star_idx = i
        if star_idx is None:
            for sub, pat in zip(subject, pattern.patterns):
                if not await self._match_pattern(sub, pat):
                    return False
            return True
        else:
            before = pattern.patterns[:star_idx]
            after = pattern.patterns[star_idx + 1:]
            if len(before) + len(after) > len(subject):
                return False
            for sub, pat in zip(subject[:len(before)], before):
                if not await self._match_pattern(sub, pat):
                    return False
            for sub, pat in zip(subject[len(subject) - len(after):], after):
                if not await self._match_pattern(sub, pat):
                    return False
            star_pat = pattern.patterns[star_idx]
            star_count = len(subject) - len(before) - len(after)
            star_sub = subject[len(before):len(before) + star_count]
            if star_pat.name:
                self.set_variable(star_pat.name, star_sub)
            return True
    elif isinstance(pattern, ast.MatchMapping):
        if not isinstance(subject, dict):
            return False
        keys = [await self.visit(k, wrap_exceptions=True) for k in pattern.keys]
        if len(keys) != len(subject) and pattern.rest is None:
            return False
        for k, p in zip(keys, pattern.patterns):
            if k not in subject or not await self._match_pattern(subject[k], p):
                return False
        if pattern.rest:
            remaining = {k: v for k, v in subject.items() if k not in keys}
            self.set_variable(pattern.rest, remaining)
        return True
    elif isinstance(pattern, ast.MatchClass):
        cls = await self.visit(pattern.cls, wrap_exceptions=True)
        if not isinstance(subject, cls):
            return False
        attrs = [getattr(subject, attr) for attr in pattern.attribute_names]
        if len(attrs) != len(pattern.patterns):
            return False
        for attr_val, pat in zip(attrs, pattern.patterns):
            if not await self._match_pattern(attr_val, pat):
                return False
        return True
    elif isinstance(pattern, ast.MatchStar):
        if pattern.name:
            self.set_variable(pattern.name, subject)
        return True
    elif isinstance(pattern, ast.MatchAs):
        if pattern.pattern:
            if not await self._match_pattern(subject, pattern.pattern):
                return False
        if pattern.name:
            self.set_variable(pattern.name, subject)
        return True
    elif isinstance(pattern, ast.MatchOr):
        for pat in pattern.patterns:
            if await self._match_pattern(subject, pat):
                return True
        return False
    else:
        raise Exception(f"Unsupported match pattern: {pattern.__class__.__name__}")