import ast
import asyncio
import builtins
import inspect  # For class checking in visit_Call
import logging  # Added for error logging in visit_Await
import textwrap
import time
from asyncio import TimeoutError
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable, Type

@dataclass
class AsyncExecutionResult:
    result: Any
    error: Optional[str]
    execution_time: float

class ReturnException(Exception):
    def __init__(self, value: Any) -> None:
        self.value: Any = value

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

class WrappedException(Exception):
    def __init__(self, message: str, original_exception: Exception, lineno: int, col: int, context_line: str):
        super().__init__(message)
        self.original_exception: Exception = original_exception
        self.lineno: int = lineno
        self.col: int = col
        self.context_line: str = context_line
        self.message = str(original_exception)  # Correct variable name

def has_await(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Await):
            return True
    return False

class ASTInterpreter:
    def __init__(
        self, 
        allowed_modules: List[str], 
        env_stack: Optional[List[Dict[str, Any]]] = None, 
        source: Optional[str] = None,
        restrict_os: bool = True,  # New parameter to restrict OS access
        namespace: Optional[Dict[str, Any]] = None  # New parameter for custom namespace
    ) -> None:
        self.allowed_modules: List[str] = allowed_modules
        self.modules: Dict[str, Any] = {mod: __import__(mod) for mod in allowed_modules}
        self.restrict_os: bool = restrict_os  # Store the restriction flag
        if env_stack is None:
            self.env_stack: List[Dict[str, Any]] = [{}]
            self.env_stack[0].update(self.modules)
            safe_builtins: Dict[str, Any] = dict(vars(builtins))
            safe_builtins["__import__"] = self.safe_import
            # Base set of allowed built-ins
            allowed_builtins = {
                "enumerate": enumerate, "zip": zip, "sum": sum, "min": min, "max": max,
                "abs": abs, "round": round, "str": str, "repr": repr, "id": id,
                "type": type, "isinstance": isinstance, "issubclass": issubclass,
                "Exception": Exception, "ZeroDivisionError": ZeroDivisionError,
                "ValueError": ValueError, "TypeError": TypeError,
                "print": print  # Add print to allowed_builtins
            }
            # Only include 'open' if restrict_os is False
            if not restrict_os:
                allowed_builtins["open"] = open
            safe_builtins.update(allowed_builtins)
            if "set" not in safe_builtins:
                safe_builtins["set"] = set
            self.env_stack[0]["__builtins__"] = safe_builtins
            self.env_stack[0].update(safe_builtins)
            # Initialize logger
            self.env_stack[0]["logger"] = logging.getLogger(__name__)
            # Add custom namespace to the global scope if provided
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
                    "print": print  # Add print to allowed_builtins
                }
                # Only include 'open' if restrict_os is False
                if not restrict_os:
                    allowed_builtins["open"] = open
                safe_builtins.update(allowed_builtins)
                if "set" not in safe_builtins:
                    safe_builtins["set"] = set
                self.env_stack[0]["__builtins__"] = safe_builtins
                self.env_stack[0].update(safe_builtins)
                # Initialize logger
                self.env_stack[0]["logger"] = logging.getLogger(__name__)
            # Add custom namespace to the provided env_stack if given
            if namespace is not None:
                self.env_stack[0].update(namespace)

        # Ensure OS-related modules are blocked when restrict_os is True, regardless of allowed_modules
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

    def safe_import(
        self,
        name: str,
        globals: Optional[Dict[str, Any]] = None,
        locals: Optional[Dict[str, Any]] = None,
        fromlist: Tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        # Define OS-related modules to block when restrict_os is True
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
            restrict_os=self.restrict_os  # Pass the restriction flag
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

    async def visit_Import(self, node: ast.Import, wrap_exceptions: bool = True) -> None:
        for alias in node.names:
            module_name: str = alias.name
            asname: str = alias.asname if alias.asname is not None else module_name
            if module_name not in self.allowed_modules:
                raise Exception(
                    f"Import Error: Module '{module_name}' is not allowed. Only {self.allowed_modules} are permitted."
                )
            self.set_variable(asname, self.modules[module_name])

    async def visit_ImportFrom(self, node: ast.ImportFrom, wrap_exceptions: bool = True) -> None:
        if not node.module:
            raise Exception("Import Error: Missing module name in 'from ... import ...' statement")
        if node.module not in self.allowed_modules:
            raise Exception(
                f"Import Error: Module '{node.module}' is not allowed. Only {self.allowed_modules} are permitted."
            )
        for alias in node.names:
            if alias.name == "*":
                raise Exception("Import Error: 'from ... import *' is not supported.")
            asname = alias.asname if alias.asname else alias.name
            attr = getattr(self.modules[node.module], alias.name)
            self.set_variable(asname, attr)

    async def visit_ListComp(self, node: ast.ListComp, wrap_exceptions: bool = True) -> List[Any]:
        results = []
        gen = await self.visit(node.generators[0].iter)
        # Create temporary scope for comprehension
        with self.new_scope():
            try:
                async for value in gen:
                    await self.assign(node.generators[0].target, value)
                    element = await self.visit(node.elt, wrap_exceptions=wrap_exceptions)
                    results.append(element)
            except TypeError:
                for value in gen:
                    await self.assign(node.generators[0].target, value)
                    element = await self.visit(node.elt, wrap_exceptions=wrap_exceptions)
                    results.append(element)
        return results

    async def visit_Module(self, node: ast.Module, wrap_exceptions: bool = True) -> Any:
        last_value = None
        for stmt in node.body:
            last_value = await self.visit(stmt, wrap_exceptions=True)
        return last_value

    async def visit_Expr(self, node: ast.Expr, wrap_exceptions: bool = True) -> Any:
        return await self.visit(node.value, wrap_exceptions=wrap_exceptions)

    async def visit_Constant(self, node: ast.Constant, wrap_exceptions: bool = True) -> Any:
        return node.value

    async def visit_Name(self, node: ast.Name, wrap_exceptions: bool = True) -> Any:
        if isinstance(node.ctx, ast.Load):
            return self.get_variable(node.id)
        elif isinstance(node.ctx, ast.Store):
            return node.id
        else:
            raise Exception("Unsupported context for Name")

    async def visit_BinOp(self, node: ast.BinOp, wrap_exceptions: bool = True) -> Any:
        left: Any = await self.visit(node.left, wrap_exceptions=wrap_exceptions)
        right: Any = await self.visit(node.right, wrap_exceptions=wrap_exceptions)
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        elif isinstance(op, ast.Sub):
            if isinstance(left, set) and isinstance(right, set):
                return left - right
            return left - right
        elif isinstance(op, ast.Mult):
            return left * right
        elif isinstance(op, ast.Div):
            return left / right
        elif isinstance(op, ast.FloorDiv):
            return left // right
        elif isinstance(op, ast.Mod):
            return left % right
        elif isinstance(op, ast.Pow):
            return left**right
        elif isinstance(op, ast.LShift):
            return left << right
        elif isinstance(op, ast.RShift):
            return left >> right
        elif isinstance(op, ast.BitOr):
            if isinstance(left, set) and isinstance(right, set):
                return left | right
            return left | right
        elif isinstance(op, ast.BitXor):
            return left ^ right
        elif isinstance(op, ast.BitAnd):
            if isinstance(left, set) and isinstance(right, set):
                return left & right
            return left & right
        else:
            raise Exception("Unsupported binary operator: " + str(op))

    async def visit_UnaryOp(self, node: ast.UnaryOp, wrap_exceptions: bool = True) -> Any:
        operand: Any = await self.visit(node.operand, wrap_exceptions=wrap_exceptions)
        op = node.op
        if isinstance(op, ast.UAdd):
            return +operand
        elif isinstance(op, ast.USub):
            return -operand
        elif isinstance(op, ast.Not):
            return not operand
        elif isinstance(op, ast.Invert):
            return ~operand
        else:
            raise Exception("Unsupported unary operator: " + str(op))

    async def visit_Assign(self, node: ast.Assign, wrap_exceptions: bool = True) -> None:
        value: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
        for target in node.targets:
            if isinstance(target, ast.Subscript):
                obj = await self.visit(target.value, wrap_exceptions=wrap_exceptions)
                key = await self.visit(target.slice, wrap_exceptions=wrap_exceptions)
                obj[key] = value
            else:
                await self.assign(target, value)

    async def visit_AugAssign(self, node: ast.AugAssign, wrap_exceptions: bool = True) -> Any:
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

    async def visit_Compare(self, node: ast.Compare, wrap_exceptions: bool = True) -> bool:
        left: Any = await self.visit(node.left, wrap_exceptions=wrap_exceptions)
        for op, comparator in zip(node.ops, node.comparators):
            right: Any = await self.visit(comparator, wrap_exceptions=wrap_exceptions)
            if isinstance(op, ast.Eq):
                if not (left == right):
                    return False
            elif isinstance(op, ast.NotEq):
                if not (left != right):
                    return False
            elif isinstance(op, ast.Lt):
                if not (left < right):
                    return False
            elif isinstance(op, ast.LtE):
                if not (left <= right):
                    return False
            elif isinstance(op, ast.Gt):
                if not (left > right):
                    return False
            elif isinstance(op, ast.GtE):
                if not (left >= right):
                    return False
            elif isinstance(op, ast.Is):
                if left is not right:
                    return False
            elif isinstance(op, ast.IsNot):
                if not (left is not right):
                    return False
            elif isinstance(op, ast.In):
                if left not in right:
                    return False
            elif isinstance(op, ast.NotIn):
                if not (left not in right):
                    return False
            else:
                raise Exception("Unsupported comparison operator: " + str(op))
            left = right
        return True

    async def visit_BoolOp(self, node: ast.BoolOp, wrap_exceptions: bool = True) -> bool:
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not await self.visit(value, wrap_exceptions=wrap_exceptions):
                    return False
            return True
        elif isinstance(node.op, ast.Or):
            for value in node.values:
                if await self.visit(value, wrap_exceptions=wrap_exceptions):
                    return True
            return False
        else:
            raise Exception("Unsupported boolean operator: " + str(node.op))

    async def visit_If(self, node: ast.If, wrap_exceptions: bool = True) -> Any:
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

    async def visit_While(self, node: ast.While, wrap_exceptions: bool = True) -> None:
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

    async def visit_For(self, node: ast.For, wrap_exceptions: bool = True) -> None:
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

    async def visit_Break(self, node: ast.Break, wrap_exceptions: bool = True) -> None:
        raise BreakException()

    async def visit_Continue(self, node: ast.Continue, wrap_exceptions: bool = True) -> None:
        raise ContinueException()

    async def visit_FunctionDef(self, node: ast.FunctionDef, wrap_exceptions: bool = True) -> None:
        closure: List[Dict[str, Any]] = self.env_stack[:]
        pos_kw_params = [arg.arg for arg in node.args.args]
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwonly_params = [arg.arg for arg in node.args.kwonlyargs]
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        pos_defaults_values = [await self.visit(default, wrap_exceptions=True) for default in node.args.defaults]
        num_pos_defaults = len(pos_defaults_values)
        pos_defaults = dict(zip(pos_kw_params[-num_pos_defaults:], pos_defaults_values)) if num_pos_defaults else {}
        kw_defaults_values = [await self.visit(default, wrap_exceptions=True) if default else None for default in node.args.kw_defaults]
        kw_defaults = dict(zip(kwonly_params, kw_defaults_values))
        kw_defaults = {k: v for k, v in kw_defaults.items() if v is not None}

        func = Function(node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults)
        decorated_func = func
        for decorator in reversed(node.decorator_list):
            dec = await self.visit(decorator, wrap_exceptions=True)
            if dec in (staticmethod, classmethod, property):
                decorated_func = dec(func)
            else:
                decorated_func = await dec(decorated_func)
        self.set_variable(node.name, decorated_func)

    async def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef, wrap_exceptions: bool = True) -> None:
        closure: List[Dict[str, Any]] = self.env_stack[:]
        pos_kw_params = [arg.arg for arg in node.args.args]
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwonly_params = [arg.arg for arg in node.args.kwonlyargs]
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        pos_defaults_values = [await self.visit(default, wrap_exceptions=True) for default in node.args.defaults]
        num_pos_defaults = len(pos_defaults_values)
        pos_defaults = dict(zip(pos_kw_params[-num_pos_defaults:], pos_defaults_values)) if num_pos_defaults else {}
        kw_defaults_values = [await self.visit(default, wrap_exceptions=True) if default else None for default in node.args.kw_defaults]
        kw_defaults = dict(zip(kwonly_params, kw_defaults_values))
        kw_defaults = {k: v for k, v in kw_defaults.items() if v is not None}

        func = AsyncFunction(node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults)
        for decorator in reversed(node.decorator_list):
            dec = await self.visit(decorator, wrap_exceptions=True)
            func = await dec(func)
        self.set_variable(node.name, func)

    async def visit_Call(self, node: ast.Call, is_await_context: bool = False, wrap_exceptions: bool = True) -> Any:
        func = await self.visit(node.func, wrap_exceptions=wrap_exceptions)

        # Evaluate arguments
        evaluated_args: List[Any] = []
        for arg in node.args:
            arg_value = await self.visit(arg, wrap_exceptions=wrap_exceptions)
            if isinstance(arg, ast.Starred):
                evaluated_args.extend(arg_value)
            else:
                evaluated_args.append(arg_value)

        kwargs: Dict[str, Any] = {}
        for kw in node.keywords:
            if kw.arg is None:
                unpacked_kwargs = await self.visit(kw.value, wrap_exceptions=wrap_exceptions)
                if not isinstance(unpacked_kwargs, dict):
                    raise TypeError(f"** argument must be a mapping, not {type(unpacked_kwargs).__name__}")
                kwargs.update(unpacked_kwargs)
            else:
                kwargs[kw.arg] = await self.visit(kw.value, wrap_exceptions=wrap_exceptions)

        # Special handling for str() on exceptions
        if func is str and len(evaluated_args) == 1 and isinstance(evaluated_args[0], BaseException):
            return str(evaluated_args[0])

        # Handle calls on super objects
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Call) and isinstance(node.func.value.func, ast.Name) and node.func.value.func.id == 'super':
            super_call = await self.visit(node.func.value, wrap_exceptions=wrap_exceptions)
            instance = self.current_instance  # Use stored class instance
            parent_class = super_call.__thisclass__
            method = getattr(parent_class, node.func.attr)
            return await self._execute_function(method, [instance] + evaluated_args, kwargs)

        # Handle list with async iterables
        if func is list and len(evaluated_args) == 1 and hasattr(evaluated_args[0], '__aiter__'):
            return [val async for val in evaluated_args[0]]

        # Handle built-in functions like range, list, etc.
        if func in (range, list, dict, set, tuple, frozenset):
            return func(*evaluated_args, **kwargs)

        # Special case for class instantiation and exceptions
        if inspect.isclass(func):
            instance = await self._create_class_instance(func, *evaluated_args, **kwargs)
            return instance

        # Handle super() with or without arguments
        if func is super:
            if len(evaluated_args) == 0:
                for frame in reversed(self.env_stack):
                    if '__current_method__' in frame:
                        method = frame['__current_method__']
                        if hasattr(method, 'defining_class') and 'self' in frame:
                            cls = method.defining_class
                            obj = frame['self']
                            result = super(cls, obj)
                            break
                else:
                    raise TypeError("super() without arguments requires a method context")
            elif len(evaluated_args) >= 2:
                cls, obj = evaluated_args[0], evaluated_args[1]
                result = super(cls, obj)
            else:
                raise TypeError("super() requires class and instance arguments")
            return result

        # Original logic for other function calls
        if isinstance(func, (staticmethod, classmethod, property)):
            if isinstance(func, property):
                result = func.fget(*evaluated_args, **kwargs)
            else:
                result = func(*evaluated_args, **kwargs)
        elif asyncio.iscoroutinefunction(func) or isinstance(func, AsyncFunction):
            result = func(*evaluated_args, **kwargs)
            if not is_await_context:
                result = await result
        elif isinstance(func, Function):
            if func.node.name == "__init__":
                await func(*evaluated_args, **kwargs)  # Special case for __init__: run but return None
                return None
            result = await func(*evaluated_args, **kwargs)
        else:
            result = func(*evaluated_args, **kwargs)
            if asyncio.iscoroutine(result) and not is_await_context:
                result = await result
        return result

    async def _create_class_instance(self, cls: Type, *args, **kwargs):
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

    async def _execute_function(self, func: Callable, args: list, kwargs: dict) -> Any:
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

    async def visit_Await(self, node: ast.Await, wrap_exceptions: bool = True) -> Any:
        coro = await self.visit(node.value, is_await_context=True, wrap_exceptions=wrap_exceptions)
        if not asyncio.iscoroutine(coro):
            raise TypeError(f"Cannot await non-coroutine object: {type(coro)}")
        
        try:
            # Set a 60-second timeout for any coroutine execution
            return await asyncio.wait_for(coro, timeout=60)
        except TimeoutError as e:
            line_info = f"line {node.lineno}" if hasattr(node, "lineno") else "unknown line"
            context_line = self.source_lines[node.lineno - 1] if self.source_lines and hasattr(node, "lineno") else "<unknown>"
            error_msg = f"Operation timed out after 60 seconds at {line_info}: {context_line.strip()}"
            logger_msg = f"Coroutine execution timed out: {error_msg}"
            
            # Use the logger initialized in __init__
            self.env_stack[0]["logger"].error(logger_msg)
            
            if wrap_exceptions:
                col = getattr(node, "col_offset", 0)
                raise WrappedException(error_msg, e, node.lineno if hasattr(node, "lineno") else 0, col, context_line)
            else:
                raise TimeoutError(error_msg) from e

    async def visit_Return(self, node: ast.Return, wrap_exceptions: bool = True) -> None:
        value: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions) if node.value is not None else None
        raise ReturnException(value)

    async def visit_Lambda(self, node: ast.Lambda, wrap_exceptions: bool = True) -> Any:
        closure: List[Dict[str, Any]] = self.env_stack[:]
        pos_kw_params = [arg.arg for arg in node.args.args]
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwonly_params = [arg.arg for arg in node.args.kwonlyargs]
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        pos_defaults_values = [await self.visit(default, wrap_exceptions=True) for default in node.args.defaults]
        num_pos_defaults = len(pos_defaults_values)
        pos_defaults = dict(zip(pos_kw_params[-num_pos_defaults:], pos_defaults_values)) if num_pos_defaults else {}
        kw_defaults_values = [await self.visit(default, wrap_exceptions=True) if default else None for default in node.args.kw_defaults]
        kw_defaults = dict(zip(kwonly_params, kw_defaults_values))
        kw_defaults = {k: v for k, v in kw_defaults.items() if v is not None}

        lambda_func = LambdaFunction(node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults)
        async def async_lambda(*args, **kwargs):
            return await lambda_func(*args, **kwargs)
        return async_lambda

    async def visit_List(self, node: ast.List, wrap_exceptions: bool = True) -> List[Any]:
        return [await self.visit(elt, wrap_exceptions=wrap_exceptions) for elt in node.elts]

    async def visit_Tuple(self, node: ast.Tuple, wrap_exceptions: bool = True) -> Tuple[Any, ...]:
        elements = [await self.visit(elt, wrap_exceptions=wrap_exceptions) for elt in node.elts]
        return tuple(elements)

    async def visit_Dict(self, node: ast.Dict, wrap_exceptions: bool = True) -> Dict[Any, Any]:
        return {
            await self.visit(k, wrap_exceptions=wrap_exceptions): await self.visit(v, wrap_exceptions=wrap_exceptions)
            for k, v in zip(node.keys, node.values)
        }

    async def visit_Set(self, node: ast.Set, wrap_exceptions: bool = True) -> set:
        elements = [await self.visit(elt, wrap_exceptions=wrap_exceptions) for elt in node.elts]
        return set(elements)

    async def visit_Attribute(self, node: ast.Attribute, wrap_exceptions: bool = True) -> Any:
        value = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
        attr = node.attr
        prop = getattr(type(value), attr, None)
        if isinstance(prop, property) and isinstance(prop.fget, Function):
            return await prop.fget(value)
        return getattr(value, attr)

    async def visit_Subscript(self, node: ast.Subscript, wrap_exceptions: bool = True) -> Any:
        value: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
        slice_val: Any = await self.visit(node.slice, wrap_exceptions=wrap_exceptions)
        return value[slice_val]

    async def visit_Slice(self, node: ast.Slice, wrap_exceptions: bool = True) -> slice:
        lower: Any = await self.visit(node.lower, wrap_exceptions=wrap_exceptions) if node.lower else None
        upper: Any = await self.visit(node.upper, wrap_exceptions=wrap_exceptions) if node.upper else None
        step: Any = await self.visit(node.step, wrap_exceptions=wrap_exceptions) if node.step else None
        return slice(lower, upper, step)

    async def visit_Index(self, node: ast.Index, wrap_exceptions: bool = True) -> Any:
        return await self.visit(node.value, wrap_exceptions=wrap_exceptions)

    async def visit_Starred(self, node: ast.Starred, wrap_exceptions: bool = True) -> Any:
        value = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
        if not isinstance(value, (list, tuple, set)):
            raise TypeError(f"Cannot unpack non-iterable object of type {type(value).__name__}")
        return value

    async def visit_Pass(self, node: ast.Pass, wrap_exceptions: bool = True) -> None:
        return None

    async def visit_TypeIgnore(self, node: ast.TypeIgnore, wrap_exceptions: bool = True) -> None:
        pass

    async def visit_Try(self, node: ast.Try, wrap_exceptions: bool = True) -> Any:
        result: Any = None
        try:
            for stmt in node.body:
                result = await self.visit(stmt, wrap_exceptions=False)
        except Exception as e:
            original_e = e.original_exception if isinstance(e, WrappedException) else e
            for handler in node.handlers:
                exc_type = await self._resolve_exception_type(handler.type)
                if exc_type and isinstance(original_e, exc_type):
                    if handler.name:
                        self.set_variable(handler.name, original_e)
                    for stmt in handler.body:
                        result = await self.visit(stmt, wrap_exceptions=True)
                    break  # Exit after handling
            else:
                raise  # Re-raise if not handled
        else:
            for stmt in node.orelse:
                result = await self.visit(stmt, wrap_exceptions=True)
        finally:
            for stmt in node.finalbody:
                await self.visit(stmt, wrap_exceptions=True)
        return result

    async def _resolve_exception_type(self, node: Optional[ast.AST]) -> Any:
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

    async def visit_TryStar(self, node: ast.TryStar, wrap_exceptions: bool = True) -> Any:
        result: Any = None
        exc_info: Optional[tuple] = None

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

    async def visit_Nonlocal(self, node: ast.Nonlocal, wrap_exceptions: bool = True) -> None:
        self.env_stack[-1].setdefault("__nonlocal_names__", set()).update(node.names)

    async def visit_JoinedStr(self, node: ast.JoinedStr, wrap_exceptions: bool = True) -> str:
        parts = []
        for value in node.values:
            val = await self.visit(value, wrap_exceptions=wrap_exceptions)
            if isinstance(value, ast.FormattedValue):
                parts.append(str(val))
            else:
                parts.append(val)
        return "".join(parts)

    async def visit_FormattedValue(self, node: ast.FormattedValue, wrap_exceptions: bool = True) -> Any:
        return await self.visit(node.value, wrap_exceptions=wrap_exceptions)

    async def visit_GeneratorExp(self, node: ast.GeneratorExp, wrap_exceptions: bool = True) -> Any:
        result = []
        base_frame: Dict[str, Any] = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)

        async def rec(gen_idx: int):
            if gen_idx == len(node.generators):
                result.append(await self.visit(node.elt, wrap_exceptions=True))
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
                    for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        await self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()

        await rec(0)
        self.env_stack.pop()
        return result

    async def visit_ClassDef(self, node: ast.ClassDef, wrap_exceptions: bool = True) -> Any:
        base_frame = {}
        self.env_stack.append(base_frame)
        bases = [await self.visit(base, wrap_exceptions=True) for base in node.bases]
        try:
            self.current_class = node
            for stmt in node.body:
                await self.visit(stmt, wrap_exceptions=True)
            class_dict = {k: v for k, v in self.env_stack[-1].items() if k not in ["__builtins__"]}
            cls = type(node.name, tuple(bases), class_dict)
            # Set defining_class for all Function instances in class_dict
            for name, value in class_dict.items():
                if isinstance(value, Function):
                    value.defining_class = cls
            self.env_stack[-2][node.name] = cls
            return cls
        finally:
            self.env_stack.pop()
            self.current_class = None

    async def visit_With(self, node: ast.With, wrap_exceptions: bool = True):
        for item in node.items:
            ctx = await self.visit(item.context_expr, wrap_exceptions=wrap_exceptions)
            val = ctx.__enter__()
            if item.optional_vars:
                await self.assign(item.optional_vars, val)
            try:
                for stmt in node.body:
                    try:
                        await self.visit(stmt, wrap_exceptions=wrap_exceptions)
                    except ReturnException as ret:
                        ctx.__exit__(None, None, None)
                        raise ret
            except ReturnException as ret:
                raise ret
            except Exception as e:
                if not ctx.__exit__(type(e), e, None):
                    raise
            else:
                ctx.__exit__(None, None, None)

    async def visit_Raise(self, node: ast.Raise, wrap_exceptions: bool = True) -> None:
        exc = await self.visit(node.exc, wrap_exceptions=wrap_exceptions) if node.exc else None
        if exc:
            raise exc
        raise Exception("Raise with no exception specified")

    async def visit_Global(self, node: ast.Global, wrap_exceptions: bool = True) -> None:
        self.env_stack[-1].setdefault("__global_names__", set()).update(node.names)

    async def visit_IfExp(self, node: ast.IfExp, wrap_exceptions: bool = True) -> Any:
        return await self.visit(node.body, wrap_exceptions=wrap_exceptions) if await self.visit(node.test, wrap_exceptions=wrap_exceptions) else await self.visit(node.orelse, wrap_exceptions=wrap_exceptions)

    async def visit_DictComp(self, node: ast.DictComp, wrap_exceptions: bool = True) -> Dict[Any, Any]:
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
                    for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        await self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()

        await rec(0)
        self.env_stack.pop()
        return result

    async def visit_SetComp(self, node: ast.SetComp, wrap_exceptions: bool = True) -> set:
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
                    for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        await self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause, wrap_exceptions=True) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()

        await rec(0)
        self.env_stack.pop()
        return result

    async def visit_Yield(self, node: ast.Yield, wrap_exceptions: bool = True) -> Any:
        value = await self.visit(node.value, wrap_exceptions=wrap_exceptions) if node.value else None
        return value

    async def visit_YieldFrom(self, node: ast.YieldFrom, wrap_exceptions: bool = True) -> Any:
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

    async def visit_Match(self, node: ast.Match, wrap_exceptions: bool = True) -> Any:
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

    async def _match_pattern(self, subject: Any, pattern: ast.AST) -> bool:
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

    async def visit_Delete(self, node: ast.Delete, wrap_exceptions: bool = True):
        for target in node.targets:
            if isinstance(target, ast.Name):
                del self.env_stack[-1][target.id]
            elif isinstance(target, ast.Subscript):
                obj = await self.visit(target.value, wrap_exceptions=wrap_exceptions)
                key = await self.visit(target.slice, wrap_exceptions=wrap_exceptions)
                del obj[key]
            else:
                raise Exception(f"Unsupported del target: {type(target).__name__}")

    async def visit_AsyncFor(self, node: ast.AsyncFor, wrap_exceptions: bool = True) -> None:
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

    async def execute_async(self, node: ast.Module) -> Any:
        return await self.visit(node)

    def new_scope(self):
        return Scope(self.env_stack)

