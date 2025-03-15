import ast
import builtins
import textwrap
from typing import Any, Dict, List, Optional, Tuple
import asyncio
from functools import wraps


class ReturnException(Exception):
    def __init__(self, value: Any) -> None:
        self.value: Any = value


class BreakException(Exception):
    pass


class ContinueException(Exception):
    pass


class ASTInterpreter:
    def __init__(
        self, allowed_modules: List[str], env_stack: Optional[List[Dict[str, Any]]] = None, source: Optional[str] = None
    ) -> None:
        self.allowed_modules: List[str] = allowed_modules
        self.modules: Dict[str, Any] = {mod: __import__(mod) for mod in allowed_modules}
        if env_stack is None:
            self.env_stack: List[Dict[str, Any]] = [{}]
            self.env_stack[0].update(self.modules)
            safe_builtins: Dict[str, Any] = dict(vars(builtins))
            safe_builtins["__import__"] = self.safe_import
            # Explicitly include exception types to ensure correct identity
            safe_builtins.update({
                "enumerate": enumerate, "zip": zip, "sum": sum, "min": min, "max": max,
                "abs": abs, "round": round, "str": str, "repr": repr, "id": id,
                "type": type, "isinstance": isinstance, "issubclass": issubclass,
                "Exception": Exception, "ZeroDivisionError": ZeroDivisionError,
                "ValueError": ValueError, "TypeError": TypeError,
            })
            if "set" not in safe_builtins:
                safe_builtins["set"] = set
            self.env_stack[0]["__builtins__"] = safe_builtins
            self.env_stack[0].update(safe_builtins)
        else:
            self.env_stack = env_stack
            if "__builtins__" not in self.env_stack[0]:
                safe_builtins: Dict[str, Any] = dict(vars(builtins))
                safe_builtins["__import__"] = self.safe_import
                safe_builtins.update({
                    "enumerate": enumerate, "zip": zip, "sum": sum, "min": min, "max": max,
                    "abs": abs, "round": round, "str": str, "repr": repr, "id": id,
                    "type": type, "isinstance": isinstance, "issubclass": issubclass,
                    "Exception": Exception, "ZeroDivisionError": ZeroDivisionError,
                    "ValueError": ValueError, "TypeError": TypeError,
                })
                if "set" not in safe_builtins:
                    safe_builtins["set"] = set
                self.env_stack[0]["__builtins__"] = safe_builtins
                self.env_stack[0].update(safe_builtins)

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

    def safe_import(
        self,
        name: str,
        globals: Optional[Dict[str, Any]] = None,
        locals: Optional[Dict[str, Any]] = None,
        fromlist: Tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name not in self.allowed_modules:
            raise ImportError(f"Import Error: Module '{name}' is not allowed. Only {self.allowed_modules} are permitted.")
        return self.modules[name]

    def spawn_from_env(self, env_stack: List[Dict[str, Any]]) -> "ASTInterpreter":
        new_interp = ASTInterpreter(
            self.allowed_modules, env_stack, source="\n".join(self.source_lines) if self.source_lines else None
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

    def assign(self, target: ast.AST, value: Any) -> None:
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
                    self.assign(t, v)
            else:
                total = len(value)
                before = target.elts[:star_index]
                after = target.elts[star_index + 1:]
                if len(before) + len(after) > total:
                    raise ValueError("Unpacking mismatch")
                for i, elt2 in enumerate(before):
                    self.assign(elt2, value[i])
                starred_count = total - len(before) - len(after)
                self.assign(target.elts[star_index].value, value[len(before):len(before) + starred_count])
                for j, elt2 in enumerate(after):
                    self.assign(elt2, value[len(before) + starred_count + j])
        elif isinstance(target, ast.Attribute):
            obj = asyncio.run_coroutine_threadsafe(self.visit(target.value), self.loop).result()
            setattr(obj, target.attr, value)
        elif isinstance(target, ast.Subscript):
            obj = asyncio.run_coroutine_threadsafe(self.visit(target.value), self.loop).result()
            key = asyncio.run_coroutine_threadsafe(self.visit(target.slice), self.loop).result()
            obj[key] = value
        else:
            raise Exception("Unsupported assignment target type: " + str(type(target)))

    async def visit(self, node: ast.AST, is_await_context: bool = False) -> Any:
        method_name: str = "visit_" + node.__class__.__name__
        method = getattr(self, method_name, self.generic_visit)
        try:
            if method_name == "visit_Call":
                result = await method(node, is_await_context)
            else:
                result = await method(node)
            return result
        except (ReturnException, BreakException, ContinueException):
            raise
        except Exception as e:
            lineno = getattr(node, "lineno", None)
            col = getattr(node, "col_offset", None)
            lineno = lineno if lineno is not None else 1
            col = col if col is not None else 0
            context_line = ""
            if self.source_lines and 1 <= lineno <= len(self.source_lines):
                context_line = self.source_lines[lineno - 1]
            raise Exception(f"Error line {lineno}, col {col}:\n{context_line}\nDescription: {str(e)}") from e

    async def generic_visit(self, node: ast.AST) -> Any:
        lineno = getattr(node, "lineno", None)
        context_line = ""
        if self.source_lines and lineno is not None and 1 <= lineno <= len(self.source_lines):
            context_line = self.source_lines[lineno - 1]
        raise Exception(
            f"Unsupported AST node type: {node.__class__.__name__} at line {lineno}.\nContext: {context_line}"
        )

    async def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module_name: str = alias.name
            asname: str = alias.asname if alias.asname is not None else module_name
            if module_name not in self.allowed_modules:
                raise Exception(
                    f"Import Error: Module '{module_name}' is not allowed. Only {self.allowed_modules} are permitted."
                )
            self.set_variable(asname, self.modules[module_name])

    async def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
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

    async def visit_ListComp(self, node: ast.ListComp) -> List[Any]:
        result: List[Any] = []
        base_frame: Dict[str, Any] = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)

        async def rec(gen_idx: int) -> None:
            if gen_idx == len(node.generators):
                result.append(await self.visit(node.elt))
            else:
                comp = node.generators[gen_idx]
                iterable = await self.visit(comp.iter)
                if hasattr(iterable, '__aiter__'):
                    async for item in iterable:
                        new_frame: Dict[str, Any] = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()
                else:
                    for item in iterable:
                        new_frame: Dict[str, Any] = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()

        await rec(0)
        self.env_stack.pop()
        return result

    async def visit_Module(self, node: ast.Module) -> Any:
        last_value = None
        for stmt in node.body:
            last_value = await self.visit(stmt)
        return self.env_stack[0].get("result", last_value)

    async def visit_Expr(self, node: ast.Expr) -> Any:
        return await self.visit(node.value)

    async def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    async def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Load):
            return self.get_variable(node.id)
        elif isinstance(node.ctx, ast.Store):
            return node.id
        else:
            raise Exception("Unsupported context for Name")

    async def visit_BinOp(self, node: ast.BinOp) -> Any:
        left: Any = await self.visit(node.left)
        right: Any = await self.visit(node.right)
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

    async def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand: Any = await self.visit(node.operand)
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

    async def visit_Assign(self, node: ast.Assign) -> None:
        value: Any = await self.visit(node.value)
        for target in node.targets:
            if isinstance(target, ast.Subscript):
                obj = await self.visit(target.value)
                key = await self.visit(target.slice)
                obj[key] = value
            else:
                self.assign(target, value)

    async def visit_AugAssign(self, node: ast.AugAssign) -> Any:
        if isinstance(node.target, ast.Name):
            current_val: Any = self.get_variable(node.target.id)
        else:
            current_val: Any = await self.visit(node.target)
        right_val: Any = await self.visit(node.value)
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
        self.assign(node.target, result)
        return result

    async def visit_Compare(self, node: ast.Compare) -> bool:
        left: Any = await self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right: Any = await self.visit(comparator)
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

    async def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not await self.visit(value):
                    return False
            return True
        elif isinstance(node.op, ast.Or):
            for value in node.values:
                if await self.visit(value):
                    return True
            return False
        else:
            raise Exception("Unsupported boolean operator: " + str(node.op))

    async def visit_If(self, node: ast.If) -> Any:
        if await self.visit(node.test):
            branch = node.body
        else:
            branch = node.orelse
        result = None
        if branch:
            for stmt in branch[:-1]:
                await self.visit(stmt)
            result = await self.visit(branch[-1])
        return result

    async def visit_While(self, node: ast.While) -> None:
        while await self.visit(node.test):
            try:
                for stmt in node.body:
                    await self.visit(stmt)
            except BreakException:
                break
            except ContinueException:
                continue
        for stmt in node.orelse:
            await self.visit(stmt)

    async def visit_For(self, node: ast.For) -> None:
        iter_obj: Any = await self.visit(node.iter)
        broke = False  # Track if loop was broken to handle else clause correctly
        for item in iter_obj:
            self.assign(node.target, item)
            try:
                for stmt in node.body:
                    await self.visit(stmt)
            except BreakException:
                broke = True
                break
            except ContinueException:
                continue
        if not broke:  # Only execute orelse if loop completed without break
            for stmt in node.orelse:
                await self.visit(stmt)

    async def visit_Break(self, node: ast.Break) -> None:
        raise BreakException()

    async def visit_Continue(self, node: ast.Continue) -> None:
        raise ContinueException()

    async def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        closure: List[Dict[str, Any]] = self.env_stack[:]
        pos_kw_params = [arg.arg for arg in node.args.args]
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwonly_params = [arg.arg for arg in node.args.kwonlyargs]
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        pos_defaults_values = [await self.visit(default) for default in node.args.defaults]
        num_pos_defaults = len(pos_defaults_values)
        pos_defaults = dict(zip(pos_kw_params[-num_pos_defaults:], pos_defaults_values)) if num_pos_defaults else {}
        kw_defaults_values = [await self.visit(default) if default else None for default in node.args.kw_defaults]
        kw_defaults = dict(zip(kwonly_params, kw_defaults_values))
        kw_defaults = {k: v for k, v in kw_defaults.items() if v is not None}

        func = Function(node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults)
        decorated_func = func
        for decorator in reversed(node.decorator_list):
            dec = await self.visit(decorator)
            if dec in (staticmethod, classmethod, property):
                decorated_func = dec(func)
            else:
                decorated_func = await dec(decorated_func)
        self.set_variable(node.name, decorated_func)

    async def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        closure: List[Dict[str, Any]] = self.env_stack[:]
        pos_kw_params = [arg.arg for arg in node.args.args]
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwonly_params = [arg.arg for arg in node.args.kwonlyargs]
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        pos_defaults_values = [await self.visit(default) for default in node.args.defaults]
        num_pos_defaults = len(pos_defaults_values)
        pos_defaults = dict(zip(pos_kw_params[-num_pos_defaults:], pos_defaults_values)) if num_pos_defaults else {}
        kw_defaults_values = [await self.visit(default) if default else None for default in node.args.kw_defaults]
        kw_defaults = dict(zip(kwonly_params, kw_defaults_values))
        kw_defaults = {k: v for k, v in kw_defaults.items() if v is not None}

        func = AsyncFunction(node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults)
        for decorator in reversed(node.decorator_list):
            dec = await self.visit(decorator)
            func = await dec(func)
        self.set_variable(node.name, func)

    async def visit_Call(self, node: ast.Call, is_await_context: bool = False) -> Any:
        func = await self.visit(node.func)
        evaluated_args: List[Any] = []
        for arg in node.args:
            arg_value = await self.visit(arg)
            if isinstance(arg, ast.Starred):
                evaluated_args.extend(arg_value)
            else:
                evaluated_args.append(arg_value)

        kwargs: Dict[str, Any] = {}
        for kw in node.keywords:
            if kw.arg is None:  # Handle **kwargs unpacking
                unpacked_kwargs = await self.visit(kw.value)
                if not isinstance(unpacked_kwargs, dict):
                    raise TypeError(f"** argument must be a mapping, not {type(unpacked_kwargs).__name__}")
                kwargs.update(unpacked_kwargs)
            else:
                kwargs[kw.arg] = await self.visit(kw.value)

        # Handle async generators when passed to list()
        if func is list and len(evaluated_args) == 1 and hasattr(evaluated_args[0], '__aiter__'):
            return [val async for val in evaluated_args[0]]

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
            result = await func(*evaluated_args, **kwargs)
        elif func is super:
            if len(evaluated_args) >= 2:
                cls, obj = evaluated_args[0], evaluated_args[1]
                result = super(cls, obj)
            else:
                raise TypeError("super() requires class and instance arguments")
        else:
            result = func(*evaluated_args, **kwargs)
            if asyncio.iscoroutine(result) and not is_await_context:
                result = await result
        return result

    async def visit_Await(self, node: ast.Await) -> Any:
        coro = await self.visit(node.value, is_await_context=True)
        if not asyncio.iscoroutine(coro):
            raise TypeError(f"Cannot await non-coroutine object: {type(coro)}")
        return await coro

    async def visit_Return(self, node: ast.Return) -> None:
        value: Any = await self.visit(node.value) if node.value is not None else None
        raise ReturnException(value)

    async def visit_Lambda(self, node: ast.Lambda) -> Any:
        closure: List[Dict[str, Any]] = self.env_stack[:]
        pos_kw_params = [arg.arg for arg in node.args.args]
        vararg_name = node.args.vararg.arg if node.args.vararg else None
        kwonly_params = [arg.arg for arg in node.args.kwonlyargs]
        kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
        pos_defaults_values = [await self.visit(default) for default in node.args.defaults]
        num_pos_defaults = len(pos_defaults_values)
        pos_defaults = dict(zip(pos_kw_params[-num_pos_defaults:], pos_defaults_values)) if num_pos_defaults else {}
        kw_defaults_values = [await self.visit(default) if default else None for default in node.args.kw_defaults]
        kw_defaults = dict(zip(kwonly_params, kw_defaults_values))
        kw_defaults = {k: v for k, v in kw_defaults.items() if v is not None}

        lambda_func = LambdaFunction(node, closure, self, pos_kw_params, vararg_name, kwonly_params, kwarg_name, pos_defaults, kw_defaults)
        async def async_lambda(*args, **kwargs):
            return await lambda_func(*args, **kwargs)
        return async_lambda

    async def visit_List(self, node: ast.List) -> List[Any]:
        return [await self.visit(elt) for elt in node.elts]

    async def visit_Tuple(self, node: ast.Tuple) -> Tuple[Any, ...]:
        elements = [await self.visit(elt) for elt in node.elts]
        return tuple(elements)

    async def visit_Dict(self, node: ast.Dict) -> Dict[Any, Any]:
        return {await self.visit(k): await self.visit(v) for k, v in zip(node.keys, node.values)}

    async def visit_Set(self, node: ast.Set) -> set:
        return set(await self.visit(elt) for elt in node.elts)

    async def visit_Attribute(self, node: ast.Attribute) -> Any:
        value: Any = await self.visit(node.value)
        return getattr(value, node.attr)

    async def visit_Subscript(self, node: ast.Subscript) -> Any:
        value: Any = await self.visit(node.value)
        slice_val: Any = await self.visit(node.slice)
        return value[slice_val]

    async def visit_Slice(self, node: ast.Slice) -> slice:
        lower: Any = await self.visit(node.lower) if node.lower else None
        upper: Any = await self.visit(node.upper) if node.upper else None
        step: Any = await self.visit(node.step) if node.step else None
        return slice(lower, upper, step)

    async def visit_Index(self, node: ast.Index) -> Any:
        return await self.visit(node.value)

    async def visit_Starred(self, node: ast.Starred) -> Any:
        value = await self.visit(node.value)
        if not isinstance(value, (list, tuple, set)):
            raise TypeError(f"Cannot unpack non-iterable object of type {type(value).__name__}")
        return value

    async def visit_Pass(self, node: ast.Pass) -> None:
        return None

    async def visit_TypeIgnore(self, node: ast.TypeIgnore) -> None:
        pass

    async def visit_Try(self, node: ast.Try) -> Any:
        result: Any = None
        try:
            for stmt in node.body:
                result = await self.visit(stmt)
        except Exception as e:
            for handler in node.handlers:
                exc_type = await self._resolve_exception_type(handler.type)
                if exc_type and isinstance(e, exc_type):
                    if handler.name:
                        self.set_variable(handler.name, e)
                    for stmt in handler.body:
                        result = await self.visit(stmt)
                    break
            else:
                raise  # Re-raise if no handler matches
        else:
            for stmt in node.orelse:
                result = await self.visit(stmt)
        finally:
            for stmt in node.finalbody:
                await self.visit(stmt)
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
            return await self.visit(node)
        return None

    async def visit_TryStar(self, node: ast.TryStar) -> Any:
        result: Any = None
        exc_info: Optional[tuple] = None

        try:
            for stmt in node.body:
                result = await self.visit(stmt)
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
                        exc_type = await self.visit(handler.type)
                    matching_exceptions = [ex for ex in e.exceptions if isinstance(ex, exc_type)]
                    if matching_exceptions:
                        if handler.name:
                            self.set_variable(handler.name, BaseExceptionGroup("", matching_exceptions))
                        for stmt in handler.body:
                            result = await self.visit(stmt)
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
                        exc_type = await self.visit(handler.type)
                    if exc_info and issubclass(exc_info[0], exc_type):
                        if handler.name:
                            self.set_variable(handler.name, exc_info[1])
                        for stmt in handler.body:
                            result = await self.visit(stmt)
                        exc_info = None
                        handled = True
                        break
            if exc_info and not handled:
                raise exc_info[1]
        else:
            for stmt in node.orelse:
                result = await self.visit(stmt)
        finally:
            for stmt in node.finalbody:
                try:
                    await self.visit(stmt)
                except ReturnException:
                    raise
                except Exception:
                    if exc_info:
                        raise exc_info[1]
                    raise

        return result

    async def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.env_stack[-1].setdefault("__nonlocal_names__", set()).update(node.names)

    async def visit_JoinedStr(self, node: ast.JoinedStr) -> str:
        parts = []
        for value in node.values:
            val = await self.visit(value)
            if isinstance(value, ast.FormattedValue):
                parts.append(str(val))
            else:
                parts.append(val)
        return "".join(parts)

    async def visit_FormattedValue(self, node: ast.FormattedValue) -> Any:
        return await self.visit(node.value)

    async def visit_GeneratorExp(self, node: ast.GeneratorExp) -> Any:
        async def generator():
            base_frame: Dict[str, Any] = self.env_stack[-1].copy()
            self.env_stack.append(base_frame)

            async def rec(gen_idx: int):
                if gen_idx == len(node.generators):
                    yield await self.visit(node.elt)
                else:
                    comp = node.generators[gen_idx]
                    iterable = await self.visit(comp.iter)
                    if hasattr(iterable, '__aiter__'):
                        async for item in iterable:
                            new_frame = self.env_stack[-1].copy()
                            self.env_stack.append(new_frame)
                            self.assign(comp.target, item)
                            conditions = [await self.visit(if_clause) for if_clause in comp.ifs]
                            if all(conditions):
                                async for val in rec(gen_idx + 1):
                                    yield val
                            self.env_stack.pop()
                    else:
                        for item in iterable:
                            new_frame = self.env_stack[-1].copy()
                            self.env_stack.append(new_frame)
                            self.assign(comp.target, item)
                            conditions = [await self.visit(if_clause) for if_clause in comp.ifs]
                            if all(conditions):
                                async for val in rec(gen_idx + 1):
                                    yield val
                            self.env_stack.pop()

            async for val in rec(0):
                yield val
            self.env_stack.pop()

        return generator()

    async def visit_ClassDef(self, node: ast.ClassDef):
        base_frame = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)
        bases = [await self.visit(base) for base in node.bases]
        try:
            for stmt in node.body:
                await self.visit(stmt)
            class_dict = {k: v for k, v in self.env_stack[-1].items() if k not in ["__builtins__"]}
        finally:
            self.env_stack.pop()
        new_class = type(node.name, tuple(bases), class_dict)
        for decorator in reversed(node.decorator_list):
            dec = await self.visit(decorator)
            new_class = dec(new_class)
        self.set_variable(node.name, new_class)

    async def visit_With(self, node: ast.With):
        for item in node.items:
            ctx = await self.visit(item.context_expr)
            val = ctx.__enter__()
            if item.optional_vars:
                self.assign(item.optional_vars, val)
            try:
                for stmt in node.body:
                    await self.visit(stmt)
            except Exception as e:
                if not ctx.__exit__(type(e), e, None):
                    raise
            else:
                ctx.__exit__(None, None, None)

    async def visit_Raise(self, node: ast.Raise):
        exc = await self.visit(node.exc) if node.exc else None
        if exc:
            raise exc
        raise Exception("Raise with no exception specified")

    async def visit_Global(self, node: ast.Global):
        self.env_stack[-1].setdefault("__global_names__", set()).update(node.names)

    async def visit_IfExp(self, node: ast.IfExp):
        return await self.visit(node.body) if await self.visit(node.test) else await self.visit(node.orelse)

    async def visit_DictComp(self, node: ast.DictComp):
        result = {}
        base_frame = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)

        async def rec(gen_idx: int):
            if gen_idx == len(node.generators):
                key = await self.visit(node.key)
                val = await self.visit(node.value)
                result[key] = val
            else:
                comp = node.generators[gen_idx]
                iterable = await self.visit(comp.iter)
                if hasattr(iterable, '__aiter__'):
                    async for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()
                else:
                    for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()

        await rec(0)
        self.env_stack.pop()
        return result

    async def visit_SetComp(self, node: ast.SetComp):
        result = set()
        base_frame = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)

        async def rec(gen_idx: int):
            if gen_idx == len(node.generators):
                result.add(await self.visit(node.elt))
            else:
                comp = node.generators[gen_idx]
                iterable = await self.visit(comp.iter)
                if hasattr(iterable, '__aiter__'):
                    async for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()
                else:
                    for item in iterable:
                        new_frame = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        self.assign(comp.target, item)
                        conditions = [await self.visit(if_clause) for if_clause in comp.ifs]
                        if all(conditions):
                            await rec(gen_idx + 1)
                        self.env_stack.pop()

        await rec(0)
        self.env_stack.pop()
        return result

    async def visit_Match(self, node: ast.Match) -> Any:
        subject = await self.visit(node.subject)
        result = None
        base_frame = self.env_stack[-1].copy()
        for case in node.cases:
            self.env_stack.append(base_frame.copy())
            try:
                if await self._match_pattern(subject, case.pattern):
                    if case.guard and not await self.visit(case.guard):
                        continue
                    for stmt in case.body[:-1]:
                        await self.visit(stmt)
                    result = await self.visit(case.body[-1])
                    break
            finally:
                self.env_stack.pop()
        return result

    async def _match_pattern(self, subject: Any, pattern: ast.AST) -> bool:
        if isinstance(pattern, ast.MatchValue):
            value = await self.visit(pattern.value)
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
                        return False  # Multiple stars not allowed
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
            keys = [await self.visit(k) for k in pattern.keys]
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
            cls = await self.visit(pattern.cls)
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

    async def visit_Delete(self, node: ast.Delete):
        for target in node.targets:
            if isinstance(target, ast.Name):
                del self.env_stack[-1][target.id]
            elif isinstance(target, ast.Subscript):
                obj = await self.visit(target.value)
                key = await self.visit(target.slice)
                del obj[key]
            else:
                raise Exception(f"Unsupported del target: {type(target).__name__}")


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

        new_env_stack.append(local_frame)
        new_interp: ASTInterpreter = self.interpreter.spawn_from_env(new_env_stack)
        try:
            for stmt in self.node.body[:-1]:
                await new_interp.visit(stmt)
            return await new_interp.visit(self.node.body[-1])
        except ReturnException as ret:
            return ret.value
        return None

    def __get__(self, instance: Any, owner: Any):
        async def method(*args: Any, **kwargs: Any) -> Any:
            return await self(instance, *args, **kwargs) if instance else await self(*args, **kwargs)
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
                last_value = await new_interp.visit(stmt)
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
        return await new_interp.visit(self.node.body)


