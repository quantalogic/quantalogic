import ast

# Exception used to signal a "return" from a function call.
class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

# Exceptions used for loop control.
class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

# The main interpreter class.
class ASTInterpreter:
    def __init__(self, allowed_modules, env_stack=None):
        self.allowed_modules = allowed_modules
        self.modules = {}
        # Import only the allowed modules.
        for mod in allowed_modules:
            self.modules[mod] = __import__(mod)
        if env_stack is None:
            # Create a global environment (first frame) with allowed modules.
            self.env_stack = [{}]
            self.env_stack[0].update(self.modules)
            # Replace __import__ in __builtins__ with our safe_import.
            safe_builtins = {}
            for name in dir(__builtins__):
                if name == "__import__":
                    safe_builtins[name] = self.safe_import
                else:
                    safe_builtins[name] = getattr(__builtins__, name)
            self.env_stack[0]["__builtins__"] = safe_builtins
        else:
            self.env_stack = env_stack

    # This safe __import__ only allows modules explicitly provided.
    def safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        if name not in self.modules:
            raise ImportError(f"Module {name} is not allowed.")
        return self.modules[name]

    # Helper: create a new interpreter instance using a given environment stack.
    def spawn_from_env(self, env_stack):
        return ASTInterpreter(self.allowed_modules, env_stack)

    # Look up a variable in the chain of environment frames.
    def get_variable(self, name):
        for frame in reversed(self.env_stack):
            if name in frame:
                return frame[name]
        raise NameError(f"Name {name} is not defined.")

    # Always assign to the most local environment.
    def set_variable(self, name, value):
        self.env_stack[-1][name] = value

    # Used for assignment targets. This handles names and destructuring.
    def assign(self, target, value):
        if isinstance(target, ast.Name):
            self.set_variable(target.id, value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            if not isinstance(value, (list, tuple)):
                raise TypeError("Can only unpack an iterable")
            if len(target.elts) != len(value):
                raise ValueError("Unpacking mismatch")
            for elt, val in zip(target.elts, value):
                self.assign(elt, val)
        elif isinstance(target, ast.Attribute):
            obj = self.visit(target.value)
            setattr(obj, target.attr, value)
        else:
            raise Exception("Unsupported assignment target type: " + str(type(target)))

    # Main visitor dispatch.
    def visit(self, node):
        method_name = "visit_" + node.__class__.__name__
        method = getattr(self, method_name, self.generic_visit)
        return method(node)

    # Fallback for unsupported nodes.
    def generic_visit(self, node):
        raise Exception(f"Unsupported AST node type: {node.__class__.__name__}")

    # --- Visitor for Import nodes ---
    def visit_Import(self, node):
        """
        Process an import statement.
        Only allowed modules can be imported.
        """
        for alias in node.names:
            module_name = alias.name
            asname = alias.asname if alias.asname is not None else module_name
            if module_name not in self.modules:
                raise ImportError(f"Module {module_name} is not allowed.")
            self.set_variable(asname, self.modules[module_name])

    # --- Visitor for ListComprehension nodes ---
    def visit_ListComp(self, node):
        """
        Process a list comprehension.
          [elt for ... in ... if ...]
        The comprehension is executed in a new local frame that inherits the
        current environment.
        """
        result = []
        # Copy the current top-level frame for the comprehension scope.
        base_frame = self.env_stack[-1].copy()
        self.env_stack.append(base_frame)
        def rec(gen_idx):
            if gen_idx == len(node.generators):
                result.append(self.visit(node.elt))
            else:
                comp = node.generators[gen_idx]
                iterable = self.visit(comp.iter)
                for item in iterable:
                    # Push a new frame that inherits the current comprehension scope.
                    new_frame = self.env_stack[-1].copy()
                    self.env_stack.append(new_frame)
                    self.assign(comp.target, item)
                    if all(self.visit(if_clause) for if_clause in comp.ifs):
                        rec(gen_idx + 1)
                    self.env_stack.pop()
        rec(0)
        self.env_stack.pop()
        return result

    # --- Other node visitors below ---
    def visit_Module(self, node):
        result = None
        for stmt in node.body:
            result = self.visit(stmt)
        return result

    def visit_Expr(self, node):
        return self.visit(node.value)

    def visit_Constant(self, node):
        return node.value

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            return self.get_variable(node.id)
        elif isinstance(node.ctx, ast.Store):
            return node.id
        else:
            raise Exception("Unsupported context for Name")

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
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

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
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

    def visit_Assign(self, node):
        value = self.visit(node.value)
        for target in node.targets:
            self.assign(target, value)

    def visit_AugAssign(self, node):
        current_val = self.visit(node.target)
        right_val = self.visit(node.value)
        op = node.op
        if isinstance(op, ast.Add):
            result = current_val + right_val
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

    def visit_Compare(self, node):
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
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

    def visit_BoolOp(self, node):
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

    def visit_If(self, node):
        if self.visit(node.test):
            for stmt in node.body:
                self.visit(stmt)
        else:
            for stmt in node.orelse:
                self.visit(stmt)

    def visit_While(self, node):
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

    def visit_For(self, node):
        iter_obj = self.visit(node.iter)
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

    def visit_Break(self, node):
        raise BreakException()

    def visit_Continue(self, node):
        raise ContinueException()

    def visit_FunctionDef(self, node):
        # Capture the current env_stack for a closure.
        closure = [frame.copy() for frame in self.env_stack]
        func = Function(node, closure, self)
        self.set_variable(node.name, func)

    def visit_Call(self, node):
        func = self.visit(node.func)
        args = [self.visit(arg) for arg in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords}
        return func(*args, **kwargs)

    def visit_Return(self, node):
        value = self.visit(node.value) if node.value is not None else None
        raise ReturnException(value)

    def visit_Lambda(self, node):
        closure = [frame.copy() for frame in self.env_stack]
        return LambdaFunction(node, closure, self)

    def visit_List(self, node):
        return [self.visit(elt) for elt in node.elts]

    def visit_Tuple(self, node):
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_Dict(self, node):
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_Set(self, node):
        return set(self.visit(elt) for elt in node.elts)

    def visit_Attribute(self, node):
        value = self.visit(node.value)
        return getattr(value, node.attr)

    def visit_Subscript(self, node):
        value = self.visit(node.value)
        slice_val = self.visit(node.slice)
        return value[slice_val]

    def visit_Slice(self, node):
        lower = self.visit(node.lower) if node.lower else None
        upper = self.visit(node.upper) if node.upper else None
        step = self.visit(node.step) if node.step else None
        return slice(lower, upper, step)

    # For compatibility with older AST versions.
    def visit_Index(self, node):
        return self.visit(node.value)

# Class to represent a user-defined function.
class Function:
    def __init__(self, node, closure, interpreter):
        self.node = node
        self.closure = closure
        self.interpreter = interpreter

    def __call__(self, *args, **kwargs):
        new_env_stack = [frame.copy() for frame in self.closure]
        local_frame = {}
        # For simplicity, only positional parameters are supported.
        if len(args) < len(self.node.args.args):
            raise TypeError("Not enough arguments provided")
        for i, arg in enumerate(self.node.args.args):
            local_frame[arg.arg] = args[i]
        new_env_stack.append(local_frame)
        new_interp = self.interpreter.spawn_from_env(new_env_stack)
        try:
            for stmt in self.node.body:
                new_interp.visit(stmt)
        except ReturnException as ret:
            return ret.value
        return None

# Class to represent a lambda function.
class LambdaFunction:
    def __init__(self, node, closure, interpreter):
        self.node = node
        self.closure = closure
        self.interpreter = interpreter

    def __call__(self, *args, **kwargs):
        new_env_stack = [frame.copy() for frame in self.closure]
        local_frame = {}
        if len(args) < len(self.node.args.args):
            raise TypeError("Not enough arguments for lambda")
        for i, arg in enumerate(self.node.args.args):
            local_frame[arg.arg] = args[i]
        new_env_stack.append(local_frame)
        new_interp = self.interpreter.spawn_from_env(new_env_stack)
        return new_interp.visit(self.node.body)

# The main function: it takes an AST and a list of allowed module names.
def interpret_ast(ast_tree, allowed_modules):
    """
    Interpret a Python AST with a restricted set of allowed modules.

    Parameters:
      ast_tree (ast.AST): The abstract syntax tree to interpret.
      allowed_modules (list): A list of module names that are allowed during interpretation.

    Returns:
      The result of interpreting the AST.
    """
    interpreter = ASTInterpreter(allowed_modules)
    return interpreter.visit(ast_tree)


if __name__ == "__main__":
    print("Script is running!")
    source_code = """
import math
def square(x):
    return x * x

y = square(5)
z = math.sqrt(y)
z
"""
    # Parse source code into an AST.
    tree = ast.parse(source_code)
    # Only "math" is allowed here.
    result = interpret_ast(tree, allowed_modules=["math"])
    print("Result:", result)

    print("Second example:")

    # Define the source code with multiple operations and a list comprehension.
    source_code = """
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
    tree = ast.parse(source_code)
    print("Source code parsed successfully")
    # Allow both math and numpy.
    result = interpret_ast(tree, allowed_modules=["math", "numpy"])
    print("Result:", result)