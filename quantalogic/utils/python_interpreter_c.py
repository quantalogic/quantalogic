import asyncio
import builtins
import dis
import textwrap
from typing import Any, Dict, List, Optional, Tuple
import types

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

class BytecodeInterpreter:
    def __init__(
        self, allowed_modules: List[str], env_stack: Optional[List[Dict[str, Any]]] = None, source: Optional[str] = None
    ) -> None:
        self.allowed_modules: List[str] = allowed_modules
        self.modules: Dict[str, Any] = {mod: __import__(mod) for mod in allowed_modules}
        self.stack: List[Any] = []  # Execution stack
        self.frames: List[Dict[str, Any]] = []  # Call stack for frames
        self.ip: int = 0  # Instruction pointer
        self.loop = None  # For async operations
        self.block_stack: List[Tuple[str, int]] = []  # For loops, try blocks
        self.cells: Dict[str, Any] = {}  # For closures

        if env_stack is None:
            self.env_stack: List[Dict[str, Any]] = [{}]
            self.env_stack[0].update(self.modules)
            safe_builtins: Dict[str, Any] = dict(vars(builtins))
            safe_builtins["__import__"] = self.safe_import
            safe_builtins.update({
                "enumerate": enumerate, "zip": zip, "sum": sum, "min": min, "max": max,
                "abs": abs, "round": round, "str": str, "repr": repr, "id": id,
                "type": type, "isinstance": isinstance, "issubclass": issubclass,
                "Exception": Exception, "ZeroDivisionError": ZeroDivisionError,
                "ValueError": ValueError, "TypeError": TypeError,
                "ExceptionGroup": ExceptionGroup,
            })
            if "set" not in safe_builtins:
                safe_builtins["set"] = set
            self.env_stack[0]["__builtins__"] = safe_builtins
            self.env_stack[0].update(safe_builtins)
        else:
            self.env_stack = env_stack

        self.source_lines = source.splitlines() if source else None
        if "decimal" in self.modules:
            dec = self.modules["decimal"]
            self.env_stack[0]["Decimal"] = dec.Decimal
            self.env_stack[0]["getcontext"] = dec.getcontext
            self.env_stack[0]["setcontext"] = dec.setcontext
            self.env_stack[0]["localcontext"] = dec.localcontext
            self.env_stack[0]["Context"] = dec.Context

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

    def spawn_from_env(self, env_stack: List[Dict[str, Any]]) -> "BytecodeInterpreter":
        new_interp = BytecodeInterpreter(
            self.allowed_modules, env_stack, source="\n".join(self.source_lines) if self.source_lines else None
        )
        new_interp.loop = self.loop
        new_interp.cells = self.cells.copy()
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

    async def run(self, code_obj: types.CodeType) -> Any:
        instructions = list(dis.get_instructions(code_obj))
        self.ip = 0
        last_value = None
        exception_state = None

        while self.ip < len(instructions):
            instr = instructions[self.ip]
            opcode = instr.opname
            argval = instr.argval
            arg = instr.arg
            lineno = instr.starts_line or (self.ip > 0 and instructions[self.ip - 1].starts_line) or 1

            try:
                if opcode == "RESUME":
                    pass
                elif opcode == "LOAD_CONST":
                    self.stack.append(argval)
                elif opcode == "LOAD_NAME":
                    self.stack.append(self.get_variable(argval))
                elif opcode == "STORE_NAME":
                    self.set_variable(argval, self.stack.pop())
                elif opcode == "LOAD_FAST":
                    self.stack.append(self.env_stack[-1][argval])
                elif opcode == "STORE_FAST":
                    self.env_stack[-1][argval] = self.stack.pop()
                elif opcode == "LOAD_GLOBAL":
                    self.stack.append(self.env_stack[0][argval])
                elif opcode == "STORE_GLOBAL":
                    self.env_stack[0][argval] = self.stack.pop()
                elif opcode == "BINARY_ADD":
                    right = self.stack.pop()
                    left = self.stack.pop()
                    self.stack.append(left + right)
                elif opcode == "BINARY_SUBTRACT":
                    right = self.stack.pop()
                    left = self.stack.pop()
                    self.stack.append(left - right)
                elif opcode == "BINARY_MULTIPLY":
                    right = self.stack.pop()
                    left = self.stack.pop()
                    self.stack.append(left * right)
                elif opcode == "BINARY_TRUE_DIVIDE":
                    right = self.stack.pop()
                    left = self.stack.pop()
                    self.stack.append(left / right)
                elif opcode == "BINARY_SUBSCR":
                    index = self.stack.pop()
                    obj = self.stack.pop()
                    self.stack.append(obj[index])
                elif opcode == "STORE_SUBSCR":
                    index = self.stack.pop()
                    obj = self.stack.pop()
                    value = self.stack.pop()
                    obj[index] = value
                elif opcode == "COMPARE_OP":
                    right = self.stack.pop()
                    left = self.stack.pop()
                    if argval == "==":
                        self.stack.append(left == right)
                    elif argval == "<":
                        self.stack.append(left < right)
                    elif argval == ">":
                        self.stack.append(left > right)
                    elif argval == "!=":
                        self.stack.append(left != right)
                    elif argval == "in":
                        self.stack.append(left in right)
                    else:
                        raise NotImplementedError(f"Compare op {argval} not supported")
                elif opcode == "POP_JUMP_IF_FALSE":
                    if not self.stack.pop():
                        self.ip = arg
                        continue
                elif opcode == "POP_JUMP_IF_TRUE":
                    if self.stack.pop():
                        self.ip = arg
                        continue
                elif opcode == "JUMP_FORWARD":
                    self.ip += arg
                    continue
                elif opcode == "JUMP_ABSOLUTE":
                    self.ip = arg
                    continue
                elif opcode == "JUMP_IF_TRUE_OR_POP":
                    if self.stack[-1]:
                        self.ip = arg
                        continue
                    else:
                        self.stack.pop()
                elif opcode == "JUMP_IF_FALSE_OR_POP":
                    if not self.stack[-1]:
                        self.ip = arg
                        continue
                    else:
                        self.stack.pop()
                elif opcode == "POP_TOP":
                    self.stack.pop()
                elif opcode == "RETURN_VALUE":
                    raise ReturnException(self.stack.pop())
                elif opcode == "CALL_FUNCTION":
                    nargs = instr.arg
                    args = [self.stack.pop() for _ in range(nargs)][::-1]
                    func = self.stack.pop()
                    if self.stack and self.stack[-1] is None:
                        self.stack.pop()
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args)
                    else:
                        result = func(*args)
                        if asyncio.iscoroutine(result):
                            result = await result
                    self.stack.append(result)
                elif opcode == "CALL_FUNCTION_KW":
                    nargs = instr.arg
                    kw_names = self.stack.pop()
                    kw_values = [self.stack.pop() for _ in range(len(kw_names))][::-1]
                    args = [self.stack.pop() for _ in range(nargs)][::-1]
                    kwargs = dict(zip(kw_names, kw_values))
                    func = self.stack.pop()
                    if self.stack and self.stack[-1] is None:
                        self.stack.pop()
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                        if asyncio.iscoroutine(result):
                            result = await result
                    self.stack.append(result)
                elif opcode == "CALL":
                    nargs = instr.arg
                    if self.stack[-nargs - 1] is None:  # Check for KW_NAMES
                        kw_names = self.stack.pop(-nargs - 2)
                        kw_values = [self.stack.pop() for _ in range(len(kw_names))][::-1]
                        args = [self.stack.pop() for _ in range(nargs - len(kw_names))][::-1]
                        kwargs = dict(zip(kw_names, kw_values))
                    else:
                        args = [self.stack.pop() for _ in range(nargs)][::-1]
                        kwargs = {}
                    func = self.stack.pop()
                    if self.stack and self.stack[-1] is None:
                        self.stack.pop()
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                        if asyncio.iscoroutine(result):
                            result = await result
                    self.stack.append(result)
                elif opcode == "MAKE_FUNCTION":
                    flags = instr.arg
                    code = self.stack.pop()  # Code object
                    name = self.stack.pop()  # Function name
                    if flags & 0x08:  # Default arguments
                        defaults = self.stack.pop()
                    else:
                        defaults = ()
                    if flags & 0x04:  # Closure
                        closure = self.stack.pop()
                        for i, cell in enumerate(closure):
                            self.cells[code.co_freevars[i]] = cell
                    func = Function(code, self, name, defaults)
                    self.stack.append(func)
                elif opcode == "BUILD_LIST":
                    nargs = instr.arg
                    items = [self.stack.pop() for _ in range(nargs)][::-1]
                    self.stack.append(items)
                elif opcode == "BUILD_TUPLE":
                    nargs = instr.arg
                    items = [self.stack.pop() for _ in range(nargs)][::-1]
                    self.stack.append(tuple(items))
                elif opcode == "BUILD_MAP":
                    nargs = instr.arg
                    items = [self.stack.pop() for _ in range(nargs * 2)][::-1]
                    self.stack.append(dict(zip(items[::2], items[1::2])))
                elif opcode == "BUILD_CONST_KEY_MAP":
                    nargs = instr.arg
                    keys = self.stack.pop()  # Tuple of constant keys
                    values = [self.stack.pop() for _ in range(nargs)][::-1]
                    self.stack.append(dict(zip(keys, values)))
                elif opcode == "UNPACK_SEQUENCE":
                    nargs = instr.arg
                    sequence = self.stack.pop()
                    for item in reversed(sequence):
                        self.stack.append(item)
                elif opcode == "FOR_ITER":
                    iterator = self.stack[-1]
                    try:
                        if hasattr(iterator, '__aiter__'):
                            value = await anext(iterator)
                        else:
                            value = next(iterator)
                        self.stack.append(value)
                    except StopIteration:
                        self.stack.pop()  # Remove iterator
                        self.ip = arg
                        continue
                elif opcode == "LOAD_ATTR":
                    obj = self.stack.pop()
                    self.stack.append(getattr(obj, argval))
                elif opcode == "STORE_ATTR":
                    obj = self.stack.pop()
                    value = self.stack.pop()
                    setattr(obj, argval, value)
                elif opcode == "GET_ITER":
                    self.stack[-1] = iter(self.stack[-1])
                elif opcode == "RAISE_VARARGS":
                    nargs = instr.arg
                    if nargs == 1:
                        exc = self.stack.pop()
                        raise exc
                elif opcode == "SETUP_FINALLY":
                    self.block_stack.append(("finally", arg))
                elif opcode == "SETUP_LOOP":
                    self.block_stack.append(("loop", arg))
                elif opcode == "POP_BLOCK":
                    if self.block_stack:
                        self.block_stack.pop()
                elif opcode == "END_FINALLY":
                    if exception_state:
                        exception_state = None
                elif opcode == "POP_EXCEPT":
                    if exception_state:
                        self.stack.pop()  # Remove exception
                        exception_state = None
                elif opcode == "MATCH_MAPPING":
                    value = self.stack[-1]
                    self.stack.append(isinstance(value, dict))
                elif opcode == "MATCH_SEQUENCE":
                    value = self.stack[-1]
                    self.stack.append(isinstance(value, (list, tuple)))
                elif opcode == "MATCH_KEYS":
                    keys = self.stack.pop()
                    value = self.stack[-1]
                    if not isinstance(value, dict):
                        self.stack.append(None)
                    else:
                        missing = [k for k in keys if k not in value]
                        if missing:
                            self.stack.append(None)
                        else:
                            self.stack.append(tuple(value[k] for k in keys))
                elif opcode == "LOAD_METHOD":
                    obj = self.stack.pop()
                    method = getattr(obj, argval)
                    self.stack.append(method)
                    self.stack.append(obj)
                elif opcode == "CALL_METHOD":
                    nargs = instr.arg
                    args = [self.stack.pop() for _ in range(nargs)][::-1]
                    obj = self.stack.pop()
                    method = self.stack.pop()
                    if self.stack and self.stack[-1] is None:
                        self.stack.pop()
                    result = method(*args)
                    if asyncio.iscoroutine(result):
                        result = await result
                    self.stack.append(result)
                elif opcode == "WITH_EXCEPT_START":
                    exc = self.stack[-1]
                    if isinstance(exc, ExceptionGroup):
                        self.stack.append(exc)
                    else:
                        self.stack.append(exc)
                elif opcode == "YIELD_VALUE":
                    value = self.stack.pop()
                    raise NotImplementedError("Generators via YIELD_VALUE are not fully supported yet")
                elif opcode == "IMPORT_NAME":
                    level = self.stack.pop()
                    fromlist = self.stack.pop()
                    name = argval
                    module = self.safe_import(name, fromlist=fromlist, level=level)
                    self.stack.append(module)
                elif opcode == "IMPORT_FROM":
                    module = self.stack[-1]
                    self.stack.append(getattr(module, argval))
                elif opcode == "LOAD_CLOSURE":
                    name = argval
                    if name in self.cells:
                        self.stack.append(self.cells[name])
                    else:
                        self.cells[name] = {}
                        self.stack.append(self.cells[name])
                elif opcode == "LOAD_DEREF":
                    name = argval
                    if name in self.cells:
                        self.stack.append(self.cells[name])
                    else:
                        raise NameError(f"Free variable '{name}' referenced before assignment in enclosing scope")
                elif opcode == "STORE_DEREF":
                    name = argval
                    value = self.stack.pop()
                    self.cells[name] = value
                elif opcode == "MAKE_CELL":
                    name = argval
                    if name not in self.cells:
                        self.cells[name] = {}
                elif opcode == "PUSH_NULL":
                    self.stack.append(None)
                elif opcode == "KW_NAMES":
                    self.stack.append(argval)  # Push tuple of keyword names
                else:
                    raise NotImplementedError(f"Opcode {opcode} not implemented")

                self.ip += 1
            except (ReturnException, BreakException, ContinueException):
                raise
            except Exception as e:
                context_line = self.source_lines[lineno - 1] if self.source_lines and lineno <= len(self.source_lines) else ""
                if self.block_stack and self.block_stack[-1][0] == "finally":
                    self.ip = self.block_stack[-1][1]
                    exception_state = e
                    self.stack.append(e)
                    continue
                elif self.block_stack and self.block_stack[-1][0] == "loop":
                    self.ip = self.block_stack[-1][1]
                    continue
                raise WrappedException(
                    f"Error line {lineno}, col 0:\n{context_line}\nDescription: {str(e)}",
                    e, lineno, 0, context_line
                ) from e

        return last_value