def interpret_ast(ast_tree: Any, allowed_modules: list[str], source: str = "") -> Any:
    interpreter = ASTInterpreter(allowed_modules=allowed_modules, source=source)

    async def run_interpreter():
        result = await interpreter.visit(ast_tree)
        if asyncio.iscoroutine(result):
            return await result
        elif hasattr(result, '__aiter__'):
            return [val async for val in result]  # Handle async generators
        return result

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    interpreter.loop = loop
    try:
        return loop.run_until_complete(run_interpreter())
    finally:
        loop.close()


def interpret_code(source_code: str, allowed_modules: List[str]) -> Any:
    dedented_source = textwrap.dedent(source_code).strip()
    tree: ast.AST = ast.parse(dedented_source)
    return interpret_ast(tree, allowed_modules, source=dedented_source)


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
        result_1: Any = interpret_code(source_code_1, allowed_modules=[])
        print("Result:", result_1)  # Expected: 31 (1 + 4 + 7 + 5 + 6 + 8)
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
        result_2: Any = interpret_code(source_code_2, allowed_modules=["asyncio"])
        print("Result:", result_2)  # Expected: 25
    except Exception as e:
        print("Interpreter error:", e)

    source_code_3: str = """
f = lambda x, y=2, *args, z=3, **kwargs: x + y + z + sum(args) + sum(kwargs.values())
result = f(1, 4, 5, z=6, w=7)
"""
    print("Example 3 (lambda with defaults and kwargs):")
    try:
        result_3: Any = interpret_code(source_code_3, allowed_modules=[])
        print("Result:", result_3)  # Expected: 23 (1 + 4 + 6 + 5 + 7)
    except Exception as e:
        print("Interpreter error:", e)

    source_code_4: str = """
def describe(x):
    match x:
        case 1:
            return "One"
        case [a, b]:
            return f"List of {a} and {b}"
        case {"key": value}:
            return f"Dict with key={value}"
        case _:
            return "Unknown"

result = describe([10, 20])
"""
    print("Example 4 (structural pattern matching):")
    try:
        result_4: Any = interpret_code(source_code_4, allowed_modules=[])
        print("Result:", result_4)  # Expected: "List of 10 and 20"
    except Exception as e:
        print("Interpreter error:", e)

    source_code_5: str = """
def risky():
    raise ExceptionGroup("Problems", [ValueError("bad value"), TypeError("bad type")])

try:
    risky()
except* ValueError as ve:
    result = "Caught ValueError"
except* TypeError as te:
    result = "Caught TypeError"
"""
    print("Example 5 (exception groups with except*):")
    try:
        result_5: Any = interpret_code(source_code_5, allowed_modules=[])
        print("Result:", result_5)  # Expected: "Caught ValueError"
    except Exception as e:
        print("Interpreter error:", e)