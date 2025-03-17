import ast
import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from .exceptions import BreakException, ContinueException, ReturnException, WrappedException
from .function_utils import AsyncFunction, Function, LambdaFunction
from .interpreter_core import ASTInterpreter

# Explicitly define __all__ with all visitor methods
__all__ = [
    "visit_Import", "visit_ImportFrom", "visit_ListComp", "visit_Module", "visit_Expr",
    "visit_Constant", "visit_Name", "visit_BinOp", "visit_UnaryOp", "visit_Assign",
    "visit_AugAssign", "visit_AnnAssign", "visit_Compare", "visit_BoolOp", "visit_If",
    "visit_While", "visit_For", "visit_Break", "visit_Continue", "visit_FunctionDef",
    "visit_AsyncFunctionDef", "visit_Call", "visit_Await", "visit_Return", "visit_Lambda",
    "visit_List", "visit_Tuple", "visit_Dict", "visit_Set", "visit_Attribute",
    "visit_Subscript", "visit_Slice", "visit_Index", "visit_Starred", "visit_Pass",
    "visit_TypeIgnore", "visit_Try", "visit_TryStar", "visit_Nonlocal", "visit_JoinedStr",
    "visit_FormattedValue", "visit_GeneratorExp", "visit_ClassDef", "visit_With",
    "visit_AsyncWith", "visit_Raise", "visit_Global", "visit_IfExp", "visit_DictComp",
    "visit_SetComp", "visit_Yield", "visit_YieldFrom", "visit_Match", "visit_Delete",
    "visit_AsyncFor", "visit_Assert", "visit_NamedExpr"
]

async def visit_Import(self: ASTInterpreter, node: ast.Import, wrap_exceptions: bool = True) -> None:
    for alias in node.names:
        module_name: str = alias.name
        asname: str = alias.asname if alias.asname is not None else module_name
        if module_name not in self.allowed_modules:
            raise Exception(
                f"Import Error: Module '{module_name}' is not allowed. Only {self.allowed_modules} are permitted."
            )
        self.set_variable(asname, self.modules[module_name])

async def visit_ImportFrom(self: ASTInterpreter, node: ast.ImportFrom, wrap_exceptions: bool = True) -> None:
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

async def visit_ListComp(self: ASTInterpreter, node: ast.ListComp, wrap_exceptions: bool = True) -> List[Any]:
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

async def visit_Module(self: ASTInterpreter, node: ast.Module, wrap_exceptions: bool = True) -> Any:
    last_value = None
    for stmt in node.body:
        last_value = await self.visit(stmt, wrap_exceptions=True)
    return last_value

async def visit_Expr(self: ASTInterpreter, node: ast.Expr, wrap_exceptions: bool = True) -> Any:
    return await self.visit(node.value, wrap_exceptions=wrap_exceptions)

async def visit_Constant(self: ASTInterpreter, node: ast.Constant, wrap_exceptions: bool = True) -> Any:
    return node.value

async def visit_Name(self: ASTInterpreter, node: ast.Name, wrap_exceptions: bool = True) -> Any:
    if isinstance(node.ctx, ast.Load):
        return self.get_variable(node.id)
    elif isinstance(node.ctx, ast.Store):
        return node.id
    else:
        raise Exception("Unsupported context for Name")

async def visit_BinOp(self: ASTInterpreter, node: ast.BinOp, wrap_exceptions: bool = True) -> Any:
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

async def visit_UnaryOp(self: ASTInterpreter, node: ast.UnaryOp, wrap_exceptions: bool = True) -> Any:
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

async def visit_Assign(self: ASTInterpreter, node: ast.Assign, wrap_exceptions: bool = True) -> None:
    value: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    for target in node.targets:
        if isinstance(target, ast.Subscript):
            obj = await self.visit(target.value, wrap_exceptions=wrap_exceptions)
            key = await self.visit(target.slice, wrap_exceptions=wrap_exceptions)
            obj[key] = value
        else:
            await self.assign(target, value)

async def visit_AugAssign(self: ASTInterpreter, node: ast.AugAssign, wrap_exceptions: bool = True) -> Any:
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

async def visit_AnnAssign(self: ASTInterpreter, node: ast.AnnAssign, wrap_exceptions: bool = True) -> None:
    # Evaluate the value if provided
    value = await self.visit(node.value, wrap_exceptions=wrap_exceptions) if node.value else None
    # Assign the value to the target (annotation is ignored for execution)
    if value is not None or node.simple:
        await self.assign(node.target, value)
    # Note: Annotation (node.annotation) is not processed, as this interpreter doesn't use type info

async def visit_Compare(self: ASTInterpreter, node: ast.Compare, wrap_exceptions: bool = True) -> bool:
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

async def visit_BoolOp(self: ASTInterpreter, node: ast.BoolOp, wrap_exceptions: bool = True) -> bool:
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