class Scope:
    def __init__(self, env_stack):
        self.env_stack = env_stack

    def __enter__(self):
        self.env_stack.append({})

    def __exit__(self, exc_type, exc_value, traceback):
        self.env_stack.pop()

class Function:
    def __init__(self, node: ast.FunctionDef, closure: List[Dict[str, Any]], interpreter: ASTInterpreter,
                 pos_kw_params: List[str], vararg_name: Optional[str], kwonly_params: List[str],
                 kwarg_name: Optional[str], pos_defaults: Dict[str, Any], kw_defaults: Dict[str, Any]) -> None:
        self.node: ast.FunctionDef = node
        self.closure: List[Dict[str, Any]] = closure[:]
        self.interpreter: ASTInterpreter = interpreter
        self.pos_kw_params = pos_kw_params
        self.vararg_name = vararg_name
        self.kwonly_params = kwonly_params
        self.kwarg_name = kwarg_name
        self.pos_defaults = pos_defaults
        self.kw_defaults = kw_defaults
        self.defining_class = None  # Added for class inheritance support
        self.is_generator = any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(node))

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        new_env_stack: List[Dict[str, Any]] = self.closure[:]
        local_frame: Dict[str, Any] = {}
        local_frame[self.node.name] = self

        num_pos = len(self.pos_kw_params)
        for i, arg in enumerate(args):
            if i < num_pos:
                local_frame[self.pos_kw_params[i]] = arg
            elif self.vararg_name:
                if self.vararg_name not in local_frame:
                    local_frame[self.vararg_name] = []
                local_frame[self.vararg_name].append(arg)
            else:
                raise TypeError(f"Function '{self.node.name}' takes {num_pos} positional arguments but {len(args)} were given")
        if self.vararg_name and self.vararg_name not in local_frame:
            local_frame[self.vararg_name] = tuple()

        for kwarg_name, kwarg_value in kwargs.items():
            if kwarg_name in self.pos_kw_params or kwarg_name in self.kwonly_params:
                if kwarg_name in local_frame:
                    raise TypeError(f"Function '{self.node.name}' got multiple values for argument '{kwarg_name}'")
                local_frame[kwarg_name] = kwarg_value
            elif self.kwarg_name:
                if self.kwarg_name not in local_frame:
                    local_frame[self.kwarg_name] = {}
                local_frame[self.kwarg_name][kwarg_name] = kwarg_value
            else:
                raise TypeError(f"Function '{self.node.name}' got an unexpected keyword argument '{kwarg_name}'")

        for param in self.pos_kw_params:
            if param not in local_frame and param in self.pos_defaults:
                local_frame[param] = self.pos_defaults[param]
        for param in self.kwonly_params:
            if param not in local_frame and param in self.kw_defaults:
                local_frame[param] = self.kw_defaults[param]

        if self.kwarg_name and self.kwarg_name in local_frame:
            local_frame[self.kwarg_name] = dict(local_frame[self.kwarg_name])

        missing_args = [param for param in self.pos_kw_params if param not in local_frame and param not in self.pos_defaults]
        missing_args += [param for param in self.kwonly_params if param not in local_frame and param not in self.kw_defaults]
        if missing_args:
            raise TypeError(f"Function '{self.node.name}' missing required arguments: {', '.join(missing_args)}")

        # Bind 'self' explicitly and ensure state persists
        if self.pos_kw_params and self.pos_kw_params[0] == 'self' and args:
            local_frame['self'] = args[0]
            local_frame['__current_method__'] = self

        new_env_stack.append(local_frame)
        new_interp: ASTInterpreter = self.interpreter.spawn_from_env(new_env_stack)

        if self.is_generator:
            async def generator():
                for body_stmt in self.node.body:
                    if isinstance(body_stmt, ast.For):
                        iter_obj = await new_interp.visit(body_stmt.iter, wrap_exceptions=True)
                        for item in iter_obj:
                            new_frame = new_interp.env_stack[-1].copy()
                            new_interp.env_stack.append(new_frame)
                            await new_interp.assign(body_stmt.target, item)
                            try:
                                for inner_stmt in body_stmt.body:
                                    if isinstance(inner_stmt, ast.Expr) and isinstance(inner_stmt.value, ast.YieldFrom):
                                        sub_iterable = await new_interp.visit(inner_stmt.value, wrap_exceptions=True)
                                        if hasattr(sub_iterable, '__aiter__'):
                                            async for v in sub_iterable:
                                                yield v
                                        else:
                                            for v in sub_iterable:
                                                yield v
                                    elif isinstance(inner_stmt, ast.Expr) and isinstance(inner_stmt.value, ast.Yield):
                                        value = await new_interp.visit(inner_stmt.value, wrap_exceptions=True)
                                        yield value
                                    else:
                                        await new_interp.visit(inner_stmt, wrap_exceptions=True)
                            except BreakException:
                                new_interp.env_stack.pop()
                                break
                            except ContinueException:
                                new_interp.env_stack.pop()
                                continue
                            new_interp.env_stack.pop()
                    elif isinstance(body_stmt, ast.Expr) and isinstance(body_stmt.value, (ast.Yield, ast.YieldFrom)):
                        value = await new_interp.visit(body_stmt.value, wrap_exceptions=True)
                        if hasattr(value, '__aiter__'):
                            async for v in value:
                                yield v
                        elif hasattr(value, '__iter__'):
                            for v in value:
                                yield v
                        else:
                            yield value
                    else:
                        await new_interp.visit(body_stmt, wrap_exceptions=True)
            return generator()
        else:
            try:
                for stmt in self.node.body[:-1]:
                    await new_interp.visit(stmt, wrap_exceptions=True)
                return await new_interp.visit(self.node.body[-1], wrap_exceptions=True)
            except ReturnException as ret:
                return ret.value
            return None

    def __get__(self, instance: Any, owner: Any):
        if instance is None:
            return self
        async def method(*args: Any, **kwargs: Any) -> Any:
            return await self(instance, *args, **kwargs)
        method.__self__ = instance  # Explicitly bind instance to method
        return method

