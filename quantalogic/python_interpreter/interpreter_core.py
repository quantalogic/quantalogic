# quantalogic/python_interpreter/interpreter_core.py
import ast
import asyncio
import builtins
import logging
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import BreakException, ContinueException, ReturnException, WrappedException
from .scope import Scope

class ASTInterpreter:
    def __init__(
        self, 
        allowed_modules: List[str], 
        env_stack: Optional[List[Dict[str, Any]]] = None, 
        source: Optional[str] = None,
        restrict_os: bool = True,
        namespace: Optional[Dict[str, Any]] = None
    ) -> None:
        self.allowed_modules: List[str] = allowed_modules
        self.modules: Dict[str, Any] = {mod: __import__(mod) for mod in allowed_modules}
        self.restrict_os: bool = restrict_os
        if env_stack is None:
            self.env_stack: List[Dict[str, Any]] = [{}]
            self.env_stack[0].update(self.modules)
            safe_builtins: Dict[str, Any] = dict(vars(builtins))
            safe_builtins["__import__"] = self.safe_import
            allowed_builtins = {
                "enumerate": enumerate, "zip": zip, "sum": sum, "min": min, "max": max,
                "abs": abs, "round": round, "str": str, "repr": repr, "id": id,
                "type": type, "isinstance": isinstance, "issubclass": issubclass,
                "Exception": Exception, "ZeroDivisionError": ZeroDivisionError,
                "ValueError": ValueError, "TypeError": TypeError,
                "print": print, 
            }
            if not restrict_os:
                allowed_builtins["open"] = open
            safe_builtins.update(allowed_builtins)
            if "set" not in safe_builtins:
                safe_builtins["set"] = set
            self.env_stack[0]["__builtins__"] = safe_builtins
            self.env_stack[0].update(safe_builtins)
            self.env_stack[0]["logger"] = logging.getLogger(__name__)
            if namespace is not None:
                self.env_stack[0].update(namespace)
        else:
            self.env_stack = env_stack
            if "__builtins__" not in self.env_stack[0]:
                safe_builtins: Dict[str, Any] = dict(vars(builtins))
                safe_builtins["__import__"] = self.safe_import
                allowed_builtins = {
                    "enumerate": enumerate, "zip": zip, "sum": sum, "min": min, "max": max,
                    "abs": abs, "round": round, "str": str, "repr": repr, "id": id,
                    "type": type, "isinstance": isinstance, "issubclass": issubclass,
                    "Exception": Exception, "ZeroDivisionError": ZeroDivisionError,
                    "ValueError": ValueError, "TypeError": TypeError,
                    "print": print, 
                }
                if not restrict_os:
                    allowed_builtins["open"] = open
                safe_builtins.update(allowed_builtins)
                if "set" not in safe_builtins:
                    safe_builtins["set"] = set
                self.env_stack[0]["__builtins__"] = safe_builtins
                self.env_stack[0].update(safe_builtins)
                self.env_stack[0]["logger"] = logging.getLogger(__name__)
            if namespace is not None:
                self.env_stack[0].update(namespace)

        if self.restrict_os:
            os_related_modules = {"os", "sys", "subprocess", "shutil", "platform"}
            for mod in os_related_modules:
                if mod in self.modules:
                    del self.modules[mod]
            for mod in list(self.allowed_modules):
                if mod in os_related_modules:
                    self.allowed_modules.remove(mod)

        if source is not None:
            self.source_lines: Optional[List[str]] = source.splitlines()
        else:
            self.source_lines = None

        if "decimal" in self.modules:
            dec = self.modules["decimal"]
            self.env_stack[0]["Decimal"] = dec.Decimal
            self.env_stack[0]["getcontext"] = dec.getcontext
            self.env_stack[0]["setcontext"] = dec.setcontext
            self.env_stack[0]["localcontext"] = dec.localcontext
            self.env_stack[0]["Context"] = dec.Context

        self.loop = None
        self.current_class = None
        self.current_instance = None
        self.current_exception = None
        self.last_exception = None

        # Attach visitor methods
        from . import visit_handlers
        for handler_name in visit_handlers.__all__:
            handler = getattr(visit_handlers, handler_name)
            setattr(self, handler_name, handler.__get__(self, ASTInterpreter))

    def safe_import(
        self,
        name: str,
        globals: Optional[Dict[str, Any]] = None,
        locals: Optional[Dict[str, Any]] = None,
        fromlist: Tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        os_related_modules = {"os", "sys", "subprocess", "shutil", "platform"}
        if self.restrict_os and name in os_related_modules:
            raise ImportError(f"Import Error: Module '{name}' is blocked due to OS restriction.")
        if name not in self.allowed_modules:
            raise ImportError(f"Import Error: Module '{name}' is not allowed. Only {self.allowed_modules} are permitted.")
        return self.modules[name]

    def spawn_from_env(self, env_stack: List[Dict[str, Any]]) -> "ASTInterpreter":
        new_interp = ASTInterpreter(
            self.allowed_modules, 
            env_stack, 
            source="\n".join(self.source_lines) if self.source_lines else None,
            restrict_os=self.restrict_os
        )
        new_interp.loop = self.loop
        return new_interp

    def get_variable(self, name: str) -> Any:
        for frame in reversed(self.env_stack):
            if name in frame:
                return frame[name]
        raise NameError(f"Name '{name}' is not defined.")

    def set_variable(self, name: str, value: Any) -> None:
        if "__nonlocal_names__" in self.env_stack[-1] and name in self.env_stack[-1]["__nonlocal_names__"]:
            for frame in reversed(self.env_stack[:-1]):
                if name in frame:
                    frame[name] = value
                    return
            raise NameError(f"Nonlocal name '{name}' not found in outer scope")
        elif "__global_names__" in self.env_stack[-1] and name in self.env_stack[-1]["__global_names__"]:
            self.env_stack[0][name] = value
        else:
            self.env_stack[-1][name] = value

    async def assign(self, target: ast.AST, value: Any) -> None:
        if isinstance(target, ast.Name):
            self.set_variable(target.id, value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            star_index = None
            for i, elt in enumerate(target.elts):
                if isinstance(elt, ast.Starred):
                    if star_index is not None:
                        raise Exception("Multiple starred expressions not supported")
                    star_index = i
            if star_index is None:
                if len(target.elts) != len(value):
                    raise ValueError("Unpacking mismatch")
                for t, v in zip(target.elts, value):
                    await self.assign(t, v)
            else:
                total = len(value)
                before = target.elts[:star_index]
                after = target.elts[star_index + 1:]
                if len(before) + len(after) > total:
                    raise ValueError("Unpacking mismatch")
                for i, elt2 in enumerate(before):
                    await self.assign(elt2, value[i])
                starred_count = total - len(before) - len(after)
                await self.assign(target.elts[star_index].value, value[len(before):len(before) + starred_count])
                for j, elt2 in enumerate(after):
                    await self.assign(elt2, value[len(before) + starred_count + j])
        elif isinstance(target, ast.Attribute):
            obj = await self.visit(target.value, wrap_exceptions=True)
            setattr(obj, target.attr, value)
        elif isinstance(target, ast.Subscript):
            obj = await self.visit(target.value, wrap_exceptions=True)
            key = await self.visit(target.slice, wrap_exceptions=True)
            obj[key] = value
        else:
            raise Exception("Unsupported assignment target type: " + str(type(target)))

    async def visit(self, node: ast.AST, is_await_context: bool = False, wrap_exceptions: bool = True) -> Any:
        method_name: str = "visit_" + node.__class__.__name__
        method = getattr(self, method_name, self.generic_visit)
        try:
            if method_name == "visit_Call":
                result = await method(node, is_await_context, wrap_exceptions)
            else:
                result = await method(node, wrap_exceptions=wrap_exceptions)
            return result
        except (ReturnException, BreakException, ContinueException):
            raise
        except Exception as e:
            if not wrap_exceptions:
                raise
            lineno = getattr(node, "lineno", None)
            col = getattr(node, "col_offset", None)
            lineno = lineno if lineno is not None else 1
            col = col if col is not None else 0
            context_line = ""
            if self.source_lines and 1 <= lineno <= len(self.source_lines):
                context_line = self.source_lines[lineno - 1]
            raise WrappedException(
                f"Error line {lineno}, col {col}:\n{context_line}\nDescription: {str(e)}", e, lineno, col, context_line
            ) from e

    async def generic_visit(self, node: ast.AST, wrap_exceptions: bool = True) -> Any:
        lineno = getattr(node, "lineno", None)
        context_line = ""
        if self.source_lines and lineno is not None and 1 <= lineno <= len(self.source_lines):
            context_line = self.source_lines[lineno - 1]
        raise Exception(
            f"Unsupported AST node type: {node.__class__.__name__} at line {lineno}.\nContext: {context_line}"
        )

    async def execute_async(self, node: ast.Module) -> Any:
        return await self.visit(node)

    def new_scope(self):
        return Scope(self.env_stack)

    async def _resolve_exception_type(self, node: Optional[ast.AST]) -> Any:
        """Resolve the exception type from an AST node."""
        if node is None:
            return Exception
        if isinstance(node, ast.Name):
            exc_type = self.get_variable(node.id)
            if exc_type in (Exception, ZeroDivisionError, ValueError, TypeError):
                return exc_type
            return exc_type
        if isinstance(node, ast.Call):
            return await self.visit(node, wrap_exceptions=True)
        return None

    async def _create_class_instance(self, cls: type, *args, **kwargs):
        """Create an instance of a class, handling initialization."""
        if cls in (super, Exception, BaseException) or issubclass(cls, BaseException):
            instance = cls.__new__(cls, *args, **kwargs)
            if hasattr(instance, '__init__'):
                init_method = instance.__init__.__func__ if hasattr(instance.__init__, '__func__') else instance.__init__
                await self._execute_function(init_method, [instance] + list(args), kwargs)
            return instance
        instance = object.__new__(cls)
        self.current_instance = instance  # Set current_instance for super() calls
        init_method = cls.__init__.__func__ if hasattr(cls.__init__, '__func__') else cls.__init__
        await self._execute_function(init_method, [instance] + list(args), kwargs)
        self.current_instance = None  # Reset after instantiation
        return instance

    async def _execute_function(self, func: Any, args: list, kwargs: dict) -> Any:
        """Execute a function, handling both sync and async cases."""
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
            return result
        except Exception as e:
            func_name = getattr(func, '__name__', str(func))
            raise WrappedException(f"Error executing {func_name}: {str(e)}", e, 0, 0, "") from e