async def visit_Break(self: ASTInterpreter, node: ast.Break, wrap_exceptions: bool = True) -> None:
    raise BreakException()

async def visit_Continue(self: ASTInterpreter, node: ast.Continue, wrap_exceptions: bool = True) -> None:
    raise ContinueException()

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
        if dec in (staticmethod, classmethod, property):
            decorated_func = dec(func)
        else:
            decorated_func = await dec(decorated_func)
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
        func = await dec(func)
    self.set_variable(node.name, func)

async def visit_Call(self: ASTInterpreter, node: ast.Call, is_await_context: bool = False, wrap_exceptions: bool = True) -> Any:
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

async def _create_class_instance(self: ASTInterpreter, cls: Type, *args, **kwargs):
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

async def _execute_function(self: ASTInterpreter, func: Callable, args: list, kwargs: dict) -> Any:
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

async def visit_Await(self: ASTInterpreter, node: ast.Await, wrap_exceptions: bool = True) -> Any:
    coro = await self.visit(node.value, is_await_context=True, wrap_exceptions=wrap_exceptions)
    if not asyncio.iscoroutine(coro):
        raise TypeError(f"Cannot await non-coroutine object: {type(coro)}")
    
    try:
        # Set a 60-second timeout for any coroutine execution
        return await asyncio.wait_for(coro, timeout=60)
    except asyncio.TimeoutError as e:
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
            raise asyncio.TimeoutError(error_msg) from e

async def visit_Return(self: ASTInterpreter, node: ast.Return, wrap_exceptions: bool = True) -> None:
    value: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions) if node.value is not None else None
    raise ReturnException(value)

async def visit_Lambda(self: ASTInterpreter, node: ast.Lambda, wrap_exceptions: bool = True) -> Any:
    """
    Visit a Lambda node and return a callable that executes the lambda body asynchronously.
    
    Args:
        node (ast.Lambda): The lambda expression AST node.
        wrap_exceptions (bool): Whether to wrap exceptions in WrappedException.
    
    Returns:
        Callable: An async callable representing the lambda function.
    """
    # Capture the current environment as a closure
    closure: List[Dict[str, Any]] = self.env_stack[:]
    
    # Extract lambda parameters
    pos_kw_params = [arg.arg for arg in node.args.args]
    vararg_name = node.args.vararg.arg if node.args.vararg else None
    kwonly_params = [arg.arg for arg in node.args.kwonlyargs]
    kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
    
    # Evaluate default values for positional and keyword-only parameters
    pos_defaults_values = [await self.visit(default, wrap_exceptions=True) for default in node.args.defaults]
    num_pos_defaults = len(pos_defaults_values)
    pos_defaults = dict(zip(pos_kw_params[-num_pos_defaults:], pos_defaults_values)) if num_pos_defaults else {}
    
    kw_defaults_values = [await self.visit(default, wrap_exceptions=True) if default else None for default in node.args.kw_defaults]
    kw_defaults = dict(zip(kwonly_params, kw_defaults_values))
    kw_defaults = {k: v for k, v in kw_defaults.items() if v is not None}
    
    # Create the LambdaFunction instance
    lambda_func = LambdaFunction(
        node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults
    )
    
    # Define the async wrapper for the lambda
    async def lambda_wrapper(*args, **kwargs):
        """
        Async wrapper to execute the lambda function.
        
        Args:
            *args: Positional arguments passed to the lambda.
            **kwargs: Keyword arguments passed to the lambda.
        
        Returns:
            Any: The result of the lambda execution.
        """
        return await lambda_func(*args, **kwargs)
    
    # Return the async wrapper
    return lambda_wrapper

async def visit_List(self: ASTInterpreter, node: ast.List, wrap_exceptions: bool = True) -> List[Any]:
    return [await self.visit(elt, wrap_exceptions=wrap_exceptions) for elt in node.elts]

async def visit_Tuple(self: ASTInterpreter, node: ast.Tuple, wrap_exceptions: bool = True) -> Tuple[Any, ...]:
    elements = [await self.visit(elt, wrap_exceptions=wrap_exceptions) for elt in node.elts]
    return tuple(elements)

async def visit_Dict(self: ASTInterpreter, node: ast.Dict, wrap_exceptions: bool = True) -> Dict[Any, Any]:
    return {
        await self.visit(k, wrap_exceptions=wrap_exceptions): await self.visit(v, wrap_exceptions=wrap_exceptions)
        for k, v in zip(node.keys, node.values)
    }

async def visit_Set(self: ASTInterpreter, node: ast.Set, wrap_exceptions: bool = True) -> set:
    elements = [await self.visit(elt, wrap_exceptions=wrap_exceptions) for elt in node.elts]
    return set(elements)

async def visit_Attribute(self: ASTInterpreter, node: ast.Attribute, wrap_exceptions: bool = True) -> Any:
    value = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    attr = node.attr
    prop = getattr(type(value), attr, None)
    if isinstance(prop, property) and isinstance(prop.fget, Function):
        return await prop.fget(value)
    return getattr(value, attr)