class AsyncFunction:
    def __init__(self, node: ast.AsyncFunctionDef, closure: List[Dict[str, Any]], interpreter: ASTInterpreter,
                 pos_kw_params: List[str], vararg_name: Optional[str], kwonly_params: List[str],
                 kwarg_name: Optional[str], pos_defaults: Dict[str, Any], kw_defaults: Dict[str, Any]) -> None:
        self.node: ast.AsyncFunctionDef = node
        self.closure: List[Dict[str, Any]] = closure[:]
        self.interpreter: ASTInterpreter = interpreter
        self.pos_kw_params = pos_kw_params
        self.vararg_name = vararg_name
        self.kwonly_params = kwonly_params
        self.kwarg_name = kwarg_name
        self.pos_defaults = pos_defaults
        self.kw_defaults = kw_defaults

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        new_env_stack: List[Dict[str, Any]] = self.closure[:]
        local_frame: Dict[str, Any] = {}
        local_frame[self.node.name] = self

        num_pos = len(self.pos_kw_params)
        for i, arg in enumerate(args):
            if i < num_pos:
                local_frame[self.pos_kw_params[i]] = arg
            elif self.vararg_name:
                if self.vararg_name not in local_frame:
                    local_frame[self.vararg_name] = []
                local_frame[self.vararg_name].append(arg)
            else:
                raise TypeError(f"Async function '{self.node.name}' takes {num_pos} positional arguments but {len(args)} were given")
        if self.vararg_name and self.vararg_name not in local_frame:
            local_frame[self.vararg_name] = tuple()

        for kwarg_name, kwarg_value in kwargs.items():
            if kwarg_name in self.pos_kw_params or kwarg_name in self.kwonly_params:
                if kwarg_name in local_frame:
                    raise TypeError(f"Async function '{self.node.name}' got multiple values for argument '{kwarg_name}'")
                local_frame[kwarg_name] = kwarg_value
            elif self.kwarg_name:
                if self.kwarg_name not in local_frame:
                    local_frame[self.kwarg_name] = {}
                local_frame[self.kwarg_name][kwarg_name] = kwarg_value
            else:
                raise TypeError(f"Async function '{self.node.name}' got an unexpected keyword argument '{kwarg_name}'")

        for param in self.pos_kw_params:
            if param not in local_frame and param in self.pos_defaults:
                local_frame[param] = self.pos_defaults[param]
        for param in self.kwonly_params:
            if param not in local_frame and param in self.kw_defaults:
                local_frame[param] = self.kw_defaults[param]

        missing_args = [param for param in self.pos_kw_params if param not in local_frame and param not in self.pos_defaults]
        missing_args += [param for param in self.kwonly_params if param not in local_frame and param not in self.kw_defaults]
        if missing_args:
            raise TypeError(f"Async function '{self.node.name}' missing required arguments: {', '.join(missing_args)}")

        new_env_stack.append(local_frame)
        new_interp: ASTInterpreter = self.interpreter.spawn_from_env(new_env_stack)
        last_value = None
        try:
            for stmt in self.node.body:
                last_value = await new_interp.visit(stmt, wrap_exceptions=True)
            return last_value
        except ReturnException as ret:
            return ret.value