class Function:
    def __init__(self, code: types.CodeType, interpreter: 'BytecodeInterpreter', name: str, defaults: Tuple) -> None:
        self.code = code
        self.interpreter = interpreter
        self.name = name
        self.defaults = defaults
        self.closure = interpreter.env_stack[:]

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        new_env_stack = self.closure[:]
        local_frame = {}
        arg_names = self.code.co_varnames[:self.code.co_argcount]
        num_pos = len(arg_names)

        for i, arg in enumerate(args):
            if i < num_pos:
                local_frame[arg_names[i]] = arg
            else:
                raise TypeError(f"Function '{self.name}' takes {num_pos} positional arguments but {len(args)} were given")

        if self.defaults:
            for param, default in zip(arg_names[-len(self.defaults):], self.defaults):
                if param not in local_frame:
                    local_frame[param] = default

        for kw_name, kw_value in kwargs.items():
            if kw_name in arg_names:
                if kw_name in local_frame:
                    raise TypeError(f"Function '{self.name}' got multiple values for argument '{kw_name}'")
                local_frame[kw_name] = kw_value
            else:
                raise TypeError(f"Function '{self.name}' got an unexpected keyword argument '{kw_name}'")

        missing_args = [param for param in arg_names if param not in local_frame]
        if missing_args:
            raise TypeError(f"Function '{self.name}' missing required arguments: {', '.join(missing_args)}")

        new_env_stack.append(local_frame)
        new_interp = self.interpreter.spawn_from_env(new_env_stack)
        try:
            return await new_interp.run(self.code)
        except ReturnException as ret:
            return ret.value

    def __get__(self, instance: Any, owner: Any):
        if instance is None:
            return self
        async def method(*args: Any, **kwargs: Any) -> Any:
            return await self(instance, *args, **kwargs)
        method.__self__ = instance
        return method

