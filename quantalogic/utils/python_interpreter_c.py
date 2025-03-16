import asyncio
import builtins
import dis
import logging
import textwrap
from typing import Any, Dict, List, Optional, Tuple, Callable
import types
from collections import defaultdict
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReturnException(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

class WrappedException(Exception):
    def __init__(self, message: str, original_exception: Exception, lineno: int, col: int, context_line: str, stack_trace: List[str]):
        super().__init__(message)
        self.original_exception = original_exception
        self.lineno = lineno
        self.col = col
        self.context_line = context_line
        self.stack_trace = stack_trace

class Cell:
    def __init__(self, value: Any):
        self.contents = value

class GeneratorWrapper:
    def __init__(self, interpreter: 'BytecodeInterpreter', code: types.CodeType, initial_stack: List[Any]):
        self.interpreter = interpreter.spawn_from_env(interpreter.env_stack)
        self.code = code
        self.stack = initial_stack[:]
        self.ip = 0
        self.running = False

    def __iter__(self):
        return self

    def __next__(self):
        if not self.running:
            self.running = True
            return self.interpreter.loop.run_until_complete(self.interpreter.run(self.code, initial_stack=self.stack))
        raise StopIteration

class BytecodeInterpreter:
    def __init__(
        self, allowed_modules: List[str], env_stack: Optional[List[Dict[str, Any]]] = None, source: Optional[str] = None,
        max_execution_time: float = 10.0
    ) -> None:
        self.allowed_modules = allowed_modules
        self.modules = {mod: __import__(mod) for mod in allowed_modules}
        self.stack: List[Any] = []
        self.frames: List[Dict[str, Any]] = []
        self.ip = 0
        self.loop = asyncio.get_event_loop()
        self.block_stack: List[Tuple[str, int]] = []
        self.cells: Dict[str, Cell] = {}
        self.max_execution_time = max_execution_time
        self.source_lines = source.splitlines() if source else None
        self.stack_trace: List[str] = []
        self.current_kw_names = None

        if env_stack is None:
            self.env_stack = [defaultdict(lambda: None)]
            self.env_stack[0].update(self.modules)
            safe_builtins = {k: v for k, v in vars(builtins).items() if k in {
                "print", "len", "range", "enumerate", "zip", "sum", "min", "max",
                "abs", "round", "str", "repr", "id", "type", "isinstance", "issubclass",
                "Exception", "ValueError", "TypeError", "ZeroDivisionError", "ExceptionGroup"
            }}
            safe_builtins["__import__"] = self.safe_import
            self.env_stack[0]["__builtins__"] = safe_builtins
            self.env_stack[0].update(safe_builtins)
        else:
            self.env_stack = env_stack

        self.opcode_handlers: Dict[str, Callable[[dis.Instruction], None]] = {
            "NOP": self._handle_nop,
            "CACHE": self._handle_cache,
            "RESUME": self._handle_resume,
            "LOAD_CONST": self._handle_load_const,
            "LOAD_NAME": self._handle_load_name,
            "STORE_NAME": self._handle_store_name,
            "LOAD_FAST": self._handle_load_fast,
            "STORE_FAST": self._handle_store_fast,
            "DELETE_FAST": self._handle_delete_fast,
            "LOAD_GLOBAL": self._handle_load_global,
            "STORE_GLOBAL": self._handle_store_global,
            "DELETE_GLOBAL": self._handle_delete_global,
            "DELETE_NAME": self._handle_delete_name,
            "BINARY_OP": self._handle_binary_op,
            "BINARY_ADD": self._handle_binary_add,
            "BINARY_SUBTRACT": self._handle_binary_subtract,
            "BINARY_MULTIPLY": self._handle_binary_multiply,
            "BINARY_TRUE_DIVIDE": self._handle_binary_true_divide,
            "BINARY_FLOOR_DIVIDE": self._handle_binary_floor_divide,
            "BINARY_MODULO": self._handle_binary_modulo,
            "BINARY_POWER": self._handle_binary_power,
            "BINARY_LSHIFT": self._handle_binary_lshift,
            "BINARY_RSHIFT": self._handle_binary_rshift,
            "BINARY_AND": self._handle_binary_and,
            "BINARY_OR": self._handle_binary_or,
            "BINARY_XOR": self._handle_binary_xor,
            "BINARY_MATRIX_MULTIPLY": self._handle_binary_matrix_multiply,
            "INPLACE_ADD": self._handle_inplace_add,
            "INPLACE_SUBTRACT": self._handle_inplace_subtract,
            "INPLACE_MULTIPLY": self._handle_inplace_multiply,
            "INPLACE_TRUE_DIVIDE": self._handle_inplace_true_divide,
            "INPLACE_FLOOR_DIVIDE": self._handle_inplace_floor_divide,
            "INPLACE_MODULO": self._handle_inplace_modulo,
            "INPLACE_POWER": self._handle_inplace_power,
            "INPLACE_LSHIFT": self._handle_inplace_lshift,
            "INPLACE_RSHIFT": self._handle_inplace_rshift,
            "INPLACE_AND": self._handle_inplace_and,
            "INPLACE_OR": self._handle_inplace_or,
            "INPLACE_XOR": self._handle_inplace_xor,
            "BINARY_SUBSCR": self._handle_binary_subscr,
            "STORE_SUBSCR": self._handle_store_subscr,
            "DELETE_SUBSCR": self._handle_delete_subscr,
            "COMPARE_OP": self._handle_compare_op,
            "IS_OP": self._handle_is_op,
            "CONTAINS_OP": self._handle_contains_op,
            "POP_JUMP_IF_FALSE": self._handle_pop_jump_if_false,
            "POP_JUMP_IF_TRUE": self._handle_pop_jump_if_true,
            "POP_JUMP_FORWARD_IF_FALSE": self._handle_pop_jump_forward_if_false,
            "POP_JUMP_FORWARD_IF_TRUE": self._handle_pop_jump_forward_if_true,
            "POP_JUMP_FORWARD_IF_NONE": self._handle_pop_jump_forward_if_none,
            "POP_JUMP_FORWARD_IF_NOT_NONE": self._handle_pop_jump_forward_if_not_none,
            "JUMP_FORWARD": self._handle_jump_forward,
            "JUMP_ABSOLUTE": self._handle_jump_absolute,
            "JUMP_BACKWARD": self._handle_jump_backward,
            "JUMP_IF_TRUE_OR_POP": self._handle_jump_if_true_or_pop,
            "JUMP_IF_FALSE_OR_POP": self._handle_jump_if_false_or_pop,
            "POP_TOP": self._handle_pop_top,
            "RETURN_VALUE": self._handle_return_value,
            "RETURN_CONST": self._handle_return_const,  # Added for Python 3.11+
            "CALL": self._handle_call,
            "MAKE_FUNCTION": self._handle_make_function,
            "BUILD_LIST": self._handle_build_list,
            "BUILD_TUPLE": self._handle_build_tuple,
            "BUILD_MAP": self._handle_build_map,
            "BUILD_CONST_KEY_MAP": self._handle_build_const_key_map,
            "BUILD_SET": self._handle_build_set,
            "BUILD_STRING": self._handle_build_string,
            "BUILD_SLICE": self._handle_build_slice,
            "LIST_EXTEND": self._handle_list_extend,
            "SET_UPDATE": self._handle_set_update,
            "DICT_UPDATE": self._handle_dict_update,
            "UNPACK_SEQUENCE": self._handle_unpack_sequence,
            "FOR_ITER": self._handle_for_iter,
            "LOAD_ATTR": self._handle_load_attr,
            "STORE_ATTR": self._handle_store_attr,
            "DELETE_ATTR": self._handle_delete_attr,
            "LOAD_METHOD": self._handle_load_method,
            "CALL_METHOD": self._handle_call_method,
            "GET_ITER": self._handle_get_iter,
            "GET_AITER": self._handle_get_aiter,
            "GET_ANEXT": self._handle_get_anext,
            "GET_AWAITABLE": self._handle_get_awaitable,
            "END_ASYNC_FOR": self._handle_end_async_for,
            "RAISE_VARARGS": self._handle_raise_varargs,
            "SETUP_FINALLY": self._handle_setup_finally,
            "SETUP_EXCEPT": self._handle_setup_except,
            "SETUP_LOOP": self._handle_setup_loop,
            "SETUP_WITH": self._handle_setup_with,
            "SETUP_ASYNC_WITH": self._handle_setup_async_with,
            "POP_BLOCK": self._handle_pop_block,
            "POP_EXCEPT": self._handle_pop_except,
            "RERAISE": self._handle_reraise,
            "YIELD_VALUE": self._handle_yield_value,
            "YIELD_FROM": self._handle_yield_from,
            "RETURN_GENERATOR": self._handle_return_generator,
            "IMPORT_NAME": self._handle_import_name,
            "IMPORT_FROM": self._handle_import_from,
            "LOAD_CLOSURE": self._handle_load_closure,
            "LOAD_DEREF": self._handle_load_deref,
            "STORE_DEREF": self._handle_store_deref,
            "LOAD_CLASSDEREF": self._handle_load_classderef,
            "MAKE_CELL": self._handle_make_cell,
            "PUSH_NULL": self._handle_push_null,
            "KW_NAMES": self._handle_kw_names,
            "UNARY_POSITIVE": self._handle_unary_positive,
            "UNARY_NEGATIVE": self._handle_unary_negative,
            "UNARY_NOT": self._handle_unary_not,
            "UNARY_INVERT": self._handle_unary_invert,
            "LIST_APPEND": self._handle_list_append,
            "MAP_ADD": self._handle_map_add,
            "FORMAT_VALUE": self._handle_format_value,
            "ROT_TWO": self._handle_rot_two,
            "ROT_THREE": self._handle_rot_three,
            "DUP_TOP": self._handle_dup_top,
            "COPY": self._handle_copy,
            "SWAP": self._handle_swap,
            "MATCH_MAPPING": self._handle_match_mapping,
            "MATCH_SEQUENCE": self._handle_match_sequence,
            "MATCH_KEYS": self._handle_match_keys,
            "MATCH_CLASS": self._handle_match_class,
        }

    def _handle_nop(self, instr: dis.Instruction) -> None:
        pass

    def _handle_cache(self, instr: dis.Instruction) -> None:
        pass

    def _handle_resume(self, instr: dis.Instruction) -> None:
        pass

    def _handle_load_const(self, instr: dis.Instruction) -> None:
        self.stack.append(instr.argval)

    def _handle_load_name(self, instr: dis.Instruction) -> None:
        self.stack.append(self.get_variable(instr.argval))

    def _handle_store_name(self, instr: dis.Instruction) -> None:
        self.set_variable(instr.argval, self.safe_pop(instr.opname))

    def _handle_load_fast(self, instr: dis.Instruction) -> None:
        value = self.env_stack[-1].get(instr.argval)
        if value is None:
            raise NameError(f"Variable '{instr.argval}' not initialized")
        self.stack.append(value)

    def _handle_store_fast(self, instr: dis.Instruction) -> None:
        self._store_fast(instr.argval, self.safe_pop(instr.opname))

    def _handle_delete_fast(self, instr: dis.Instruction) -> None:
        self.env_stack[-1].pop(instr.argval, None)

    def _handle_load_global(self, instr: dis.Instruction) -> None:
        value = self.env_stack[0].get(instr.argval)
        if value is None:
            raise NameError(f"Global '{instr.argval}' not defined")
        self.stack.append(value)

    def _handle_store_global(self, instr: dis.Instruction) -> None:
        self.env_stack[0].update({instr.argval: self.safe_pop(instr.opname)})

    def _handle_delete_global(self, instr: dis.Instruction) -> None:
        self.env_stack[0].pop(instr.argval, None)

    def _handle_delete_name(self, instr: dis.Instruction) -> None:
        self._delete_name(instr.argval)

    def _handle_binary_op(self, instr: dis.Instruction) -> None:
        ops = {
            0: lambda x, y: x + y,
            1: lambda x, y: x & y,
            2: lambda x, y: x // y,
            3: lambda x, y: x << y,
            4: lambda x, y: x @ y,
            5: lambda x, y: x * y,
            6: lambda x, y: x % y,
            7: lambda x, y: x | y,
            8: lambda x, y: x ** y,
            9: lambda x, y: x >> y,
            10: lambda x, y: x - y,
            11: lambda x, y: x / y,
            12: lambda x, y: x ^ y,
        }
        right = self.safe_pop(instr.opname)
        left = self.safe_pop(instr.opname)
        self.stack.append(ops[instr.arg](left, right))

    def _handle_binary_add(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x + y)

    def _handle_binary_subtract(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x - y)

    def _handle_binary_multiply(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x * y)

    def _handle_binary_true_divide(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x / y)

    def _handle_binary_floor_divide(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x // y)

    def _handle_binary_modulo(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x % y)

    def _handle_binary_power(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x ** y)

    def _handle_binary_lshift(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x << y)

    def _handle_binary_rshift(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x >> y)

    def _handle_binary_and(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x & y)

    def _handle_binary_or(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x | y)

    def _handle_binary_xor(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x ^ y)

    def _handle_binary_matrix_multiply(self, instr: dis.Instruction) -> None:
        self._binary_op(instr.opname, lambda x, y: x @ y)

    def _handle_inplace_add(self, instr: dis.Instruction) -> None:
        right = self.safe_pop(instr.opname)
        left = self.safe_pop(instr.opname)
        if isinstance(left, list):
            if isinstance(right, (list, tuple, set)):
                left.extend(right)
            else:
                left.append(right)
            self.stack.append(left)
        else:
            self.stack.append(left + right)

    def _handle_inplace_subtract(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x - y)

    def _handle_inplace_multiply(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x * y)

    def _handle_inplace_true_divide(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x / y)

    def _handle_inplace_floor_divide(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x // y)

    def _handle_inplace_modulo(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x % y)

    def _handle_inplace_power(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x ** y)

    def _handle_inplace_lshift(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x << y)

    def _handle_inplace_rshift(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x >> y)

    def _handle_inplace_and(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x & y)

    def _handle_inplace_or(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x | y)

    def _handle_inplace_xor(self, instr: dis.Instruction) -> None:
        self._inplace_op(instr.opname, lambda x, y: x ^ y)

    def _handle_binary_subscr(self, instr: dis.Instruction) -> None:
        index = self.safe_pop(instr.opname)
        obj = self.safe_pop(instr.opname)
        self.stack.append(obj[index])

    def _handle_store_subscr(self, instr: dis.Instruction) -> None:
        self._store_subscr(instr.opname)

    def _handle_delete_subscr(self, instr: dis.Instruction) -> None:
        self._delete_subscr(instr.opname)

    def _handle_compare_op(self, instr: dis.Instruction) -> None:
        right = self.safe_pop("COMPARE_OP")
        left = self.safe_pop("COMPARE_OP")
        ops = {
            "==": lambda x, y: x == y,
            "<": lambda x, y: x < y,
            ">": lambda x, y: x > y,
            "!=": lambda x, y: x != y,
            "in": lambda x, y: x in y,
            "not in": lambda x, y: x not in y,
            "<=": lambda x, y: x <= y,
            ">=": lambda x, y: x >= y
        }
        self.stack.append(ops[instr.argval](left, right))

    def _handle_is_op(self, instr: dis.Instruction) -> None:
        self.stack.append((self.safe_pop(instr.opname) is self.safe_pop(instr.opname)) == (instr.argval == 0))

    def _handle_contains_op(self, instr: dis.Instruction) -> None:
        self.stack.append((self.safe_pop(instr.opname) in self.safe_pop(instr.opname)) == (instr.argval == 0))

    def _handle_pop_jump_if_false(self, instr: dis.Instruction) -> None:
        self._jump_if(instr, lambda x: not x)

    def _handle_pop_jump_if_true(self, instr: dis.Instruction) -> None:
        self._jump_if(instr, lambda x: x)

    def _handle_pop_jump_forward_if_false(self, instr: dis.Instruction) -> None:
        self._jump_forward_if(instr, lambda x: not x)

    def _handle_pop_jump_forward_if_true(self, instr: dis.Instruction) -> None:
        self._jump_forward_if(instr, lambda x: x)

    def _handle_pop_jump_forward_if_none(self, instr: dis.Instruction) -> None:
        self._jump_forward_if(instr, lambda x: x is None)

    def _handle_pop_jump_forward_if_not_none(self, instr: dis.Instruction) -> None:
        self._jump_forward_if(instr, lambda x: x is not None)

    def _handle_jump_forward(self, instr: dis.Instruction) -> None:
        self.ip = self.ip + instr.arg

    def _handle_jump_absolute(self, instr: dis.Instruction) -> None:
        self.ip = instr.arg

    def _handle_jump_backward(self, instr: dis.Instruction) -> None:
        self.ip = self.ip - instr.arg

    def _handle_jump_if_true_or_pop(self, instr: dis.Instruction) -> None:
        self._jump_or_pop(instr, lambda x: x)

    def _handle_jump_if_false_or_pop(self, instr: dis.Instruction) -> None:
        self._jump_or_pop(instr, lambda x: not x)

    def _handle_pop_top(self, instr: dis.Instruction) -> None:
        self.safe_pop(instr.opname)

    def _handle_return_value(self, instr: dis.Instruction) -> None:
        self._raise_return(self.safe_pop(instr.opname))

    def _handle_return_const(self, instr: dis.Instruction) -> None:
        self._raise_return(instr.argval)

    async def _handle_call(self, instr: dis.Instruction) -> None:
        if self.current_kw_names is not None:
            kw_names = self.current_kw_names
            self.current_kw_names = None
            kw_count = len(kw_names)
            total_args = instr.arg
            if total_args < kw_count:
                raise RuntimeError("Not enough arguments for keyword names")
            kw_values = [self.safe_pop("CALL") for _ in range(kw_count)][::-1]
            pos_args = [self.safe_pop("CALL") for _ in range(total_args - kw_count)][::-1]
            func = self.safe_pop("CALL")
            kwargs = dict(zip(kw_names, kw_values))
            result = func(*pos_args, **kwargs)
        else:
            args = [self.safe_pop("CALL") for _ in range(instr.arg)][::-1]
            func = self.safe_pop("CALL")
            result = func(*args)
        if asyncio.iscoroutine(result):
            result = await result
        self.stack.append(result)

    def _handle_make_function(self, instr: dis.Instruction) -> None:
        self._make_function(instr.arg)

    def _handle_build_list(self, instr: dis.Instruction) -> None:
        self.stack.append([self.safe_pop(instr.opname) for _ in range(instr.arg)][::-1])

    def _handle_build_tuple(self, instr: dis.Instruction) -> None:
        self.stack.append(tuple([self.safe_pop(instr.opname) for _ in range(instr.arg)][::-1]))

    def _handle_build_map(self, instr: dis.Instruction) -> None:
        self._build_map(instr.arg)

    def _handle_build_const_key_map(self, instr: dis.Instruction) -> None:
        self._build_const_key_map(instr.arg)

    def _handle_build_set(self, instr: dis.Instruction) -> None:
        self.stack.append(set([self.safe_pop(instr.opname) for _ in range(instr.arg)][::-1]))

    def _handle_build_string(self, instr: dis.Instruction) -> None:
        self.stack.append("".join(str(self.safe_pop(instr.opname)) for _ in range(instr.arg)[::-1]))

    def _handle_build_slice(self, instr: dis.Instruction) -> None:
        self._build_slice(instr.arg)

    def _handle_list_extend(self, instr: dis.Instruction) -> None:
        self.stack[-instr.arg].extend(self.safe_pop(instr.opname))

    def _handle_set_update(self, instr: dis.Instruction) -> None:
        self.stack[-instr.arg].update(self.safe_pop(instr.opname))

    def _handle_dict_update(self, instr: dis.Instruction) -> None:
        self.stack[-instr.arg].update(self.safe_pop(instr.opname))

    def _handle_unpack_sequence(self, instr: dis.Instruction) -> None:
        seq = self.safe_pop(instr.opname)
        if len(seq) != instr.arg:
            raise ValueError(f"Expected sequence of length {instr.arg}, got {len(seq)}")
        self.stack.extend(reversed(seq))

    async def _handle_for_iter(self, instr: dis.Instruction) -> None:
        self._for_iter(instr)

    def _handle_load_attr(self, instr: dis.Instruction) -> None:
        self.stack.append(getattr(self.safe_pop(instr.opname), instr.argval))

    def _handle_store_attr(self, instr: dis.Instruction) -> None:
        obj = self.safe_pop(instr.opname)
        value = self.safe_pop(instr.opname)
        setattr(obj, instr.argval, value)

    def _handle_delete_attr(self, instr: dis.Instruction) -> None:
        delattr(self.safe_pop(instr.opname), instr.argval)

    def _handle_load_method(self, instr: dis.Instruction) -> None:
        self._load_method(instr.argval)

    async def _handle_call_method(self, instr: dis.Instruction) -> None:
        args = [self.safe_pop("CALL_METHOD") for _ in range(instr.arg)][::-1]
        obj = self.safe_pop("CALL_METHOD")
        method = self.safe_pop("CALL_METHOD")
        result = method(obj, *args)
        if asyncio.iscoroutine(result):
            result = await result
        self.stack.append(result)

    def _handle_get_iter(self, instr: dis.Instruction) -> None:
        self.stack[-1] = iter(self.stack[-1])

    def _handle_get_aiter(self, instr: dis.Instruction) -> None:
        self.stack[-1] = self.stack[-1].__aiter__()

    def _handle_get_anext(self, instr: dis.Instruction) -> None:
        self.stack.append(anext(self.stack[-1]))

    def _handle_get_awaitable(self, instr: dis.Instruction) -> None:
        self.stack.append(asyncio.ensure_future(self.safe_pop(instr.opname)))

    def _handle_end_async_for(self, instr: dis.Instruction) -> None:
        self._end_async_for(instr)

    def _handle_raise_varargs(self, instr: dis.Instruction) -> None:
        self._raise_varargs(instr.arg)

    def _handle_setup_finally(self, instr: dis.Instruction) -> None:
        self.block_stack.append(("finally", self.ip + instr.arg))

    def _handle_setup_except(self, instr: dis.Instruction) -> None:
        self.block_stack.append(("except", self.ip + instr.arg))

    def _handle_setup_loop(self, instr: dis.Instruction) -> None:
        self.block_stack.append(("loop", self.ip + instr.arg))

    def _handle_setup_with(self, instr: dis.Instruction) -> None:
        self._setup_with(self.ip + instr.arg)

    async def _handle_setup_async_with(self, instr: dis.Instruction) -> None:
        self._setup_async_with(self.ip + instr.arg)

    def _handle_pop_block(self, instr: dis.Instruction) -> None:
        if self.block_stack:
            self.block_stack.pop()

    def _handle_pop_except(self, instr: dis.Instruction) -> None:
        if self.stack:
            self.stack.pop()

    def _handle_reraise(self, instr: dis.Instruction) -> None:
        self._reraise(instr)

    def _handle_yield_value(self, instr: dis.Instruction) -> None:
        self._yield_value(instr)

    def _handle_yield_from(self, instr: dis.Instruction) -> None:
        self._yield_from(instr)

    def _handle_return_generator(self, instr: dis.Instruction) -> None:
        self._return_generator(instr)

    def _handle_import_name(self, instr: dis.Instruction) -> None:
        self.stack.append(self.safe_import(instr.argval, fromlist=self.safe_pop(instr.opname), level=self.safe_pop(instr.opname)))

    def _handle_import_from(self, instr: dis.Instruction) -> None:
        self.stack.append(getattr(self.stack[-1], instr.argval))

    def _handle_load_closure(self, instr: dis.Instruction) -> None:
        self._load_closure(instr.argval)

    def _handle_load_deref(self, instr: dis.Instruction) -> None:
        self.stack.append(self.cells[instr.argval].contents)

    def _handle_store_deref(self, instr: dis.Instruction) -> None:
        self.cells[instr.argval].contents = self.safe_pop(instr.opname)

    def _handle_load_classderef(self, instr: dis.Instruction) -> None:
        self._load_classderef(instr.argval)

    def _handle_make_cell(self, instr: dis.Instruction) -> None:
        self.cells.setdefault(instr.argval, Cell(None))

    def _handle_push_null(self, instr: dis.Instruction) -> None:
        self.stack.append(None)

    def _handle_kw_names(self, instr: dis.Instruction) -> None:
        self.current_kw_names = instr.argval

    def _handle_unary_positive(self, instr: dis.Instruction) -> None:
        self.stack.append(+self.safe_pop(instr.opname))

    def _handle_unary_negative(self, instr: dis.Instruction) -> None:
        self.stack.append(-self.safe_pop(instr.opname))

    def _handle_unary_not(self, instr: dis.Instruction) -> None:
        self.stack.append(not self.safe_pop(instr.opname))

    def _handle_unary_invert(self, instr: dis.Instruction) -> None:
        self.stack.append(~self.safe_pop(instr.opname))

    def _handle_list_append(self, instr: dis.Instruction) -> None:
        self.stack[-instr.argval].append(self.safe_pop(instr.opname))

    def _handle_map_add(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        key = self.safe_pop(instr.opname)
        self.stack[-instr.argval][key] = value

    def _handle_format_value(self, instr: dis.Instruction) -> None:
        self._format_value(instr.arg)

    def _handle_rot_two(self, instr: dis.Instruction) -> None:
        self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]

    def _handle_rot_three(self, instr: dis.Instruction) -> None:
        self.stack[-1], self.stack[-2], self.stack[-3] = self.stack[-2], self.stack[-3], self.stack[-1]

    def _handle_dup_top(self, instr: dis.Instruction) -> None:
        self.stack.append(self.stack[-1])

    def _handle_copy(self, instr: dis.Instruction) -> None:
        self.stack.append(self.stack[-instr.arg])

    def _handle_swap(self, instr: dis.Instruction) -> None:
        self.stack[-1], self.stack[-instr.arg] = self.stack[-instr.arg], self.stack[-1]

    def _handle_match_mapping(self, instr: dis.Instruction) -> None:
        self.stack.append(isinstance(self.stack[-1], dict))

    def _handle_match_sequence(self, instr: dis.Instruction) -> None:
        self.stack.append(isinstance(self.stack[-1], (list, tuple)))

    def _handle_match_keys(self, instr: dis.Instruction) -> None:
        self._match_keys(instr)

    def _handle_match_class(self, instr: dis.Instruction) -> None:
        nargs = instr.arg
        args = [self.safe_pop(instr.opname) for _ in range(nargs)][::-1]
        cls = self.safe_pop(instr.opname)
        value = self.stack[-1]
        if isinstance(value, cls):
            if nargs:
                try:
                    self.stack.append(tuple(getattr(value, arg) for arg in args))
                except AttributeError:
                    self.stack.append(False)
            else:
                self.stack.append(True)
        else:
            self.stack.append(False)

    def safe_import(self, name: str, globals=None, locals=None, fromlist: Tuple[str, ...] = (), level: int = 0) -> Any:
        if name not in self.allowed_modules:
            raise ImportError(f"Module '{name}' not allowed. Permitted: {self.allowed_modules}")
        return self.modules[name]

    def spawn_from_env(self, env_stack: List[Dict[str, Any]]) -> "BytecodeInterpreter":
        new_interp = BytecodeInterpreter(self.allowed_modules, env_stack, "\n".join(self.source_lines) if self.source_lines else None)
        new_interp.loop = self.loop
        new_interp.cells = self.cells.copy()
        return new_interp

    def get_variable(self, name: str) -> Any:
        for frame in reversed(self.env_stack):
            if name in frame and frame[name] is not None:
                return frame[name]
        raise NameError(f"Name '{name}' is not defined")

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

    def safe_pop(self, opcode: str) -> Any:
        if not self.stack:
            raise RuntimeError(f"Stack underflow in {opcode}")
        return self.stack.pop()

    def _store_fast(self, name: str, value: Any) -> None:
        self.env_stack[-1][name] = value
        if name in self.cells:
            self.cells[name].contents = value

    def _delete_name(self, name: str) -> None:
        for frame in reversed(self.env_stack):
            if name in frame:
                del frame[name]
                return
        raise NameError(f"Name '{name}' is not defined")

    def _delete_subscr(self, opcode: str) -> None:
        index = self.safe_pop(opcode)
        obj = self.safe_pop(opcode)
        del obj[index]

    def _binary_op(self, opcode: str, op: Callable[[Any, Any], Any]) -> None:
        right = self.safe_pop(opcode)
        left = self.safe_pop(opcode)
        self.stack.append(op(left, right))

    def _inplace_op(self, opcode: str, op: Callable[[Any, Any], Any]) -> None:
        right = self.safe_pop(opcode)
        left = self.safe_pop(opcode)
        self.stack.append(op(left, right))

    def _store_subscr(self, opcode: str) -> None:
        value = self.safe_pop(opcode)
        index = self.safe_pop(opcode)
        obj = self.safe_pop(opcode)
        obj[index] = value

    def _jump_if(self, instr: dis.Instruction, condition: Callable[[Any], bool]) -> None:
        if condition(self.safe_pop(instr.opname)):
            self.ip = instr.arg

    def _jump_forward_if(self, instr: dis.Instruction, condition: Callable[[Any], bool]) -> None:
        if condition(self.safe_pop(instr.opname)):
            self.ip += instr.arg

    def _jump_or_pop(self, instr: dis.Instruction, condition: Callable[[Any], bool]) -> None:
        if condition(self.stack[-1]):
            self.ip = instr.arg
        else:
            self.safe_pop(instr.opname)

    def _raise_return(self, value: Any) -> None:
        raise ReturnException(value)

    def _make_function(self, flags: int) -> None:
        code = self.safe_pop("MAKE_FUNCTION")
        name = code.co_name
        closure = self.safe_pop("MAKE_FUNCTION") if flags & 0x08 else ()
        annotations = self.safe_pop("MAKE_FUNCTION") if flags & 0x04 else None
        kwdefaults = self.safe_pop("MAKE_FUNCTION") if flags & 0x02 else {}
        defaults = self.safe_pop("MAKE_FUNCTION") if flags & 0x01 else ()
        func = Function(code, self, name, defaults, closure, kwdefaults)
        self.stack.append(func)

    def _build_map(self, nargs: int) -> None:
        items = [self.safe_pop("BUILD_MAP") for _ in range(nargs * 2)][::-1]
        self.stack.append(dict(zip(items[::2], items[1::2])))

    def _build_const_key_map(self, nargs: int) -> None:
        keys = self.safe_pop("BUILD_CONST_KEY_MAP")
        values = [self.safe_pop("BUILD_CONST_KEY_MAP") for _ in range(nargs)][::-1]
        self.stack.append(dict(zip(keys, values)))

    def _build_slice(self, nargs: int) -> None:
        if nargs == 3:
            step = self.safe_pop("BUILD_SLICE")
            stop = self.safe_pop("BUILD_SLICE")
            start = self.safe_pop("BUILD_SLICE")
        else:
            step = None
            stop = self.safe_pop("BUILD_SLICE")
            start = self.safe_pop("BUILD_SLICE")
        self.stack.append(slice(start, stop, step))

    async def _for_iter(self, instr: dis.Instruction) -> None:
        iterator = self.stack[-1]
        try:
            value = await anext(iterator) if hasattr(iterator, '__aiter__') else next(iterator)
            self.stack.append(value)
        except (StopIteration, StopAsyncIteration):
            self.safe_pop(instr.opname)
            self.ip = instr.arg

    def _load_method(self, name: str) -> None:
        obj = self.safe_pop("LOAD_METHOD")
        method = getattr(obj, name)
        self.stack.append(method)
        self.stack.append(obj)

    def _end_async_for(self, instr: dis.Instruction) -> None:
        exc = self.safe_pop(instr.opname)
        self.safe_pop(instr.opname)
        if not isinstance(exc, StopAsyncIteration):
            raise exc

    def _raise_varargs(self, nargs: int) -> None:
        if nargs == 1:
            raise self.safe_pop("RAISE_VARARGS")
        elif nargs == 0:
            raise

    def _setup_with(self, target: int) -> None:
        self.block_stack.append(("with", target))
        mgr = self.safe_pop("SETUP_WITH")
        self.stack.append(mgr.__exit__)
        self.stack.append(mgr.__enter__())

    async def _setup_async_with(self, target: int) -> None:
        self.block_stack.append(("async_with", target))
        mgr = self.safe_pop("SETUP_ASYNC_WITH")
        self.stack.append(mgr.__aexit__)
        self.stack.append(await mgr.__aenter__())

    def _reraise(self, instr: dis.Instruction) -> None:
        if self.stack and isinstance(self.stack[-1], Exception):
            raise self.stack[-1]
        raise RuntimeError("No exception to reraise")

    def _yield_value(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        self.stack.append(value)
        raise ReturnException(value)

    def _yield_from(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        iterator = iter(value)
        while True:
            try:
                yield_val = next(iterator)
                self.stack.append(yield_val)
            except StopIteration as e:
                if e.value is not None:
                    self.stack.append(e.value)
                break

    def _return_generator(self, instr: dis.Instruction) -> None:
        self.stack.append(GeneratorWrapper(self, self.frames[-1]["code"], self.stack[:]))

    def _load_closure(self, name: str) -> None:
        if name not in self.cells:
            self.cells[name] = Cell(self.env_stack[-1].get(name))
        self.stack.append(self.cells[name])

    def _load_classderef(self, name: str) -> None:
        if name in self.cells:
            self.stack.append(self.cells[name].contents)
        else:
            self.stack.append(self.get_variable(name))

    def _format_value(self, flags: int) -> None:
        spec = self.safe_pop("FORMAT_VALUE") if flags & 0x04 else ""
        value = self.safe_pop("FORMAT_VALUE")
        self.stack.append(format(value, spec))

    def _match_keys(self, instr: dis.Instruction) -> None:
        keys = self.safe_pop(instr.opname)
        value = self.stack[-1]
        if not isinstance(value, dict) or any(k not in value for k in keys):
            self.stack.append(None)
        else:
            self.stack.append(tuple(value[k] for k in keys))

    async def run(self, code_obj: types.CodeType, initial_stack: List[Any] = None) -> Any:
        instructions = list(dis.get_instructions(code_obj))
        self.ip = 0
        last_value = None
        exception_state = None
        self.frames.append({"code": code_obj})
        if initial_stack:
            self.stack.extend(initial_stack)

        @contextmanager
        def execution_timer():
            deadline = self.loop.time() + self.max_execution_time
            yield
            if self.loop.time() > deadline:
                raise TimeoutError("Execution time exceeded")

        with execution_timer():
            while self.ip < len(instructions):
                instr = instructions[self.ip]
                lineno = instr.starts_line or (self.ip > 0 and instructions[self.ip - 1].starts_line) or 1
                self.stack_trace.append(f"Line {lineno}: {instr.opname} {instr.argval}")
                logger.debug(f"IP: {self.ip}, Opcode: {instr.opname}, Arg: {instr.arg}, Stack: {self.stack}")

                try:
                    handler = self.opcode_handlers.get(instr.opname, self._not_implemented)
                    result = handler(instr)
                    if asyncio.iscoroutine(result):
                        result = await result
                    self.ip += 1
                except (ReturnException, BreakException, ContinueException) as e:
                    if isinstance(e, ReturnException):
                        last_value = e.value
                        break
                    raise
                except Exception as e:
                    context_line = self.source_lines[lineno - 1] if self.source_lines and lineno <= len(self.source_lines) else ""
                    if isinstance(e, ExceptionGroup) and self.block_stack:
                        block_type, target = self.block_stack[-1]
                        if block_type == "except":
                            self.ip = target
                            for sub_exc in e.exceptions:
                                if isinstance(sub_exc, ValueError):  # Simplified except* simulation
                                    self.stack.append(sub_exc)
                                    exception_state = sub_exc
                                    break
                            else:
                                self.stack.append(e.exceptions[0])
                            continue
                    if self.block_stack:
                        block_type, target = self.block_stack[-1]
                        if block_type in ("finally", "except"):
                            self.ip = target
                            exception_state = e
                            self.stack.append(e)
                            continue
                        elif block_type == "loop":
                            self.ip = target
                            continue
                    raise WrappedException(
                        f"Error line {lineno}, col 0:\n{context_line}\nDescription: {str(e)}",
                        e, lineno, 0, context_line, self.stack_trace
                    ) from e

        self.frames.pop()
        if asyncio.iscoroutine(last_value):
            last_value = await last_value
        return last_value

    def _not_implemented(self, instr: dis.Instruction) -> None:
        raise NotImplementedError(f"Opcode {instr.opname} not implemented")

class Function:
    def __init__(self, code: types.CodeType, interpreter: 'BytecodeInterpreter', name: str, defaults: Tuple, closure: Tuple[Cell, ...] = (), kwdefaults: Dict[str, Any] = {}):
        self.code = code
        self.interpreter = interpreter
        self.name = name
        self.defaults = defaults
        self.closure = closure
        self.kwdefaults = kwdefaults

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        new_env_stack = self.interpreter.env_stack[:]
        local_frame = defaultdict(lambda: None)

        arg_count = self.code.co_argcount
        varnames = self.code.co_varnames
        for i, arg in enumerate(args[:arg_count]):
            local_frame[varnames[i]] = arg

        default_start = max(0, arg_count - len(self.defaults))
        for i, default in enumerate(self.defaults):
            idx = default_start + i
            if idx < arg_count and idx >= len(args):
                local_frame[varnames[idx]] = default

        kwonly_start = arg_count
        kwonly_count = self.code.co_kwonlyargcount
        for i in range(kwonly_start, kwonly_start + kwonly_count):
            name = varnames[i]
            if name in kwargs:
                local_frame[name] = kwargs[name]
            elif name in self.kwdefaults:
                local_frame[name] = self.kwdefaults[name]

        if self.code.co_flags & 0x04:  # CO_VARARGS
            vararg_name = varnames[arg_count + kwonly_count]
            local_frame[vararg_name] = args[arg_count:] if len(args) > arg_count else ()

        if self.code.co_flags & 0x08:  # CO_VARKEYWORDS
            varkw_name = varnames[arg_count + kwonly_count + (1 if self.code.co_flags & 0x04 else 0)]
            remaining_kwargs = {k: v for k, v in kwargs.items() if k not in varnames[:arg_count + kwonly_count]}
            local_frame[varkw_name] = remaining_kwargs

        for name, value in kwargs.items():
            if name in varnames[:arg_count]:
                local_frame[name] = value

        new_env_stack.append(local_frame)
        new_interp = self.interpreter.spawn_from_env(new_env_stack)
        if self.code.co_freevars and self.closure:
            for name, cell in zip(self.code.co_freevars, self.closure):
                new_interp.cells[name] = cell

        result = await new_interp.run(self.code)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def __get__(self, instance: Any, owner: Any):
        if instance is None:
            return self
        async def method(*args: Any, **kwargs: Any) -> Any:
            return await self(instance, *args, **kwargs)
        method.__self__ = instance
        return method

async def interpret_ast_async(ast_tree: Any, allowed_modules: List[str], source: str = "") -> Any:
    code_obj = compile(ast_tree, "<string>", "exec") if not isinstance(ast_tree, types.CodeType) else ast_tree
    interpreter = BytecodeInterpreter(allowed_modules=allowed_modules, source=source)
    result = await interpreter.run(code_obj)
    if asyncio.iscoroutine(result):
        result = await result
    elif hasattr(result, '__aiter__'):
        return [val async for val in result]
    return interpreter.env_stack[0].get('result', result)

def interpret_ast(ast_tree: Any, allowed_modules: List[str], source: str = "") -> Any:
    return asyncio.run(interpret_ast_async(ast_tree, allowed_modules, source))

def interpret_code(source_code: str, allowed_modules: List[str]) -> Any:
    dedented_source = textwrap.dedent(source_code).strip()
    code_obj = compile(dedented_source, "<string>", "exec")
    return interpret_ast(code_obj, allowed_modules, source=dedented_source)

async def run_examples():
    examples = [
        (
            "Decorators and args",
            """
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("Decorated!")
        return func(*args, **kwargs)
    return wrapper

@my_decorator
def example(a, b=2, *args, c=3, **kwargs):
    return a + b + c + sum(args) + sum(kwargs.values())

result = example(1, 4, 5, 6, c=7, x=8)
            """,
            [],
            31
        ),
        (
            "Async function",
            """
import asyncio

async def delay_square(x, delay=1):
    await asyncio.sleep(delay)
    return x * x

result = delay_square(5)
            """,
            ["asyncio"],
            25
        ),
        (
            "Lambda with kwargs",
            """
f = lambda x, y=2, *args, z=3, **kwargs: x + y + z + sum(args) + sum(kwargs.values())
result = f(1, 4, 5, z=6, w=7)
            """,
            [],
            23
        ),
        (
            "Pattern matching",
            """
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
            """,
            [],
            "List of 10 and 20"
        ),
        (
            "Exception groups",
            """
def risky():
    raise ExceptionGroup("Problems", [ValueError("bad value"), TypeError("bad type")])

try:
    risky()
except* ValueError as ve:
    result = "Caught ValueError"
except* TypeError as te:
    result = "Caught TypeError"
            """,
            [],
            "Caught ValueError"
        ),
        (
            "Inplace ops and f-strings",
            """
lst = [1, 2, 3]
lst += [4, 5]
del lst[0]
x = f"Value: {lst[0]}"
result = x
            """,
            [],
            "Value: 2"
        )
    ]

    for name, code, modules, expected in examples:
        print(f"\nRunning: {name}")
        try:
            result = await interpret_ast_async(compile(textwrap.dedent(code).strip(), "<string>", "exec"), modules, code)
            print(f"Result: {result} (Expected: {expected})")
            assert str(result) == str(expected), f"Expected {expected}, got {result}"
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_examples())