class LambdaFunction:
    def __init__(self, node: ast.Lambda, closure: List[Dict[str, Any]], interpreter: ASTInterpreter,
                 pos_kw_params: List[str], vararg_name: Optional[str], kwonly_params: List[str],
                 kwarg_name: Optional[str], pos_defaults: Dict[str, Any], kw_defaults: Dict[str, Any]) -> None:
        self.node: ast.Lambda = node
        self.closure: List[Dict[str, Any]] = closure[:]
        self.interpreter: ASTInterpreter = interpreter
        self.pos_kw_params = pos_kw_params
        self.vararg_name = vararg_name
        self.kwonly_params = kwonly_params
        self.kwarg_name = kwarg_name
        self.pos_defaults = pos_defaults
        self.kw_defaults = kw_defaults

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        new_env_stack: List[Dict[str, Any]] = self.closure[:]
        local_frame: Dict[str, Any] = {}

        num_pos = len(self.pos_kw_params)
        for i, arg in enumerate(args):
            if i < num_pos:
                local_frame[self.pos_kw_params[i]] = arg
            elif self.vararg_name:
                if self.vararg_name not in local_frame:
                    local_frame[self.vararg_name] = []
                local_frame[self.vararg_name].append(arg)
            else:
                raise TypeError(f"Lambda takes {num_pos} positional arguments but {len(args)} were given")
        if self.vararg_name and self.vararg_name not in local_frame:
            local_frame[self.vararg_name] = tuple()

        for kwarg_name, kwarg_value in kwargs.items():
            if kwarg_name in self.pos_kw_params or kwarg_name in self.kwonly_params:
                if kwarg_name in local_frame:
                    raise TypeError(f"Lambda got multiple values for argument '{kwarg_name}'")
                local_frame[kwarg_name] = kwarg_value
            elif self.kwarg_name:
                if self.kwarg_name not in local_frame:
                    local_frame[self.kwarg_name] = {}
                local_frame[self.kwarg_name][kwarg_name] = kwarg_value
            else:
                raise TypeError(f"Lambda got an unexpected keyword argument '{kwarg_name}'")

        for param in self.pos_kw_params:
            if param not in local_frame and param in self.pos_defaults:
                local_frame[param] = self.pos_defaults[param]
        for param in self.kwonly_params:
            if param not in local_frame and param in self.kw_defaults:
                local_frame[param] = self.kw_defaults[param]

        missing_args = [param for param in self.pos_kw_params if param not in local_frame and param not in self.pos_defaults]
        missing_args += [param for param in self.kwonly_params if param not in local_frame and param not in self.kw_defaults]
        if missing_args:
            raise TypeError(f"Lambda missing required arguments: {', '.join(missing_args)}")

        new_env_stack.append(local_frame)
        new_interp: ASTInterpreter = self.interpreter.spawn_from_env(new_env_stack)
        return await new_interp.visit(self.node.body, wrap_exceptions=True)

