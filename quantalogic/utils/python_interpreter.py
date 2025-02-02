import ast
from typing import Any, List, Dict, Optional, Tuple
import builtins  # <-- added to correctly copy builtins

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
        self,
        allowed_modules: List[str],
        env_stack: Optional[List[Dict[str, Any]]] = None,
        source: Optional[str] = None
    ) -> None:
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
                safe_builtins["set"] = builtins.set
            self.env_stack[0]["__builtins__"] = safe_builtins
            # Make builtins names (like set) directly available.
            self.env_stack[0].update(safe_builtins)
            if "set" not in self.env_stack[0]:
                self.env_stack[0]["set"] = safe_builtins["set"]
        else:
            self.env_stack = env_stack
            # Ensure global frame has safe builtins.
            if "__builtins__" not in self.env_stack[0]:
                safe_builtins: Dict[str, Any] = dict(vars(builtins))
                safe_builtins["__import__"] = self.safe_import
                if "set" not in safe_builtins:
                    safe_builtins["set"] = builtins.set
                self.env_stack[0]["__builtins__"] = safe_builtins
                self.env_stack[0].update(safe_builtins)
            if "set" not in self.env_stack[0]:
                self.env_stack[0]["set"] = self.env_stack[0]["__builtins__"]["set"]

        # Store source code lines for error reporting if provided.
        if source is not None:
            self.source_lines: Optional[List[str]] = source.splitlines()
        else:
            self.source_lines = None

    # This safe __import__ only allows modules explicitly provided.
    def safe_import(
        self,
        name: str,
        globals: Optional[Dict[str, Any]] = None,
        locals: Optional[Dict[str, Any]] = None,
        fromlist: Tuple[str, ...] = (),
        level: int = 0
    ) -> Any:
        if name not in self.allowed_modules:
            error_msg = f"Import Error: Module '{name}' is not allowed. Only {self.allowed_modules} are permitted."
            raise ImportError(error_msg)
        return self.modules[name]

    # Helper: create a new interpreter instance using a given environment stack.
    def spawn_from_env(self, env_stack: List[Dict[str, Any]]) -> "ASTInterpreter":
        return ASTInterpreter(
            self.allowed_modules,
            env_stack,
            source="\n".join(self.source_lines) if self.source_lines else None
        )

    # Look up a variable in the chain of environment frames.
    def get_variable(self, name: str) -> Any:
        for frame in reversed(self.env_stack):
            if name in frame:
                return frame[name]
        raise NameError(f"Name {name} is not defined.")

    # Always assign to the most local environment.
    def set_variable(self, name: str, value: Any) -> None:
        self.env_stack[-1][name] = value

    # Used for assignment targets. This handles names and destructuring.
    def assign(self, target: ast.AST, value: Any) -> None:
        if isinstance(target, ast.Name):
            self.set_variable(target.id, value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            if not isinstance(value, (list, tuple)):
                raise TypeError("Can only unpack an iterable")
            if len(target.elts) != len(value):
                raise ValueError("Unpacking mismatch")
            for i in range(len(target.elts)):
                self.assign(target.elts[i], value[i])
        elif isinstance(target, ast.Attribute):
            obj = self.visit(target.value)
            setattr(obj, target.attr, value)
        else:
            raise Exception("Unsupported assignment target type: " + str(type(target)))

    # Main visitor dispatch.
    def visit(self, node: ast.AST) -> Any:
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
            raise Exception(
                f"Error line {lineno}, col {col}:\n{context_line}\nDescription: {str(e)}"
            ) from e

    # Fallback for unsupported nodes.
    def generic_visit(self, node: ast.AST) -> Any:
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
                raise Exception(f"Import Error: Module '{module_name}' is not allowed. Only {self.allowed_modules} are permitted.")
            self.set_variable(asname, self.modules[module_name])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.module:
            raise Exception("Import Error: Missing module name in 'from ... import ...' statement")
        if node.module not in self.allowed_modules:
            raise Exception(f"Import Error: Module '{node.module}' is not allowed. Only {self.allowed_modules} are permitted.")
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
        The comprehension is executed in a new local frame that inherits the
        current environment.
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
        result: Any = None
        body = node.body
        for stmt in body:
            result = self.visit(stmt)
        return result

    def visit_Expr(self, node: ast.Expr) -> Any:
        return self.visit(node.value)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Load):
            return self.get_variable(node.id)
        elif isinstance(node.ctx, ast.Store):
            return node.id
        else:
            raise Exception("Unsupported context for Name")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
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
            return left ** right
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
        value: Any = self.visit(node.value)
        for target in node.targets:
            self.assign(target, value)

    def visit_AugAssign(self, node: ast.AugAssign) -> Any:
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
            result = current_val ** right_val
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
                if not (left is right):
                    return False
            elif isinstance(op, ast.IsNot):
                if not (left is not right):
                    return False
            elif isinstance(op, ast.In):
                if not (left in right):
                    return False
            elif isinstance(op, ast.NotIn):
                if not (left not in right):
                    return False
            else:
                raise Exception("Unsupported comparison operator: " + str(op))
            left = right
        return True

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
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
        raise BreakException()

    def visit_Continue(self, node: ast.Continue) -> None:
        raise ContinueException()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Capture the current env_stack for a closure.
        closure: List[Dict[str, Any]] = [frame.copy() for frame in self.env_stack]
        func = Function(node, closure, self)
        self.set_variable(node.name, func)

    def visit_Call(self, node: ast.Call) -> Any:
        func = self.visit(node.func)
        args: List[Any] = [self.visit(arg) for arg in node.args]
        kwargs: Dict[str, Any] = {kw.arg: self.visit(kw.value) for kw in node.keywords}
        return func(*args, **kwargs)

    def visit_Return(self, node: ast.Return) -> None:
        value: Any = self.visit(node.value) if node.value is not None else None
        raise ReturnException(value)

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        closure: List[Dict[str, Any]] = [frame.copy() for frame in self.env_stack]
        return LambdaFunction(node, closure, self)

    def visit_List(self, node: ast.List) -> List[Any]:
        return [self.visit(elt) for elt in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> Tuple[Any, ...]:
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_Dict(self, node: ast.Dict) -> Dict[Any, Any]:
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_Set(self, node: ast.Set) -> set:
        return set(self.visit(elt) for elt in node.elts)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        value: Any = self.visit(node.value)
        return getattr(value, node.attr)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        value: Any = self.visit(node.value)
        slice_val: Any = self.visit(node.slice)
        return value[slice_val]

    def visit_Slice(self, node: ast.Slice) -> slice:
        lower: Any = self.visit(node.lower) if node.lower else None
        upper: Any = self.visit(node.upper) if node.upper else None
        step: Any = self.visit(node.step) if node.step else None
        return slice(lower, upper, step)

    # For compatibility with older AST versions.
    def visit_Index(self, node: ast.Index) -> Any:
        return self.visit(node.value)

    # Visitor for Pass nodes.
    def visit_Pass(self, node: ast.Pass) -> None:
        # Simply ignore 'pass' statements.
        return None

    def visit_TypeIgnore(self, node: ast.TypeIgnore) -> None:
        pass

# Class to represent a user-defined function.
class Function:
    def __init__(self, node: ast.FunctionDef, closure: List[Dict[str, Any]], interpreter: ASTInterpreter) -> None:
        self.node: ast.FunctionDef = node
        self.closure: List[Dict[str, Any]] = closure
        self.interpreter: ASTInterpreter = interpreter

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        new_env_stack: List[Dict[str, Any]] = [frame.copy() for frame in self.closure]
        local_frame: Dict[str, Any] = {}
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
            for stmt in self.node.body:
                new_interp.visit(stmt)
        except ReturnException as ret:
            return ret.value
        return None

# Class to represent a lambda function.
class LambdaFunction:
    def __init__(self, node: ast.Lambda, closure: List[Dict[str, Any]], interpreter: ASTInterpreter) -> None:
        self.node: ast.Lambda = node
        self.closure: List[Dict[str, Any]] = closure
        self.interpreter: ASTInterpreter = interpreter

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        new_env_stack: List[Dict[str, Any]] = [frame.copy() for frame in self.closure]
        local_frame: Dict[str, Any] = {}
        if len(args) < len(self.node.args.args):
            raise TypeError("Not enough arguments for lambda")
        if len(args) > len(self.node.args.args):
            raise TypeError("Too many arguments for lambda")
        if kwargs:
            raise TypeError("Keyword arguments are not supported in lambda")
        for i, arg in enumerate(self.node.args.args):
            local_frame[arg.arg] = args[i]
        new_env_stack.append(local_frame)
        new_interp: ASTInterpreter = self.interpreter.spawn_from_env(new_env_stack)
        return new_interp.visit(self.node.body)

# The main function to interpret an AST.
def interpret_ast(ast_tree: ast.AST, allowed_modules: List[str], source: Optional[str] = None) -> Any:
    """
    Interpret a Python AST with a restricted set of allowed modules.
    
    :param ast_tree: The abstract syntax tree to interpret.
    :param allowed_modules: A list of module names that are allowed.
    :param source: The original source code (for detailed error context), if available.
    :return: The result of interpreting the AST.
    """
    interpreter: ASTInterpreter = ASTInterpreter(allowed_modules, source=source)
    return interpreter.visit(ast_tree)

# A helper function which takes a Python code string and a list of allowed module names,
# then parses and interprets the code.
def interpret_code(source_code: str, allowed_modules: List[str]) -> Any:
    """
    Interpret a Python source code string with a restricted set of allowed modules.
    
    :param source_code: The Python source code to interpret.
    :param allowed_modules: A list of module names that are allowed.
    :return: The result of interpreting the source code.
    """
    tree: ast.AST = ast.parse(source_code)
    return interpret_ast(tree, allowed_modules, source=source_code)

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
        tree_2: ast.AST = ast.parse(source_code_2)
        print("Source code parsed successfully")
        # Allow both math and numpy.
        result_2: Any = interpret_ast(tree_2, allowed_modules=["math", "numpy"], source=source_code_2)
        print("Result:", result_2)
    except Exception as e:
        print("Interpreter error:", e)