def interpret_ast(ast_tree: Any, allowed_modules: List[str], source: str = "") -> Any:
    if not isinstance(ast_tree, types.CodeType):
        code_obj = compile(ast_tree, "<string>", "exec")
    else:
        code_obj = ast_tree

    interpreter = BytecodeInterpreter(allowed_modules=allowed_modules, source=source)

    async def run_interpreter():
        result = await interpreter.run(code_obj)
        if asyncio.iscoroutine(result):
            return await result
        elif hasattr(result, '__aiter__'):
            return [val async for val in result]
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
    code_obj = compile(dedented_source, "<string>", "exec")
    return interpret_ast(code_obj, allowed_modules, source=dedented_source)

if __name__ == "__main__":
    print("Script is running!")

    source_code_1 = """
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
        result_1 = interpret_code(source_code_1, allowed_modules=[])
        print("Result:", result_1)  # Expected: 31
    except Exception as e:
        print("Interpreter error:", e)

    source_code_2 = """
import asyncio

async def delay_square(x, delay=1):
    await asyncio.sleep(delay)
    return x * x

result = delay_square(5)
"""
    print("Example 2 (async function):")
    try:
        result_2 = interpret_code(source_code_2, allowed_modules=["asyncio"])
        print("Result:", result_2)  # Expected: 25
    except Exception as e:
        print("Interpreter error:", e)

    source_code_3 = """
f = lambda x, y=2, *args, z=3, **kwargs: x + y + z + sum(args) + sum(kwargs.values())
result = f(1, 4, 5, z=6, w=7)
"""
    print("Example 3 (lambda with defaults and kwargs):")
    try:
        result_3 = interpret_code(source_code_3, allowed_modules=[])
        print("Result:", result_3)  # Expected: 23
    except Exception as e:
        print("Interpreter error:", e)

    source_code_4 = """
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
        result_4 = interpret_code(source_code_4, allowed_modules=[])
        print("Result:", result_4)  # Expected: "List of 10 and 20"
    except Exception as e:
        print("Interpreter error:", e)

    source_code_5 = """
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
        result_5 = interpret_code(source_code_5, allowed_modules=[])
        print("Result:", result_5)  # Expected: "Caught ValueError"
    except Exception as e:
        print("Interpreter error:", e)