async def execute_async(
    code: str,
    entry_point: Optional[str] = None,
    args: Optional[Tuple] = None,
    kwargs: Optional[Dict[str, Any]] = None,
    timeout: float = 30,
    allowed_modules: List[str] = ['asyncio'],
    namespace: Optional[Dict[str, Any]] = None
) -> AsyncExecutionResult:
    start_time = time.time()
    try:
        # Parse the code into an AST
        ast_tree = ast.parse(textwrap.dedent(code))
        
        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Create the interpreter with the namespace
        interpreter = ASTInterpreter(
            allowed_modules=allowed_modules,
            restrict_os=True,
            namespace=namespace
        )
        
        # Set the interpreter's loop to be the same as our current loop
        interpreter.loop = loop
        
        # Define the execution function that runs in the same loop context
        async def run_execution():
            return await interpreter.execute_async(ast_tree)
        
        # Execute the module with timeout
        module_result = await asyncio.wait_for(run_execution(), timeout=timeout)
        
        # If an entry_point is specified, execute that function
        if entry_point:
            func = interpreter.env_stack[0].get(entry_point)
            if not func:
                raise NameError(f"Function '{entry_point}' not found in the code")
            args = args or ()
            kwargs = kwargs or {}
            if isinstance(func, AsyncFunction) or asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            elif isinstance(func, Function):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
        else:
            result = module_result
        
        return AsyncExecutionResult(
            result=result,
            error=None,
            execution_time=time.time() - start_time
        )
    except asyncio.TimeoutError as e:
        return AsyncExecutionResult(
            result=None,
            error=f'{type(e).__name__}: {str(e)}',
            execution_time=time.time() - start_time
        )
    except WrappedException as e:
        return AsyncExecutionResult(
            result=None,
            error=str(e),
            execution_time=time.time() - start_time
        )
    except Exception as e:
        error_type = type(getattr(e, 'original_exception', e)).__name__
        return AsyncExecutionResult(
            result=None,
            error=f'{error_type}: {str(e)}',
            execution_time=time.time() - start_time
        )

