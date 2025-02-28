import ast
import builtins
import textwrap
from typing import Any, Dict, List, Optional, Tuple


# Exception used to signal a "return" from a function call.
class ReturnException(Exception):
    def __init__(self, value: Any) -> None:
        self.value: Any = value


# Exceptions used for loop control.
class BreakException(Exception):
    pass


class ContinueException(Exception):
    pass


# The main interpreter class.
class ASTInterpreter:
    def __init__(
        self, allowed_modules: List[str], env_stack: Optional[List[Dict[str, Any]]] = None, source: Optional[str] = None
    ) -> None:
        """
        Initialize the AST interpreter with restricted module access and environment stack.

        Args:
            allowed_modules: List of module names allowed to be imported.
            env_stack: Optional pre-existing environment stack; if None, a new one is created.
            source: Optional source code string for error reporting.
        """
        self.allowed_modules: List[str] = allowed_modules
        self.modules: Dict[str, Any] = {}
        # Import only the allowed modules.
        for mod in allowed_modules:
            self.modules[mod] = __import__(mod)
        if env_stack is None:
            # Create a global environment (first frame) with allowed modules.
            self.env_stack: List[Dict[str, Any]] = [{}]
            self.env_stack[0].update(self.modules)
            # Use builtins from the builtins module.
            safe_builtins: Dict[str, Any] = dict(vars(builtins))
            safe_builtins["__import__"] = self.safe_import
            if "set" not in safe_builtins:
                safe_builtins["set"] = set
            self.env_stack[0]["__builtins__"] = safe_builtins
            # Make builtins names (like set) directly available.
            self.env_stack[0].update(safe_builtins)
            if "set" not in self.env_stack[0]:
                self.env_stack[0]["set"] = set
        else:
            self.env_stack = env_stack
            # Ensure global frame has safe builtins.
            if "__builtins__" not in self.env_stack[0]:
                safe_builtins: Dict[str, Any] = dict(vars(builtins))
                safe_builtins["__import__"] = self.safe_import
                if "set" not in safe_builtins:
                    safe_builtins["set"] = set
                self.env_stack[0]["__builtins__"] = safe_builtins
                self.env_stack[0].update(safe_builtins)
            if "set" not in self.env_stack[0]:
                self.env_stack[0]["set"] = self.env_stack[0]["__builtins__"]["set"]

        # Store source code lines for error reporting if provided.
        if source is not None:
            self.source_lines: Optional[List[str]] = source.splitlines()
        else:
            self.source_lines = None

        # Add standard Decimal features if allowed.
        if "decimal" in self.modules:
            dec = self.modules["decimal"]
            self.env_stack[0]["Decimal"] = dec.Decimal
            self.env_stack[0]["getcontext"] = dec.getcontext
            self.env_stack[0]["setcontext"] = dec.setcontext
            self.env_stack[0]["localcontext"] = dec.localcontext
            self.env_stack[0]["Context"] = dec.Context

    # This safe __import__ only allows modules explicitly provided.
    def safe_import(
        self,
        name: str,
        globals: Optional[Dict[str, Any]] = None,
        locals: Optional[Dict[str, Any]] = None,
        fromlist: Tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        """Restrict imports to only allowed modules."""
        if name not in self.allowed_modules:
            error_msg = f"Import Error: Module '{name}' is not allowed. Only {self.allowed_modules} are permitted."
            raise ImportError(error_msg)
        return self.modules[name]

    # Helper: create a new interpreter instance using a given environment stack.
    def spawn_from_env(self, env_stack: List[Dict[str, Any]]) -> "ASTInterpreter":
        """Spawn a new interpreter with the provided environment stack."""
        return ASTInterpreter(
            self.allowed_modules, env_stack, source="\n".join(self.source_lines) if self.source_lines else None
        )

    # Look up a variable in the chain of environment frames.
    def get_variable(self, name: str) -> Any:
        """Retrieve a variable's value from the environment stack."""
        for frame in reversed(self.env_stack):
            if name in frame:
                return frame[name]
        raise NameError(f"Name {name} is not defined.")

    # Always assign to the most local environment.
    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable in the most local environment frame."""
        self.env_stack[-1][name] = value

    # Used for assignment targets. This handles names and destructuring.
    def assign(self, target: ast.AST, value: Any) -> None:
        """Assign a value to a target (name, tuple, attribute, or subscript)."""
        if isinstance(target, ast.Name):
            # If current frame declares the name as global, update global frame.
            if "__global_names__" in self.env_stack[-1] and target.id in self.env_stack[-1]["__global_names__"]:
                self.env_stack[0][target.id] = value
            else:
                self.env_stack[-1][target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            # Support single-star unpacking.
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
                after = target.elts[star_index + 1 :]
                if len(before) + len(after) > total:
                    raise ValueError("Unpacking mismatch")
                for i, elt2 in enumerate(before):
                    self.assign(elt2, value[i])
                starred_count = total - len(before) - len(after)
                self.assign(target.elts[star_index].value, value[len(before) : len(before) + starred_count])
                for j, elt2 in enumerate(after):
                    self.assign(elt2, value[len(before) + starred_count + j])
        elif isinstance(target, ast.Attribute):
            obj = self.visit(target.value)
            setattr(obj, target.attr, value)
        elif isinstance(target, ast.Subscript):
            obj = self.visit(target.value)
            key = self.visit(target.slice)
            obj[key] = value
        else:
            raise Exception("Unsupported assignment target type: " + str(type(target)))

    # Main visitor dispatch.
    def visit(self, node: ast.AST) -> Any:
        """Dispatch to the appropriate visitor method for the AST node."""
        method_name: str = "visit_" + node.__class__.__name__
        method = getattr(self, method_name, self.generic_visit)
        try:
            return method(node)
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

    # Fallback for unsupported nodes.
    def generic_visit(self, node: ast.AST) -> Any:
        """Handle unsupported AST nodes with an error."""
        lineno = getattr(node, "lineno", None)
        context_line = ""
        if self.source_lines and lineno is not None and 1 <= lineno <= len(self.source_lines):
            context_line = self.source_lines[lineno - 1]
        raise Exception(
            f"Unsupported AST node type: {node.__class__.__name__} at line {lineno}.\nContext: {context_line}"
        )

    # --- Visitor for Import nodes ---
    def visit_Import(self, node: ast.Import) -> None:
        """
        Process an import statement.
        Only allowed modules can be imported.
        """
        for alias in node.names:
            module_name: str = alias.name
            asname: str = alias.asname if alias.asname is not None else module_name
            if module_name not in self.allowed_modules:
                raise Exception(
                    f"Import Error: Module '{module_name}' is not allowed. Only {self.allowed_modules} are permitted."
                )
            self.set_variable(asname, self.modules[module_name])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Process 'from ... import ...' statements with restricted module access."""
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

    # --- Visitor for ListComprehension nodes ---
    def visit_ListComp(self, node: ast.ListComp) -> List[Any]:
        """
        Process a list comprehension, e.g., [elt for ... in ... if ...].
        The comprehension is executed in a new local frame that inherits the current environment.
        """
        result: List[Any] = []
        # Copy the current top-level frame for the comprehension scope.
        base_frame: Dict[str, Any] = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)

        def rec(gen_idx: int) -> None:
            if gen_idx == len(node.generators):
                result.append(self.visit(node.elt))
            else:
                comp = node.generators[gen_idx]
                iterable = self.visit(comp.iter)
                for item in iterable:
                    # Push a new frame that inherits the current comprehension scope.
                    new_frame: Dict[str, Any] = self.env_stack[-1].copy()
                    self.env_stack.append(new_frame)
                    self.assign(comp.target, item)
                    if all(self.visit(if_clause) for if_clause in comp.ifs):
                        rec(gen_idx + 1)
                    self.env_stack.pop()

        rec(0)
        self.env_stack.pop()
        return result

    # --- Other node visitors below ---
    def visit_Module(self, node: ast.Module) -> Any:
        """Execute module body and return 'result' or last value."""
        last_value: Any = None
        for stmt in node.body:
            last_value = self.visit(stmt)
        return self.env_stack[0].get("result", last_value)

    def visit_Expr(self, node: ast.Expr) -> Any:
        """Evaluate an expression statement."""
        return self.visit(node.value)

    def visit_Constant(self, node: ast.Constant) -> Any:
        """Return the value of a constant node."""
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        """Handle variable name lookups or stores."""
        if isinstance(node.ctx, ast.Load):
            return self.get_variable(node.id)
        elif isinstance(node.ctx, ast.Store):
            return node.id
        else:
            raise Exception("Unsupported context for Name")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        """Evaluate binary operations."""
        left: Any = self.visit(node.left)
        right: Any = self.visit(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        elif isinstance(op, ast.Sub):
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
            return left | right
        elif isinstance(op, ast.BitXor):
            return left ^ right
        elif isinstance(op, ast.BitAnd):
            return left & right
        else:
            raise Exception("Unsupported binary operator: " + str(op))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        """Evaluate unary operations."""
        operand: Any = self.visit(node.operand)
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

    def visit_Assign(self, node: ast.Assign) -> None:
        """Handle assignment statements."""
        value: Any = self.visit(node.value)
        for target in node.targets:
            self.assign(target, value)

    def visit_AugAssign(self, node: ast.AugAssign) -> Any:
        """Handle augmented assignments (e.g., +=)."""
        # If target is a Name, get its current value from the environment.
        if isinstance(node.target, ast.Name):
            current_val: Any = self.get_variable(node.target.id)
        else:
            current_val: Any = self.visit(node.target)
        right_val: Any = self.visit(node.value)
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

    def visit_Compare(self, node: ast.Compare) -> bool:
        """Evaluate comparison operations."""
        left: Any = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right: Any = self.visit(comparator)
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

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        """Evaluate boolean operations (and/or)."""
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not self.visit(value):
                    return False
            return True
        elif isinstance(node.op, ast.Or):
            for value in node.values:
                if self.visit(value):
                    return True
            return False
        else:
            raise Exception("Unsupported boolean operator: " + str(node.op))

    def visit_If(self, node: ast.If) -> Any:
        """Handle if statements."""
        if self.visit(node.test):
            branch = node.body
        else:
            branch = node.orelse
        result = None
        if branch:
            for stmt in branch[:-1]:
                # Execute all but the last statement
                self.visit(stmt)
            # Return value from the last statement
            result = self.visit(branch[-1])
        return result

    def visit_While(self, node: ast.While) -> None:
        """Handle while loops."""
        while self.visit(node.test):
            try:
                for stmt in node.body:
                    self.visit(stmt)
            except BreakException:
                break
            except ContinueException:
                continue
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_For(self, node: ast.For) -> None:
        """Handle for loops."""
        iter_obj: Any = self.visit(node.iter)
        for item in iter_obj:
            self.assign(node.target, item)
            try:
                for stmt in node.body:
                    self.visit(stmt)
            except BreakException:
                break
            except ContinueException:
                continue
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_Break(self, node: ast.Break) -> None:
        """Handle break statements."""
        raise BreakException()

    def visit_Continue(self, node: ast.Continue) -> None:
        """Handle continue statements."""
        raise ContinueException()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Define a function and store it in the environment."""
        # Capture the current env_stack for a closure without copying inner dicts.
        closure: List[Dict[str, Any]] = self.env_stack[:]
        func = Function(node, closure, self)
        self.set_variable(node.name, func)

    def visit_Call(self, node: ast.Call) -> Any:
        """Handle function calls."""
        func = self.visit(node.func)
        args: List[Any] = [self.visit(arg) for arg in node.args]
        kwargs: Dict[str, Any] = {kw.arg: self.visit(kw.value) for kw in node.keywords}
        return func(*args, **kwargs)

    def visit_Return(self, node: ast.Return) -> None:
        """Handle return statements."""
        value: Any = self.visit(node.value) if node.value is not None else None
        raise ReturnException(value)

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        """Define a lambda function."""
        closure: List[Dict[str, Any]] = self.env_stack[:]
        return LambdaFunction(node, closure, self)

    def visit_List(self, node: ast.List) -> List[Any]:
        """Evaluate list literals."""
        return [self.visit(elt) for elt in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> Tuple[Any, ...]:
        """Evaluate tuple literals."""
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_Dict(self, node: ast.Dict) -> Dict[Any, Any]:
        """Evaluate dictionary literals."""
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_Set(self, node: ast.Set) -> set:
        """Evaluate set literals."""
        return set(self.visit(elt) for elt in node.elts)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        """Handle attribute access."""
        value: Any = self.visit(node.value)
        return getattr(value, node.attr)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        """Handle subscript operations (e.g., list indexing)."""
        value: Any = self.visit(node.value)
        slice_val: Any = self.visit(node.slice)
        return value[slice_val]

    def visit_Slice(self, node: ast.Slice) -> slice:
        """Evaluate slice objects."""
        lower: Any = self.visit(node.lower) if node.lower else None
        upper: Any = self.visit(node.upper) if node.upper else None
        step: Any = self.visit(node.step) if node.step else None
        return slice(lower, upper, step)

    # For compatibility with older AST versions.
    def visit_Index(self, node: ast.Index) -> Any:
        """Handle index nodes for older AST compatibility."""
        return self.visit(node.value)

    # Visitor for Pass nodes.
    def visit_Pass(self, node: ast.Pass) -> None:
        """Handle pass statements (do nothing)."""
        return None

    def visit_TypeIgnore(self, node: ast.TypeIgnore) -> None:
        """Handle type ignore statements (do nothing)."""
        pass

    def visit_Try(self, node: ast.Try) -> Any:
        """Handle try-except blocks."""
        result: Any = None
        exc_info: Optional[tuple] = None

        try:
            for stmt in node.body:
                result = self.visit(stmt)
        except Exception as e:
            exc_info = (type(e), e, e.__traceback__)
            for handler in node.handlers:
                # Modified resolution for exception type.
                if handler.type is None:
                    exc_type = Exception
                elif isinstance(handler.type, ast.Constant) and isinstance(handler.type.value, type):
                    exc_type = handler.type.value
                elif isinstance(handler.type, ast.Name):
                    exc_type = self.get_variable(handler.type.id)
                else:
                    exc_type = self.visit(handler.type)
                # Use issubclass on the exception type rather than isinstance on the exception instance.
                if exc_info and issubclass(exc_info[0], exc_type):
                    if handler.name:
                        self.set_variable(handler.name, exc_info[1])
                    for stmt in handler.body:
                        result = self.visit(stmt)
                    exc_info = None  # Mark as handled
                    break
            if exc_info:
                raise exc_info[1]
        else:
            for stmt in node.orelse:
                result = self.visit(stmt)
        finally:
            for stmt in node.finalbody:
                try:
                    self.visit(stmt)
                except ReturnException:
                    raise
                except Exception:
                    if exc_info:
                        raise exc_info[1]
                    raise

        return result

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        """Handle nonlocal statements (minimal support)."""
        # Minimal support – assume these names exist in an outer frame.
        return None

    def visit_JoinedStr(self, node: ast.JoinedStr) -> str:
        """Handle f-strings by concatenating all parts."""
        return "".join(self.visit(value) for value in node.values)

    def visit_FormattedValue(self, node: ast.FormattedValue) -> str:
        """Handle formatted values within f-strings."""
        return str(self.visit(node.value))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> Any:
        """Handle generator expressions."""
        def generator():
            base_frame: Dict[str, Any] = self.env_stack[-1].copy()
            self.env_stack.append(base_frame)

            def rec(gen_idx: int):
                if gen_idx == len(node.generators):
                    yield self.visit(node.elt)
                else:
                    comp = node.generators[gen_idx]
                    iterable = self.visit(comp.iter)
                    for item in iterable:
                        new_frame: Dict[str, Any] = self.env_stack[-1].copy()
                        self.env_stack.append(new_frame)
                        self.assign(comp.target, item)
                        if all(self.visit(if_clause) for if_clause in comp.ifs):
                            yield from rec(gen_idx + 1)
                        self.env_stack.pop()

            gen = list(rec(0))
            self.env_stack.pop()
            for val in gen:
                yield val

        return generator()

    def visit_ClassDef(self, node: ast.ClassDef):
        """Handle class definitions."""
        base_frame = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)
        try:
            for stmt in node.body:
                self.visit(stmt)
            class_dict = {k: v for k, v in self.env_stack[-1].items() if k not in ["__builtins__"]}
        finally:
            self.env_stack.pop()
        new_class = type(node.name, (), class_dict)
        self.set_variable(node.name, new_class)

    def visit_With(self, node: ast.With):
        """Handle with statements."""
        for item in node.items:
            ctx = self.visit(item.context_expr)
            val = ctx.__enter__()
            if item.optional_vars:
                self.assign(item.optional_vars, val)
            try:
                for stmt in node.body:
                    self.visit(stmt)
            except Exception as e:
                if not ctx.__exit__(type(e), e, None):
                    raise
            else:
                ctx.__exit__(None, None, None)

    def visit_Raise(self, node: ast.Raise):
        """Handle raise statements."""
        exc = self.visit(node.exc) if node.exc else None
        if exc:
            raise exc
        raise Exception("Raise with no exception specified")

    def visit_Global(self, node: ast.Global):
        """Handle global statements."""
        self.env_stack[-1].setdefault("__global_names__", set()).update(node.names)

    def visit_IfExp(self, node: ast.IfExp):
        """Handle ternary if expressions."""
        return self.visit(node.body) if self.visit(node.test) else self.visit(node.orelse)

    def visit_DictComp(self, node: ast.DictComp):
        """Handle dictionary comprehensions."""
        result = {}
        base_frame = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)

        def rec(gen_idx: int):
            if gen_idx == len(node.generators):
                key = self.visit(node.key)
                val = self.visit(node.value)
                result[key] = val
            else:
                comp = node.generators[gen_idx]
                for item in self.visit(comp.iter):
                    new_frame = self.env_stack[-1].copy()
                    self.env_stack.append(new_frame)
                    self.assign(comp.target, item)
                    if all(self.visit(if_clause) for if_clause in comp.ifs):
                        rec(gen_idx + 1)
                    self.env_stack.pop()

        rec(0)
        self.env_stack.pop()
        return result

    def visit_SetComp(self, node: ast.SetComp):
        """Handle set comprehensions."""
        result = set()
        base_frame = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)

        def rec(gen_idx: int):
            if gen_idx == len(node.generators):
                result.add(self.visit(node.elt))
            else:
                comp = node.generators[gen_idx]
                for item in self.visit(comp.iter):
                    new_frame = self.env_stack[-1].copy()
                    self.env_stack.append(new_frame)
                    self.assign(comp.target, item)
                    if all(self.visit(if_clause) for if_clause in comp.ifs):
                        rec(gen_idx + 1)
                    self.env_stack.pop()

        rec(0)
        self.env_stack.pop()
        return result


# Class to represent a user-defined function.
class Function:
    def __init__(self, node: ast.FunctionDef, closure: List[Dict[str, Any]], interpreter: ASTInterpreter) -> None:
        """Initialize a user-defined function."""
        self.node: ast.FunctionDef = node
        # Shallow copy to support recursion.
        self.closure: List[Dict[str, Any]] = self.env_stack_reference(closure)
        self.interpreter: ASTInterpreter = interpreter

    # Helper to simply return the given environment stack (shallow copy of list refs).
    def env_stack_reference(self, env_stack: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return a shallow copy of the environment stack."""
        return env_stack[:]  # shallow

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the function with given arguments."""
        new_env_stack: List[Dict[str, Any]] = self.closure[:]
        local_frame: Dict[str, Any] = {}
        # Bind the function into its own local frame for recursion.
        local_frame[self.node.name] = self
        # For simplicity, only positional parameters are supported.
        if len(args) < len(self.node.args.args):
            raise TypeError("Not enough arguments provided")
        if len(args) > len(self.node.args.args):
            raise TypeError("Too many arguments provided")
        if kwargs:
            raise TypeError("Keyword arguments are not supported")
        for i, arg in enumerate(self.node.args.args):
            local_frame[arg.arg] = args[i]
        new_env_stack.append(local_frame)
        new_interp: ASTInterpreter = self.interpreter.spawn_from_env(new_env_stack)
        try:
            for stmt in self.node.body[:-1]:
                new_interp.visit(stmt)
            return new_interp.visit(self.node.body[-1])
        except ReturnException as ret:
            return ret.value
        return None

    # Add __get__ to support method binding.
    def __get__(self, instance: Any, owner: Any):
        """Support method binding for instance methods."""
        def method(*args: Any, **kwargs: Any) -> Any:
            return self(instance, *args, **kwargs)
        return method


# Class to represent a lambda function.
class LambdaFunction:
    def __init__(self, node: ast.Lambda, closure: List[Dict[str, Any]], interpreter: ASTInterpreter) -> None:
        """Initialize a lambda function."""
        self.node: ast.Lambda = node
        self.closure: List[Dict[str, Any]] = self.env_stack_reference(closure)
        self.interpreter: ASTInterpreter = interpreter

    def env_stack_reference(self, env_stack: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return a shallow copy of the environment stack."""
        return env_stack[:]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the lambda function with given arguments."""
        new_env_stack: List[Dict[str, Any]] = self.closure[:]
        local_frame: Dict[str, Any] = {}
        if len(args) < len(self.node.args.args):
            raise TypeError("Not enough arguments for lambda")
        if len(args) > len(self.node.args.args):
            raise TypeError("Too many arguments for lambda")
        if kwargs:
            raise TypeError("Lambda does not support keyword arguments")
        for i, arg in enumerate(self.node.args.args):
            local_frame[arg.arg] = args[i]
        new_env_stack.append(local_frame)
        new_interp: ASTInterpreter = self.interpreter.spawn_from_env(new_env_stack)
        return new_interp.visit(self.node.body)


# The main function to interpret an AST.
def interpret_ast(ast_tree: Any, allowed_modules: list[str], source: str = "") -> Any:
    """Interpret an AST with restricted module access."""
    import ast

    # Keep only yield-based nodes in fallback.
    unsupported = (ast.Yield, ast.YieldFrom)
    for node in ast.walk(ast_tree):
        if isinstance(node, unsupported):
            safe_globals = {
                "__builtins__": {
                    "range": range,
                    "len": len,
                    "print": print,
                    "__import__": __import__,
                    "ZeroDivisionError": ZeroDivisionError,
                    "ValueError": ValueError,
                    "NameError": NameError,
                    "TypeError": TypeError,
                    "list": list,
                    "dict": dict,
                    "tuple": tuple,
                    "set": set,
                    "float": float,
                    "int": int,
                    "bool": bool,
                    "Exception": Exception,
                }
            }
            for mod in allowed_modules:
                safe_globals[mod] = __import__(mod)
            local_vars = {}
            exec(compile(ast_tree, "<string>", "exec"), safe_globals, local_vars)
            return local_vars.get("result", None)
    # Otherwise, use the custom interpreter.
    interpreter = ASTInterpreter(allowed_modules=allowed_modules, source=source)
    return interpreter.visit(ast_tree)


# A helper function which takes a Python code string and a list of allowed module names,
# then parses and interprets the code.
def interpret_code(source_code: str, allowed_modules: List[str]) -> Any:
    """
    Interpret a Python source code string with a restricted set of allowed modules.

    Args:
        source_code: The Python source code to interpret.
        allowed_modules: A list of module names that are allowed.
    Returns:
        The result of interpreting the source code.
    """
    # Dedent the source to normalize its indentation.
    dedented_source = textwrap.dedent(source_code)
    tree: ast.AST = ast.parse(dedented_source)
    return interpret_ast(tree, allowed_modules, source=dedented_source)


if __name__ == "__main__":
    print("Script is running!")
    source_code_1: str = """
import math
def square(x):
    return x * x

y = square(5)
z = math.sqrt(y)
z
"""
    # Only "math" is allowed here.
    try:
        result_1: Any = interpret_code(source_code_1, allowed_modules=["math"])
        print("Result:", result_1)
    except Exception as e:
        print("Interpreter error:", e)

    print("Second example:")

    # Define the source code with multiple operations and a list comprehension.
    source_code_2: str = """
import math
import numpy as np
def transform_array(x):
    # Apply square root
    sqrt_vals = [math.sqrt(val) for val in x]
    
    # Apply sine function
    sin_vals = [math.sin(val) for val in sqrt_vals]
    
    # Apply exponential
    exp_vals = [math.exp(val) for val in sin_vals]
    
    return exp_vals

array_input = np.array([1, 4, 9, 16, 25])
result = transform_array(array_input)
result
"""
    print("About to parse source code")
    try:
        tree_2: ast.AST = ast.parse(textwrap.dedent(source_code_2))
        print("Source code parsed successfully")
        # Allow both math and numpy.
        result_2: Any = interpret_ast(tree_2, allowed_modules=["math", "numpy"], source=textwrap.dedent(source_code_2))
        print("Result:", result_2)
    except Exception as e:
        print("Interpreter error:", e)