async def visit_Subscript(self: ASTInterpreter, node: ast.Subscript, wrap_exceptions: bool = True) -> Any:
    value: Any = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    slice_val: Any = await self.visit(node.slice, wrap_exceptions=wrap_exceptions)
    return value[slice_val]

async def visit_Slice(self: ASTInterpreter, node: ast.Slice, wrap_exceptions: bool = True) -> slice:
    lower: Any = await self.visit(node.lower, wrap_exceptions=wrap_exceptions) if node.lower else None
    upper: Any = await self.visit(node.upper, wrap_exceptions=wrap_exceptions) if node.upper else None
    step: Any = await self.visit(node.step, wrap_exceptions=wrap_exceptions) if node.step else None
    return slice(lower, upper, step)

async def visit_Index(self: ASTInterpreter, node: ast.Index, wrap_exceptions: bool = True) -> Any:
    return await self.visit(node.value, wrap_exceptions=wrap_exceptions)

async def visit_Starred(self: ASTInterpreter, node: ast.Starred, wrap_exceptions: bool = True) -> Any:
    value = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    if not isinstance(value, (list, tuple, set)):
        raise TypeError(f"Cannot unpack non-iterable object of type {type(value).__name__}")
    return value

async def visit_Pass(self: ASTInterpreter, node: ast.Pass, wrap_exceptions: bool = True) -> None:
    return None

async def visit_TypeIgnore(self: ASTInterpreter, node: ast.TypeIgnore, wrap_exceptions: bool = True) -> None:
    pass

async def visit_Try(self: ASTInterpreter, node: ast.Try, wrap_exceptions: bool = True) -> Any:
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

async def _resolve_exception_type(self: ASTInterpreter, node: Optional[ast.AST]) -> Any:
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

async def visit_TryStar(self: ASTInterpreter, node: ast.TryStar, wrap_exceptions: bool = True) -> Any:
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

async def visit_Nonlocal(self: ASTInterpreter, node: ast.Nonlocal, wrap_exceptions: bool = True) -> None:
    self.env_stack[-1].setdefault("__nonlocal_names__", set()).update(node.names)

async def visit_JoinedStr(self: ASTInterpreter, node: ast.JoinedStr, wrap_exceptions: bool = True) -> str:
    parts = []
    for value in node.values:
        val = await self.visit(value, wrap_exceptions=wrap_exceptions)
        if isinstance(value, ast.FormattedValue):
            parts.append(str(val))
        else:
            parts.append(val)
    return "".join(parts)

async def visit_FormattedValue(self: ASTInterpreter, node: ast.FormattedValue, wrap_exceptions: bool = True) -> Any:
    return await self.visit(node.value, wrap_exceptions=wrap_exceptions)

async def visit_GeneratorExp(self: ASTInterpreter, node: ast.GeneratorExp, wrap_exceptions: bool = True) -> Any:
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

async def visit_ClassDef(self: ASTInterpreter, node: ast.ClassDef, wrap_exceptions: bool = True) -> Any:
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

async def visit_With(self: ASTInterpreter, node: ast.With, wrap_exceptions: bool = True):
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

async def visit_Raise(self: ASTInterpreter, node: ast.Raise, wrap_exceptions: bool = True) -> None:
    exc = await self.visit(node.exc, wrap_exceptions=wrap_exceptions) if node.exc else None
    if exc:
        raise exc
    raise Exception("Raise with no exception specified")

async def visit_Global(self: ASTInterpreter, node: ast.Global, wrap_exceptions: bool = True) -> None:
    self.env_stack[-1].setdefault("__global_names__", set()).update(node.names)

async def visit_IfExp(self: ASTInterpreter, node: ast.IfExp, wrap_exceptions: bool = True) -> Any:
    return await self.visit(node.body, wrap_exceptions=wrap_exceptions) if await self.visit(node.test, wrap_exceptions=wrap_exceptions) else await self.visit(node.orelse, wrap_exceptions=wrap_exceptions)

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

async def visit_Yield(self: ASTInterpreter, node: ast.Yield, wrap_exceptions: bool = True) -> Any:
    value = await self.visit(node.value, wrap_exceptions=wrap_exceptions) if node.value else None
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

async def visit_Assert(self: ASTInterpreter, node: ast.Assert, wrap_exceptions: bool = True) -> None:
    test = await self.visit(node.test, wrap_exceptions=wrap_exceptions)
    if not test:
        msg = await self.visit(node.msg, wrap_exceptions=wrap_exceptions) if node.msg else "Assertion failed"
        raise AssertionError(msg)

async def visit_NamedExpr(self: ASTInterpreter, node: ast.NamedExpr, wrap_exceptions: bool = True) -> Any:
    value = await self.visit(node.value, wrap_exceptions=wrap_exceptions)
    await self.assign(node.target, value)
    return value