def interpret_ast(ast_tree: Any, allowed_modules: List[str], source: str = "", restrict_os: bool = False, namespace: Optional[Dict[str, Any]] = None) -> Any:
    interpreter = ASTInterpreter(allowed_modules=allowed_modules, source=source, restrict_os=restrict_os, namespace=namespace)

    async def run_interpreter():
        result = await interpreter.visit(ast_tree, wrap_exceptions=True)
        if asyncio.iscoroutine(result):
            return await result
        elif hasattr(result, '__aiter__'):
            return [val async for val in result]
        return result

    # Use the current event loop if one is running, otherwise create a new one
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # No running event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        interpreter.loop = loop
        try:
            return loop.run_until_complete(run_interpreter())
        finally:
            loop.close()
    else:
        interpreter.loop = loop
        return asyncio.run_coroutine_threadsafe(run_interpreter(), loop).result()

def interpret_code(source_code: str, allowed_modules: List[str], restrict_os: bool = False, namespace: Optional[Dict[str, Any]] = None) -> Any:
    dedented_source = textwrap.dedent(source_code).strip()
    tree: ast.AST = ast.parse(dedented_source)
    return interpret_ast(tree, allowed_modules, source=dedented_source, restrict_os=restrict_os, namespace=namespace)

if __name__ == "__main__":
    print("Script is running!")

    source_code_1: str = """
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("Decorated!")
        return func(*args, **kwargs)
    return wrapper

@my_decorator
def example(a, b=2, *args, c=3, **kwargs):
    return a + b + c + sum(args) + sum(kwargs.values())

result = example(1, 4, 5, 6, c=7, x=8)
"""
    print("Example 1 (function with decorator, defaults, *args, **kwargs):")
    try:
        result_1: Any = interpret_code(source_code_1, allowed_modules=[], restrict_os=True)
        print("Result:", result_1)
    except Exception as e:
        print("Interpreter error:", e)

    source_code_2: str = """
import asyncio

async def delay_square(x, delay=1):
    await asyncio.sleep(delay)
    return x * x

result = await delay_square(5)
"""
    print("Example 2 (async function):")
    try:
        result_2: Any = interpret_code(source_code_2, allowed_modules=["asyncio"], restrict_os=True)
        print("Result:", result_2)
    except Exception as e:
        print("Interpreter error:", e)

    source_code_3: str = """
import os
result = os.path.join("a", "b")
"""
    print("Example 3 (attempt to use os module with restrict_os=True):")
    try:
        result_3: Any = interpret_code(source_code_3, allowed_modules=["os"], restrict_os=True)
        print("Result:", result_3)
    except Exception as e:
        print("Interpreter error:", e)

    source_code_4: str = """
with open("test.txt", "r") as f:
    result = f.read()
"""
    print("Example 4 (attempt to use open() with restrict_os=True):")
    try:
        result_4: Any = interpret_code(source_code_4, allowed_modules=[], restrict_os=True)
        print("Result:", result_4)
    except Exception as e:
        print("Interpreter error:", e)

    source_code_5: str = """
def add(a, b):
    return a + b

async def async_multiply(x, y):
    await asyncio.sleep(0.1)
    return x * y
"""
    print("Example 5 (execute_async with entry_point):")
    async def run_example_5():
        result_5a = await execute_async(source_code_5, entry_point="add", args=(3, 4))
        print("Result (add):", result_5a.result)
        result_5b = await execute_async(source_code_5, entry_point="async_multiply", args=(2, 3), allowed_modules=["asyncio"])
        print("Result (async_multiply):", result_5b.result)
    asyncio.run(run_example_5())