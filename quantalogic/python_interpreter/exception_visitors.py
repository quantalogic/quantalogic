import ast
from typing import Any, Optional, Tuple

from .exceptions import BaseExceptionGroup, ReturnException, WrappedException
from .interpreter_core import ASTInterpreter

async def visit_Try(self: ASTInterpreter, node: ast.Try, wrap_exceptions: bool = True) -> Any:
    result: Any = None
    try:
        for stmt in node.body:
            result = await self.visit(stmt, wrap_exceptions=False)
    except ReturnException as ret:
        raise ret
    except Exception as e:
        original_e = e.original_exception if isinstance(e, WrappedException) else e
        for handler in node.handlers:
            exc_type = await self._resolve_exception_type(handler.type)
            if exc_type and isinstance(original_e, exc_type):
                if handler.name:
                    self.set_variable(handler.name, original_e)
                handler_result = None
                try:
                    for stmt in handler.body:
                        handler_result = await self.visit(stmt, wrap_exceptions=True)
                except ReturnException as ret:
                    raise ret
                if handler_result is not None:
                    result = handler_result
                break
        else:
            raise
    else:
        for stmt in node.orelse:
            result = await self.visit(stmt, wrap_exceptions=True)
    finally:
        for stmt in node.finalbody:
            await self.visit(stmt, wrap_exceptions=True)
    return result

async def visit_TryStar(self: ASTInterpreter, node: ast.TryStar, wrap_exceptions: bool = True) -> Any:
    result: Any = None
    exc_info: Optional[Tuple] = None

    try:
        for stmt in node.body:
            result = await self.visit(stmt, wrap_exceptions=False)
    except BaseException as e:
        exc_info = (type(e), e, e.__traceback__)
        handled = False
        if isinstance(e, BaseExceptionGroup):
            remaining_exceptions = []
            for handler in node.handlers:
                if handler.type is None:
                    exc_type = BaseException
                elif isinstance(handler.type, ast.Name):
                    exc_type = self.get_variable(handler.type.id)
                else:
                    exc_type = await self.visit(handler.type, wrap_exceptions=True)
                matching_exceptions = [ex for ex in e.exceptions if isinstance(ex, exc_type)]
                if matching_exceptions:
                    if handler.name:
                        self.set_variable(handler.name, BaseExceptionGroup("", matching_exceptions))
                    for stmt in handler.body:
                        result = await self.visit(stmt, wrap_exceptions=True)
                    handled = True
                remaining_exceptions.extend([ex for ex in e.exceptions if not isinstance(ex, exc_type)])
            if remaining_exceptions and not handled:
                raise BaseExceptionGroup("Uncaught exceptions", remaining_exceptions)
            if handled:
                exc_info = None
        else:
            for handler in node.handlers:
                if handler.type is None:
                    exc_type = BaseException
                elif isinstance(handler.type, ast.Name):
                    exc_type = self.get_variable(handler.type.id)
                else:
                    exc_type = await self.visit(handler.type, wrap_exceptions=True)
                if exc_info and issubclass(exc_info[0], exc_type):
                    if handler.name:
                        self.set_variable(handler.name, exc_info[1])
                    for stmt in handler.body:
                        result = await self.visit(stmt, wrap_exceptions=True)
                    exc_info = None
                    handled = True
                    break
        if exc_info and not handled:
            raise exc_info[1]
    else:
        for stmt in node.orelse:
            result = await self.visit(stmt, wrap_exceptions=True)
    finally:
        for stmt in node.finalbody:
            try:
                await self.visit(stmt, wrap_exceptions=True)
            except ReturnException:
                raise
            except Exception:
                if exc_info:
                    raise exc_info[1]
                raise

    return result

async def visit_Raise(self: ASTInterpreter, node: ast.Raise, wrap_exceptions: bool = True) -> None:
    exc = await self.visit(node.exc, wrap_exceptions=wrap_exceptions) if node.exc else None
    if exc:
        raise exc
    raise Exception("Raise with no exception specified")