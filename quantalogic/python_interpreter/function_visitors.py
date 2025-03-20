import ast
import asyncio
import inspect
from typing import Any, Dict, List

from .exceptions import WrappedException
from .function_utils import AsyncFunction, Function, LambdaFunction, AsyncGeneratorFunction
from .interpreter_core import ASTInterpreter

async def visit_FunctionDef(self: ASTInterpreter, node: ast.FunctionDef, wrap_exceptions: bool = True) -> None:
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
        if asyncio.iscoroutine(dec):
            dec = await dec
        if dec in (staticmethod, classmethod, property):
            decorated_func = dec(func)
        else:
            decorated_func = await self._execute_function(dec, [decorated_func], {})
    self.set_variable(node.name, decorated_func)

async def visit_AsyncFunctionDef(self: ASTInterpreter, node: ast.AsyncFunctionDef, wrap_exceptions: bool = True) -> None:
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
        if asyncio.iscoroutine(dec):
            dec = await dec
        func = await self._execute_function(dec, [func], {})
    self.set_variable(node.name, func)

async def visit_AsyncGeneratorDef(self: ASTInterpreter, node: ast.AsyncFunctionDef, wrap_exceptions: bool = True) -> None:
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

    func = AsyncGeneratorFunction(node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults)
    for decorator in reversed(node.decorator_list):
        dec = await self.visit(decorator, wrap_exceptions=True)
        if asyncio.iscoroutine(dec):
            dec = await dec
        func = await self._execute_function(dec, [func], {})
    self.set_variable(node.name, func)

async def visit_Call(self: ASTInterpreter, node: ast.Call, is_await_context: bool = False, wrap_exceptions: bool = True) -> Any:
    func = await self.visit(node.func, wrap_exceptions=wrap_exceptions)

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

    # Handle str() explicitly to avoid __new__ restriction
    if func is str:
        if len(evaluated_args) != 1:
            raise TypeError(f"str() takes exactly one argument ({len(evaluated_args)} given)")
        arg = evaluated_args[0]
        return f"{arg}"  # Use f-string to safely convert to string

    # Handle exceptions passed to str() (original behavior preserved)
    if func is str and len(evaluated_args) == 1 and isinstance(evaluated_args[0], BaseException):
        exc = evaluated_args[0]
        if isinstance(exc, WrappedException) and hasattr(exc, 'original_exception'):
            inner_exc = exc.original_exception
            return inner_exc.args[0] if inner_exc.args else str(inner_exc)
        return exc.args[0] if exc.args else str(exc)

    if func is super:
        if len(evaluated_args) == 0:
            if not (self.current_class and self.current_instance):
                # Infer from call stack if possible
                for frame in reversed(self.env_stack):
                    if 'self' in frame and '__current_method__' in frame:
                        self.current_instance = frame['self']
                        self.current_class = frame['self'].__class__
                        break
                if not (self.current_class and self.current_instance):
                    raise TypeError("super() without arguments requires a class instantiation context")
            result = super(self.current_class, self.current_instance)
        elif len(evaluated_args) >= 2:
            cls, obj = evaluated_args[0], evaluated_args[1]
            result = super(cls, obj)
        else:
            raise TypeError("super() requires class and instance arguments")
        return result

    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Call) and isinstance(node.func.value.func, ast.Name) and node.func.value.func.id == 'super':
        super_call = await self.visit(node.func.value, wrap_exceptions=wrap_exceptions)
        method = getattr(super_call, node.func.attr)
        return await self._execute_function(method, evaluated_args, kwargs)

    if func is list and len(evaluated_args) == 1 and hasattr(evaluated_args[0], '__aiter__'):
        return [val async for val in evaluated_args[0]]

    if func in (range, list, dict, set, tuple, frozenset):
        return func(*evaluated_args, **kwargs)

    if inspect.isclass(func):
        instance = await self._create_class_instance(func, *evaluated_args, **kwargs)
        return instance

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
            await func(*evaluated_args, **kwargs)
            return None
        result = await func(*evaluated_args, **kwargs)
    elif isinstance(func, AsyncGeneratorFunction):
        return func(*evaluated_args, **kwargs)
    else:
        result = func(*evaluated_args, **kwargs)
        if asyncio.iscoroutine(result) and not is_await_context:
            result = await result
    return result

async def visit_Await(self: ASTInterpreter, node: ast.Await, wrap_exceptions: bool = True) -> Any:
    coro = await self.visit(node.value, is_await_context=True, wrap_exceptions=wrap_exceptions)
    if not asyncio.iscoroutine(coro):
        raise TypeError(f"Cannot await non-coroutine object: {type(coro)}")
    
    try:
        return await asyncio.wait_for(coro, timeout=60)
    except asyncio.TimeoutError as e:
        line_info = f"line {node.lineno}" if hasattr(node, "lineno") else "unknown line"
        context_line = self.source_lines[node.lineno - 1] if self.source_lines and hasattr(node, "lineno") else "<unknown>"
        error_msg = f"Operation timed out after 60 seconds at {line_info}: {context_line.strip()}"
        logger_msg = f"Coroutine execution timed out: {error_msg}"
        self.env_stack[0]["logger"].error(logger_msg)
        
        if wrap_exceptions:
            col = getattr(node, "col_offset", 0)
            raise WrappedException(error_msg, e, node.lineno if hasattr(node, "lineno") else 0, col, context_line)
        else:
            raise asyncio.TimeoutError(error_msg) from e

async def visit_Lambda(self: ASTInterpreter, node: ast.Lambda, wrap_exceptions: bool = True) -> Any:
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

    lambda_func = LambdaFunction(
        node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults
    )
    
    async def lambda_wrapper(*args, **kwargs):
        return await lambda_func(*args, **kwargs)
    
    return lambda_wrapper