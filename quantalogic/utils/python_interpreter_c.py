import asyncio
import builtins
import dis
import inspect
import logging
import textwrap
from typing import Any, Dict, List, Optional, Tuple, Callable
import types
from collections import defaultdict
from contextlib import contextmanager

# Configure logging - change DEBUG to INFO for less verbosity
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
        self.task = None
        self.last_value = None

    def __iter__(self):
        return self

    def __next__(self):
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self.interpreter.run(self.code, initial_stack=self.stack))
        try:
            result = self.interpreter.loop.run_until_complete(self.task)
            if isinstance(result, ReturnException):
                self.last_value = result.value
                return result.value
            elif result is not None:
                self.last_value = result
                return result
            raise StopIteration
        except StopIteration:
            raise
        except Exception as e:
            self.task = None
            raise

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
        try:
            # Try to get the current event loop
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create a new event loop if there's no current loop
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        self.block_stack: List[Tuple[str, int]] = []
        self.cells: Dict[str, Cell] = {}
        self.max_execution_time = max_execution_time
        self.source_lines = source.splitlines() if source else []
        self.stack_trace: List[str] = []
        self.current_kw_names: Optional[Tuple[str, ...]] = None

        if env_stack is None:
            self.env_stack = [defaultdict(lambda: None)]
            self.env_stack[0].update(self.modules)
            safe_builtins = {k: v for k, v in vars(builtins).items() if k in {
                "print", "len", "range", "enumerate", "zip", "sum", "min", "max",
                "abs", "round", "str", "repr", "id", "type", "isinstance", "issubclass",
                "Exception", "ValueError", "TypeError", "ZeroDivisionError", "ExceptionGroup",
                "list", "dict", "set", "tuple", "frozenset"
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
            "POP_TOP": self._handle_pop_top,
            "RETURN_VALUE": self._handle_return_value,
            "RETURN_CONST": self._handle_return_const,
            "CALL": self._handle_call,
            "CALL_FUNCTION_EX": self._handle_call_function_ex,
            "MAKE_FUNCTION": self._handle_make_function,
            "BUILD_LIST": self._handle_build_list,
            "BUILD_TUPLE": self._handle_build_tuple,
            "BUILD_MAP": self._handle_build_map,
            "BUILD_CONST_KEY_MAP": self._handle_build_const_key_map,
            "BUILD_SET": self._handle_build_set,
            "BUILD_STRING": self._handle_build_string,
            "BUILD_SLICE": self._handle_build_slice,
            "BINARY_SLICE": self._handle_binary_slice,
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
            "RAISE_VARARGS": self._handle_raise_varargs,
            "SETUP_FINALLY": self._handle_setup_finally,
            "SETUP_EXCEPT": self._handle_setup_except,
            "SETUP_LOOP": self._handle_setup_loop,
            "SETUP_WITH": self._handle_setup_with,
            "POP_BLOCK": self._handle_pop_block,
            "POP_EXCEPT": self._handle_pop_except,
            "RERAISE": self._handle_reraise,
            "YIELD_VALUE": self._handle_yield_value,
            "YIELD_FROM": self._handle_yield_from,
            "GET_YIELD_FROM_ITER": self._handle_get_yield_from_iter,
            "RETURN_GENERATOR": self._handle_return_generator,
            "IMPORT_NAME": self._handle_import_name,
            "IMPORT_FROM": self._handle_import_from,
            "LOAD_CLOSURE": self._handle_load_closure,
            "LOAD_DEREF": self._handle_load_deref,
            "STORE_DEREF": self._handle_store_deref,
            "LOAD_CLASSDEREF": self._handle_load_classderef,
            "MAKE_CELL": self._handle_make_cell,
            "LOAD_BUILD_CLASS": self._handle_load_build_class,
            "PUSH_NULL": self._handle_push_null,
            "KW_NAMES": self._handle_kw_names,
            "UNARY_POSITIVE": self._handle_unary_positive,
            "UNARY_NEGATIVE": self._handle_unary_negative,
            "UNARY_NOT": self._handle_unary_not,
            "UNARY_INVERT": self._handle_unary_invert,
            "LIST_APPEND": self._handle_list_append,
            "MAP_ADD": self._handle_map_add,
            "SET_ADD": self._handle_set_add,
            "FORMAT_VALUE": self._handle_format_value,
            "ROT_TWO": self._handle_rot_two,
            "ROT_THREE": self._handle_rot_three,
            "DUP_TOP": self._handle_dup_top,
            "COPY": self._handle_copy,
            "SWAP": self._handle_swap,
            "LOAD_FAST_AND_CLEAR": self._handle_load_fast_and_clear,
            "GET_AWAITABLE": self._handle_get_awaitable,
            "MATCH_SEQUENCE": self._handle_match_sequence,
            "MATCH_MAPPING": self._handle_match_mapping,
            "MATCH_CLASS": self._handle_match_class,
            "MATCH_KEYS": self._handle_match_keys,
            "GET_LEN": self._handle_get_len,
            "CHECK_EG_MATCH": self._handle_check_eg_match,
            "JUMP_NO_INTERRUPT": self._handle_jump_no_interrupt,
            "SEND": self._handle_send,  # Added for yield from
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
        if value is None and instr.argval in self.cells:
            value = self.cells[instr.argval].contents
        self.stack.append(value)

    def _handle_store_fast(self, instr: dis.Instruction) -> None:
        self._store_fast(instr.argval, self.safe_pop(instr.opname))

    def _handle_delete_fast(self, instr: dis.Instruction) -> None:
        self.env_stack[-1].pop(instr.argval, None)

    def _handle_load_global(self, instr: dis.Instruction) -> None:
        self.stack.append(self.env_stack[0][instr.argval])

    def _handle_store_global(self, instr: dis.Instruction) -> None:
        self.env_stack[0][instr.argval] = self.safe_pop(instr.opname)

    def _handle_delete_global(self, instr: dis.Instruction) -> None:
        self.env_stack[0].pop(instr.argval, None)

    def _handle_delete_name(self, instr: dis.Instruction) -> None:
        self._delete_name(instr.argval)

    def _handle_binary_op(self, instr: dis.Instruction) -> None:
        """Handle binary operations according to Python 3.11 opcode mapping."""
        right = self.safe_pop(instr.opname)
        left = self.safe_pop(instr.opname)
        
        # Check for None operands
        if left is None or right is None:
            raise TypeError(f"Cannot perform binary operation on NoneType")
        
        try:
            # Full Python 3.11 binary operations mapping
            if instr.arg == 0:      # +
                result = left + right
            elif instr.arg == 1:    # &
                result = left & right
            elif instr.arg == 2:    # //
                result = left // right
            elif instr.arg == 3:    # <<
                result = left << right
            elif instr.arg == 4:    # @
                result = left @ right
            elif instr.arg == 5:    # *
                result = left * right
            elif instr.arg == 6:    # %
                result = left % right
            elif instr.arg == 7:    # |
                result = left | right
            elif instr.arg == 8:    # **
                result = left ** right
            elif instr.arg == 9:    # >>
                result = left >> right
            elif instr.arg == 10:   # -
                result = left - right
            elif instr.arg == 11:   # /
                result = left / right
            elif instr.arg == 12:   # ^
                result = left ^ right
            # In-place operations (13-25)
            elif instr.arg == 13:   # +=
                if hasattr(left, '__iadd__'):
                    result = left.__iadd__(right)
                else:
                    result = left + right
            elif instr.arg == 14:   # &=
                if hasattr(left, '__iand__'):
                    result = left.__iand__(right)
                else:
                    result = left & right
            elif instr.arg == 15:   # //=
                if hasattr(left, '__ifloordiv__'):
                    result = left.__ifloordiv__(right)
                else:
                    result = left // right
            elif instr.arg == 16:   # <<=
                if hasattr(left, '__ilshift__'):
                    result = left.__ilshift__(right)
                else:
                    result = left << right
            elif instr.arg == 17:   # @=
                if hasattr(left, '__imatmul__'):
                    result = left.__imatmul__(right)
                else:
                    result = left @ right
            elif instr.arg == 18:   # *=
                if hasattr(left, '__imul__'):
                    result = left.__imul__(right)
                else:
                    result = left * right
            elif instr.arg == 19:   # %=
                if hasattr(left, '__imod__'):
                    result = left.__imod__(right)
                else:
                    result = left % right
            elif instr.arg == 20:   # |=
                if hasattr(left, '__ior__'):
                    result = left.__ior__(right)
                else:
                    result = left | right
            elif instr.arg == 21:   # **=
                if hasattr(left, '__ipow__'):
                    result = left.__ipow__(right)
                else:
                    result = left ** right
            elif instr.arg == 22:   # >>=
                if hasattr(left, '__irshift__'):
                    result = left.__irshift__(right)
                else:
                    result = left >> right
            elif instr.arg == 23:   # -=
                if hasattr(left, '__isub__'):
                    result = left.__isub__(right)
                else:
                    result = left - right
            elif instr.arg == 24:   # /=
                if hasattr(left, '__itruediv__'):
                    result = left.__itruediv__(right)
                else:
                    result = left / right
            elif instr.arg == 25:   # ^=
                if hasattr(left, '__ixor__'):
                    result = left.__ixor__(right)
                else:
                    result = left ^ right
            else:
                raise ValueError(f"Unknown binary operation code: {instr.arg}")
                
            self.stack.append(result)
        except Exception as e:
            # Provide detailed error message for debugging
            op_name = self._get_binary_op_name(instr.arg)
            raise TypeError(f"unsupported operand type(s) for {op_name}: '{type(left).__name__}' and '{type(right).__name__}'") from e
    
    def _get_binary_op_name(self, op_code: int) -> str:
        """Return the string representation of a binary operation code."""
        op_names = {
            0: '+', 1: '&', 2: '//', 3: '<<', 4: '@', 5: '*', 
            6: '%', 7: '|', 8: '**', 9: '>>', 10: '-', 11: '/', 
            12: '^', 13: '+=', 14: '&=', 15: '//=', 16: '<<=',
            17: '@=', 18: '*=', 19: '%=', 20: '|=', 21: '**=',
            22: '>>=', 23: '-=', 24: '/=', 25: '^='
        }
        return op_names.get(op_code, f"operation {op_code}")

    def _handle_binary_subscr(self, instr: dis.Instruction) -> None:
        # Improved error handling for subscripting
        index = self.safe_pop(instr.opname)
        obj = self.safe_pop(instr.opname)
        if obj is None:
            raise TypeError(f"'NoneType' object is not subscriptable")
        if not hasattr(obj, '__getitem__'):
            raise TypeError(f"'{type(obj).__name__}' object is not subscriptable")
        try:
            self.stack.append(obj[index])
        except (IndexError, KeyError) as e:
            raise e

    def _handle_store_subscr(self, instr: dis.Instruction) -> None:
        # Improved error handling for store subscript
        value = self.safe_pop(instr.opname)
        index = self.safe_pop(instr.opname)
        obj = self.safe_pop(instr.opname)
        if obj is None:
            raise TypeError(f"'NoneType' object does not support item assignment")
        if not hasattr(obj, '__setitem__'):
            raise TypeError(f"'{type(obj).__name__}' object does not support item assignment")
        obj[index] = value
        # Update references
        for env in self.env_stack:
            for var_name, var_value in env.items():
                if var_value is obj:
                    env[var_name] = obj

    def _handle_delete_subscr(self, instr: dis.Instruction) -> None:
        index = self.safe_pop(instr.opname)
        obj = self.safe_pop(instr.opname)
        if not hasattr(obj, '__delitem__'):
            raise TypeError(f"'{type(obj).__name__}' object does not support item deletion")
        del obj[index]
        frame = self.env_stack[-1]
        for var_name, var_value in frame.items():
            if var_value is obj:
                frame[var_name] = obj

    def _handle_compare_op(self, instr: dis.Instruction) -> None:
        # Fix stack underflow in compare operations
        if len(self.stack) < 2:
            raise ValueError(f"Not enough values on stack for comparison operation")
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
        right = self.safe_pop(instr.opname)
        left = self.safe_pop(instr.opname)
        self.stack.append((left is right) == (instr.arg == 0))

    def _handle_contains_op(self, instr: dis.Instruction) -> None:
        right = self.safe_pop(instr.opname)
        left = self.safe_pop(instr.opname)
        self.stack.append((left in right) == (instr.arg == 0))

    def _handle_pop_jump_if_false(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        if not value:
            self.ip = instr.argval

    def _handle_pop_jump_if_true(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        if value:
            self.ip = instr.argval

    def _handle_pop_jump_forward_if_false(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        if not value:
            self.ip += instr.arg

    def _handle_pop_jump_forward_if_true(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        if value:
            self.ip += instr.arg

    def _handle_pop_jump_forward_if_none(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        if value is None:
            # Adjust for the auto-increment that happens in the main loop
            self.ip += instr.arg - 1

    def _handle_pop_jump_forward_if_not_none(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        if value is not None:
            # Adjust for the auto-increment that happens in the main loop
            self.ip += instr.arg - 1

    def _handle_jump_forward(self, instr: dis.Instruction) -> None:
        # Adjust for the auto-increment that happens in the main loop
        self.ip += instr.arg - 1

    def _handle_jump_absolute(self, instr: dis.Instruction) -> None:
        # Set IP directly to target and adjust for the auto-increment
        self.ip = instr.argval - 1

    def _handle_jump_backward(self, instr: dis.Instruction) -> None:
        # Adjust for the auto-increment that happens in the main loop
        self.ip -= instr.arg + 1

    def _handle_pop_top(self, instr: dis.Instruction) -> None:
        self.safe_pop(instr.opname)

    def _handle_return_value(self, instr: dis.Instruction) -> None:
        self._raise_return(self.safe_pop(instr.opname))

    def _handle_return_const(self, instr: dis.Instruction) -> None:
        self._raise_return(instr.argval)

    async def _handle_call(self, instr: dis.Instruction) -> None:
        num_pos = instr.arg & 0xFF
        num_kw = (instr.arg >> 8) if self.current_kw_names else 0

        kwargs = {}
        if num_kw > 0 and self.current_kw_names:
            kw_values = [self.safe_pop("CALL") for _ in range(num_kw)][::-1]
            kwargs = dict(zip(self.current_kw_names, kw_values)) or {}
            self.current_kw_names = None

        args = [self.safe_pop("CALL") for _ in range(num_pos)][::-1] or ()
        func = self.safe_pop("CALL")

        try:
            if isinstance(func, Function):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
            self.stack.append(result)
        except Exception as e:
            lineno = instr.starts_line or 1
            context_line = self.source_lines[lineno - 1] if self.source_lines and lineno <= len(self.source_lines) else ""
            raise WrappedException(
                f"Error line {lineno}, col 0:\n{context_line}\nDescription: {str(e)}",
                e, lineno, 0, context_line, self.stack_trace
            ) from e

    async def _handle_call_function_ex(self, instr: dis.Instruction) -> None:
        if instr.arg & 0x01:  # Has **kwargs
            kwargs = self.safe_pop("CALL_FUNCTION_EX")
        else:
            kwargs = {}
        if instr.arg & 0x02:  # Has *args
            args = self.safe_pop("CALL_FUNCTION_EX")
        else:
            args = ()
        func = self.safe_pop("CALL_FUNCTION_EX")
        try:
            if isinstance(func, Function):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
            self.stack.append(result)
        except Exception as e:
            lineno = instr.starts_line or 1
            context_line = self.source_lines[lineno - 1] if self.source_lines and lineno <= len(self.source_lines) else ""
            raise WrappedException(
                f"Error line {lineno}, col 0:\n{context_line}\nDescription: {str(e)}",
                e, lineno, 0, context_line, self.stack_trace
            ) from e

    def _handle_make_function(self, instr: dis.Instruction) -> None:
        flags = instr.arg
        code = self.safe_pop("MAKE_FUNCTION")
        name = code.co_name
        closure = self.safe_pop("MAKE_FUNCTION") if flags & 0x08 else ()
        annotations = self.safe_pop("MAKE_FUNCTION") if flags & 0x04 else None
        kwdefaults = self.safe_pop("MAKE_FUNCTION") if flags & 0x02 else {}
        defaults = self.safe_pop("MAKE_FUNCTION") if flags & 0x01 else ()
        func = Function(code, self, name, defaults, closure, kwdefaults)
        self.stack.append(func)

    def _handle_build_list(self, instr: dis.Instruction) -> None:
        items = [self.safe_pop(instr.opname) for _ in range(instr.arg)][::-1]
        self.stack.append(items)

    def _handle_build_tuple(self, instr: dis.Instruction) -> None:
        self.stack.append(tuple([self.safe_pop(instr.opname) for _ in range(instr.arg)][::-1]))

    def _handle_build_map(self, instr: dis.Instruction) -> None:
        items = [self.safe_pop("BUILD_MAP") for _ in range(instr.arg * 2)][::-1]
        self.stack.append(dict(zip(items[::2], items[1::2])))

    def _handle_build_const_key_map(self, instr: dis.Instruction) -> None:
        keys = self.safe_pop("BUILD_CONST_KEY_MAP")
        values = [self.safe_pop("BUILD_CONST_KEY_MAP") for _ in range(instr.arg)][::-1]
        self.stack.append(dict(zip(keys, values)))

    def _handle_build_set(self, instr: dis.Instruction) -> None:
        self.stack.append(set([self.safe_pop(instr.opname) for _ in range(instr.arg)][::-1]))

    def _handle_build_string(self, instr: dis.Instruction) -> None:
        parts = [self.safe_pop(instr.opname) for _ in range(instr.arg)][::-1]
        self.stack.append("".join(str(part) for part in parts))

    def _handle_build_slice(self, instr: dis.Instruction) -> None:
        if instr.arg == 3:
            step = self.safe_pop("BUILD_SLICE")
            stop = self.safe_pop("BUILD_SLICE")
            start = self.safe_pop("BUILD_SLICE")
        else:
            step = None
            stop = self.safe_pop("BUILD_SLICE")
            start = self.safe_pop("BUILD_SLICE")
        self.stack.append(slice(start, stop, step))

    def _handle_binary_slice(self, instr: dis.Instruction) -> None:
        # Fix slice handling
        slc = self.safe_pop(instr.opname)
        obj = self.safe_pop(instr.opname)
        if obj is None:
            raise TypeError(f"'NoneType' object is not subscriptable")
        if not hasattr(obj, '__getitem__'):
            raise TypeError(f"'{type(obj).__name__}' object is not subscriptable")
        try:
            self.stack.append(obj[slc])
        except (IndexError, TypeError) as e:
            raise e

    def _handle_list_extend(self, instr: dis.Instruction) -> None:
        items = self.safe_pop(instr.opname)
        self.stack[-instr.arg].extend(items)

    def _handle_set_update(self, instr: dis.Instruction) -> None:
        items = self.safe_pop(instr.opname)
        self.stack[-instr.arg].update(items)

    def _handle_dict_update(self, instr: dis.Instruction) -> None:
        items = self.safe_pop(instr.opname)
        self.stack[-instr.arg].update(items)

    def _handle_unpack_sequence(self, instr: dis.Instruction) -> None:
        seq = self.safe_pop(instr.opname)
        if len(seq) != instr.arg:
            raise ValueError(f"Expected sequence of length {instr.arg}, got {len(seq)}")
        self.stack.extend(reversed(list(seq)))

    async def _handle_for_iter(self, instr: dis.Instruction) -> None:
        iterator = self.stack[-1]
        try:
            value = next(iterator)
            self.stack.append(value)
        except StopIteration:
            self.safe_pop(instr.opname)
            self.ip = instr.argval

    def _handle_load_attr(self, instr: dis.Instruction) -> None:
        obj = self.safe_pop(instr.opname)
        self.stack.append(getattr(obj, instr.argval))

    def _handle_store_attr(self, instr: dis.Instruction) -> None:
        obj = self.safe_pop(instr.opname)
        value = self.safe_pop(instr.opname)
        setattr(obj, instr.argval, value)

    def _handle_delete_attr(self, instr: dis.Instruction) -> None:
        obj = self.safe_pop(instr.opname)
        delattr(obj, instr.argval)

    def _handle_load_method(self, instr: dis.Instruction) -> None:
        obj = self.safe_pop("LOAD_METHOD")
        method = getattr(obj, instr.argval)
        self.stack.append(method)
        self.stack.append(obj)

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

    def _handle_raise_varargs(self, instr: dis.Instruction) -> None:
        if instr.arg == 1:
            exc = self.safe_pop("RAISE_VARARGS")
            # Store the exception for potential exception handling
            exc_value = exc
            if isinstance(exc, type) and issubclass(exc, Exception):
                exc_value = exc()
            self.stack.append(exc_value)
            # Check if we are in a try block by examining the block_stack
            if any(block_type in ("finally", "except") for block_type, _ in self.block_stack):
                # Let the outer try/except handle it in the run method
                raise exc_value
            else:
                # Wrap the exception for better reporting
                context_line = ""
                lineno = instr.starts_line or 1
                if self.source_lines and lineno <= len(self.source_lines):
                    context_line = self.source_lines[lineno - 1]
                raise WrappedException(
                    f"Error line {lineno}, col 0:\n{context_line}\nDescription: {str(exc_value)}",
                    exc_value, lineno, 0, context_line, self.stack_trace
                )
        elif instr.arg == 0:
            if not self.stack or not isinstance(self.stack[-1], Exception):
                raise RuntimeError("No exception to reraise")
            exc = self.stack[-1]
            # Similar behavior as above
            if any(block_type in ("finally", "except") for block_type, _ in self.block_stack):
                raise exc
            else:
                context_line = ""
                lineno = instr.starts_line or 1
                if self.source_lines and lineno <= len(self.source_lines):
                    context_line = self.source_lines[lineno - 1]
                original_type = type(exc).__name__
                raise WrappedException(
                    f"Error line {lineno}, col 0:\n{context_line}\nDescription: {original_type}: {str(exc)}",
                    exc, lineno, 0, context_line, self.stack_trace
                )
        elif instr.arg == 2:
            cause = self.safe_pop("RAISE_VARARGS")
            exc = self.safe_pop("RAISE_VARARGS")
            if isinstance(exc, type) and issubclass(exc, Exception):
                exc = exc()
            self.stack.append(exc)
            raise exc from cause
        else:
            # Handle other cases
            exc = self.safe_pop("RAISE_VARARGS")
            if isinstance(exc, type) and issubclass(exc, Exception):
                exc = exc()
            self.stack.append(exc)
            raise exc

    def _handle_setup_finally(self, instr: dis.Instruction) -> None:
        self.block_stack.append(("finally", self.ip + instr.arg))

    def _handle_setup_except(self, instr: dis.Instruction) -> None:
        self.block_stack.append(("except", self.ip + instr.arg))

    def _handle_setup_loop(self, instr: dis.Instruction) -> None:
        self.block_stack.append(("loop", self.ip + instr.arg))

    def _handle_setup_with(self, instr: dis.Instruction) -> None:
        mgr = self.safe_pop("SETUP_WITH")
        self.stack.append(mgr.__exit__)
        self.stack.append(mgr.__enter__())
        self.block_stack.append(("with", self.ip + instr.arg))

    def _handle_load_build_class(self, instr: dis.Instruction) -> None:
        # Fix class creation
        def build_class(func, name, *bases, **kwds):
            # Simplified build_class implementation
            namespace = {}
            if hasattr(func, '__globals__'):
                func.__globals__.update(self.env_stack[0])
            
            # Call the function to populate the namespace
            if isinstance(func, Function):
                self.loop.run_until_complete(func(namespace))
            else:
                func(namespace)
            
            return type(name, bases, namespace)
        
        self.stack.append(build_class)

    def _handle_pop_block(self, instr: dis.Instruction) -> None:
        if self.block_stack:
            self.block_stack.pop()

    def _handle_pop_except(self, instr: dis.Instruction) -> None:
        if self.stack:
            self.stack.pop()

    def _handle_reraise(self, instr: dis.Instruction) -> None:
        if self.stack and isinstance(self.stack[-1], Exception):
            raise self.stack[-1]
        raise RuntimeError("No exception to reraise")

    def _handle_yield_value(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        self.stack.append(value)
        raise ReturnException(value)

    async def _handle_yield_from(self, instr: dis.Instruction) -> None:
        value = self.safe_pop("YIELD_FROM")
        if asyncio.iscoroutine(value):
            result = await value
            self.stack.append(result)
        else:
            iterator = iter(value)
            while True:
                try:
                    yield_val = next(iterator)
                    self.stack.append(yield_val)
                    raise ReturnException(yield_val)
                except StopIteration as e:
                    if e.value is not None:
                        self.stack.append(e.value)
                    break

    def _handle_get_yield_from_iter(self, instr: dis.Instruction) -> None:
        self.stack[-1] = iter(self.stack[-1])

    def _handle_return_generator(self, instr: dis.Instruction) -> None:
        self.stack.append(GeneratorWrapper(self, self.frames[-1]["code"], self.stack[:]))

    def _handle_import_name(self, instr: dis.Instruction) -> None:
        fromlist = self.safe_pop(instr.opname)
        level = self.safe_pop(instr.opname)
        self.stack.append(self.safe_import(instr.argval, fromlist=fromlist, level=level))

    def _handle_import_from(self, instr: dis.Instruction) -> None:
        module = self.stack[-1]
        self.stack.append(getattr(module, instr.argval))

    def _handle_load_closure(self, instr: dis.Instruction) -> None:
        if instr.argval not in self.cells:
            self.cells[instr.argval] = Cell(self.env_stack[-1].get(instr.argval))
        self.stack.append(self.cells[instr.argval])

    def _handle_load_deref(self, instr: dis.Instruction) -> None:
        self.stack.append(self.cells[instr.argval].contents)

    def _handle_store_deref(self, instr: dis.Instruction) -> None:
        self.cells[instr.argval].contents = self.safe_pop(instr.opname)

    def _handle_load_classderef(self, instr: dis.Instruction) -> None:
        if instr.argval in self.cells:
            self.stack.append(self.cells[instr.argval].contents)
        else:
            self.stack.append(self.get_variable(instr.argval))

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
        value = self.safe_pop(instr.opname)
        self.stack[-instr.arg].append(value)

    def _handle_map_add(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        key = self.safe_pop(instr.opname)
        self.stack[-instr.arg][key] = value

    def _handle_set_add(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        self.stack[-instr.arg].add(value)

    def _handle_format_value(self, instr: dis.Instruction) -> None:
        spec = self.safe_pop("FORMAT_VALUE") if instr.arg & 0x04 else ""
        if instr.arg & 0x03 == 0:
            value = self.safe_pop("FORMAT_VALUE")
        elif instr.arg & 0x03 == 1:
            value = str(self.safe_pop("FORMAT_VALUE"))
        elif instr.arg & 0x03 == 2:
            value = repr(self.safe_pop("FORMAT_VALUE"))
        else:
            value = self.safe_pop("FORMAT_VALUE")
        self.stack.append(format(value, spec))

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

    def _handle_load_fast_and_clear(self, instr: dis.Instruction) -> None:
        value = self.env_stack[-1].get(instr.argval)
        if value is None and instr.argval in self.cells:
            value = self.cells[instr.argval].contents
        self.stack.append(value)
        self.env_stack[-1][instr.argval] = None

    def _handle_get_awaitable(self, instr: dis.Instruction) -> None:
        obj = self.safe_pop("GET_AWAITABLE")
        if not asyncio.iscoroutine(obj):
            raise TypeError(f"object {type(obj).__name__} cannot be used in 'await'")
        self.stack.append(obj)

    def _handle_match_sequence(self, instr: dis.Instruction) -> None:
        subject = self.stack[-1]
        is_match = isinstance(subject, (list, tuple)) and not isinstance(subject, str)
        self.stack.append(is_match)
        if is_match:
            self.env_stack[-1]['__match_args__'] = tuple(subject)

    def _handle_match_mapping(self, instr: dis.Instruction) -> None:
        subject = self.stack[-1]
        self.stack.append(isinstance(subject, dict))

    def _handle_match_class(self, instr: dis.Instruction) -> None:
        cls = self.safe_pop("MATCH_CLASS")
        subject = self.stack[-1]
        self.stack.append(isinstance(subject, cls))

    def _handle_match_keys(self, instr: dis.Instruction) -> None:
        keys = self.safe_pop("MATCH_KEYS")
        subject = self.stack[-1]
        if not isinstance(subject, dict):
            self.stack.append(None)
        else:
            missing = [k for k in keys if k not in subject]
            if missing:
                self.stack.append(None)
            else:
                values = tuple(subject[k] for k in keys)
                self.stack.append(values)
                self.env_stack[-1]['__match_args__'] = values

    def _handle_get_len(self, instr: dis.Instruction) -> None:
        obj = self.stack[-1]
        self.stack.append(len(obj) if hasattr(obj, '__len__') else 0)

    def _handle_check_eg_match(self, instr: dis.Instruction) -> None:
        exc = self.safe_pop("CHECK_EG_MATCH")
        exc_type = self.safe_pop("CHECK_EG_MATCH")
        if isinstance(exc, BaseExceptionGroup):
            matches = [e for e in exc.exceptions if isinstance(e, exc_type)]
            if matches:
                eg = BaseExceptionGroup(f"matching {exc_type.__name__}", matches)
                self.stack.append(eg)
            else:
                self.stack.append(None)
        else:
            self.stack.append(exc if isinstance(exc, exc_type) else None)

    def _handle_jump_no_interrupt(self, instr: dis.Instruction) -> None:
        self.ip += instr.arg

    def _handle_send(self, instr: dis.Instruction) -> None:
        value = self.safe_pop(instr.opname)
        gen = self.stack[-1]
        try:
            result = gen.send(value)
            self.stack.append(result)
        except StopIteration as e:
            self.ip = instr.argval
            if e.value is not None:
                self.stack.append(e.value)

    def _handle_copy_free_vars(self, instr: dis.Instruction) -> None:
        """Handle the COPY_FREE_VARS opcode needed for closures.
        
        This opcode copies free variables from the current function to cells
        that will be used by nested functions.
        """
        if hasattr(self.frames[-1]["code"], "co_freevars"):
            for var_name in self.frames[-1]["code"].co_freevars:
                if var_name not in self.cells:
                    value = self.env_stack[-1].get(var_name)
                    self.cells[var_name] = Cell(value)

    def safe_import(self, name: str, globals=None, locals=None, fromlist: Tuple[str, ...] = (), level: int = 0) -> Any:
        if name not in self.allowed_modules:
            raise ImportError(f"Module '{name}' not allowed. Permitted: {self.allowed_modules}")
        module = self.modules[name]
        if fromlist:
            for attr in fromlist:
                getattr(module, attr)
        return module

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

    def _raise_return(self, value: Any) -> None:
        raise ReturnException(value)

    async def run(self, code_obj: types.CodeType, initial_stack: List[Any] = None) -> Any:
        instructions = list(dis.get_instructions(code_obj))
        self.ip = 0
        last_value = None
        exception_state = None
        self.frames.append({"code": code_obj})
        if initial_stack:
            self.stack = initial_stack[:]

        # Calculate the deadline outside the loop
        try:
            deadline = self.loop.time() + self.max_execution_time
        except (RuntimeError, AttributeError):
            # Fallback if loop.time() fails
            deadline = None

        # Register the COPY_FREE_VARS handler if not already registered
        if "COPY_FREE_VARS" not in self.opcode_handlers:
            self.opcode_handlers["COPY_FREE_VARS"] = self._handle_copy_free_vars

        # Counter for instruction execution
        instruction_count = 0
        
        # Create a new local variable scope if needed
        if not self.env_stack or code_obj.co_varnames:
            local_frame = defaultdict(lambda: None)
            # Transfer function parameters if they exist
            if len(self.env_stack) > 0 and len(code_obj.co_varnames) > 0:
                for var_name in code_obj.co_varnames:
                    if var_name in self.env_stack[-1]:
                        local_frame[var_name] = self.env_stack[-1][var_name]
            self.env_stack.append(local_frame)

        # Initialize free variables cells if needed
        if hasattr(code_obj, 'co_freevars') and code_obj.co_freevars:
            for var_name in code_obj.co_freevars:
                if var_name not in self.cells:
                    self.cells[var_name] = Cell(None)

        # Clear the stack trace for each new execution
        self.stack_trace = []

        while self.ip < len(instructions):
            # Check for timeout more frequently for CPU-intensive code
            instruction_count += 1
            if deadline and instruction_count % 50 == 0:  # Check more often
                if self.loop.time() > deadline:
                    raise TimeoutError(f"Execution time exceeded limit of {self.max_execution_time} seconds")

            instr = instructions[self.ip]
            # More accurate line number tracking
            lineno = instr.starts_line
            if lineno is None and self.ip > 0:
                # Find the most recent instruction with a line number
                for prev_i in range(self.ip - 1, -1, -1):
                    if instructions[prev_i].starts_line is not None:
                        lineno = instructions[prev_i].starts_line
                        break
            if lineno is None:
                lineno = 1  # Default to line 1 if no line number is found
            
            # Add to stack trace with more detail
            self.stack_trace.append(f"Line {lineno}: {instr.opname} {instr.argval if hasattr(instr, 'argval') else instr.arg}")
            logger.debug(f"IP: {self.ip}, Opcode: {instr.opname}, Arg: {instr.arg}, Stack: {self.stack}, Env: {dict(self.env_stack[-1])}")

            try:
                # Get handler or use _not_implemented for unrecognized opcodes
                handler = self.opcode_handlers.get(instr.opname)
                if handler is None:
                    # Try to handle any new opcodes that might have been added in Python updates
                    logger.warning(f"Unhandled opcode: {instr.opname}. Attempting fallback handling.")
                    handler = self._not_implemented
                
                # Execute the handler
                result = handler(instr)
                if asyncio.iscoroutine(result):
                    await result

                # Special handling for pattern matching - process STORE operations after pattern match
                if instr.opname in ("MATCH_SEQUENCE", "MATCH_KEYS", "MATCH_MAPPING", "MATCH_CLASS") and self.stack and self.stack[-1]:
                    match_args = self.env_stack[-1].get('__match_args__')
                    if match_args:
                        i = self.ip + 1
                        arg_idx = 0
                        while (i < len(instructions) and 
                               instructions[i].opname in ("STORE_FAST", "STORE_NAME", "STORE_ATTR", "STORE_DEREF") and
                               arg_idx < len(match_args)):
                            value = match_args[arg_idx]
                            if instructions[i].opname == "STORE_FAST":
                                self._store_fast(instructions[i].argval, value)
                            elif instructions[i].opname == "STORE_NAME":
                                self.set_variable(instructions[i].argval, value)
                            elif instructions[i].opname == "STORE_ATTR":
                                obj = self.stack[-1]
                                setattr(obj, instructions[i].argval, value)
                            elif instructions[i].opname == "STORE_DEREF":
                                self.cells[instructions[i].argval].contents = value
                            arg_idx += 1
                            i += 1
                        self.ip = i - 1

                self.ip += 1
            except ReturnException as e:
                last_value = e.value
                break
            except BreakException:
                # Find the end of the loop block
                if self.block_stack and self.block_stack[-1][0] == "loop":
                    self.ip = self.block_stack[-1][1]
                    self.block_stack.pop()
                else:
                    raise SyntaxError("'break' outside loop")
                continue
            except ContinueException:
                # Find the start of the loop block
                if self.block_stack and self.block_stack[-1][0] == "loop":
                    # Find the FOR_ITER instruction
                    for i in range(self.block_stack[-1][1] - 1, -1, -1):
                        if instructions[i].opname == "FOR_ITER":
                            self.ip = i
                            break
                    else:
                        # If no FOR_ITER found, go back to the start of the loop
                        self.ip = self.block_stack[-1][1] - 1
                else:
                    raise SyntaxError("'continue' outside loop")
                continue
            except Exception as e:
                # Get context for error reporting
                context_line = ""
                if self.source_lines and lineno <= len(self.source_lines):
                    context_line = self.source_lines[lineno - 1]
                
                # Check if we're in an exception handling block
                if self.block_stack:
                    block_type, target = self.block_stack[-1]
                    if block_type in ("finally", "except"):
                        self.ip = target
                        exception_state = e
                        self.stack.append(e)
                        self.block_stack.pop()
                        continue
                    elif block_type == "loop":
                        # Exit the loop on exception unless handled
                        self.ip = target
                        continue
                
                # Generate a better error message with more context
                error_type = type(e).__name__
                error_msg = str(e)
                
                # Handle wrapped exceptions
                if isinstance(e, WrappedException):
                    error_type = type(e.original_exception).__name__
                    error_msg = str(e.original_exception)
                
                # Create a detailed error message
                full_error = f"Error at line {lineno}, col 0:\n{context_line}\n"
                full_error += f"Description: {error_type}: {error_msg}\n"
                full_error += f"Current opcode: {instr.opname} {instr.argval if hasattr(instr, 'argval') else ''}"
                
                # Wrap the exception for better reporting
                raise WrappedException(
                    full_error,
                    e, lineno, 0, context_line, self.stack_trace
                ) from e

        # Clean up frames and handle return value
        if self.frames:
            self.frames.pop()
        
        # Return either the explicit return value or the result variable if defined
        if last_value is not None:
            return last_value
        elif self.env_stack and 'result' in self.env_stack[-1]:
            return self.env_stack[-1]['result']
        elif self.stack:
            return self.stack[-1]  # Return the top of the stack if no explicit return
        return None

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
        self.is_async = bool(code.co_flags & inspect.CO_COROUTINE)
        self.__globals__ = {}  # Add __globals__ attribute

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        local_frame = defaultdict(lambda: None)
        varnames = self.code.co_varnames
        arg_count = self.code.co_argcount
        kwonly_count = self.code.co_kwonlyargcount

        pos_args = list(args[:arg_count])
        for i, arg in enumerate(pos_args):
            local_frame[varnames[i]] = arg

        default_start = arg_count - len(self.defaults) if self.defaults else arg_count
        for i in range(len(pos_args), arg_count):
            if i >= default_start and i - default_start < len(self.defaults):
                local_frame[varnames[i]] = self.defaults[i - default_start]
            else:
                local_frame[varnames[i]] = None

        if self.code.co_flags & 0x04:  # CO_VARARGS
            varargs_name = varnames[arg_count]
            local_frame[varargs_name] = tuple(args[arg_count:]) or ()

        kwonly_start = arg_count + (1 if self.code.co_flags & 0x04 else 0)
        for i in range(kwonly_count):
            name = varnames[kwonly_start + i]
            if name in kwargs:
                local_frame[name] = kwargs[name]
            elif name in self.kwdefaults:
                local_frame[name] = self.kwdefaults[name]
            elif not self.code.co_flags & 0x08:
                raise TypeError(f"{self.name}() missing required keyword-only argument: '{name}'")

        if self.code.co_flags & 0x08:  # CO_VARKEYWORDS
            varkw_name = varnames[kwonly_start + kwonly_count]
            remaining_kwargs = {k: v for k, v in kwargs.items() if k not in varnames[kwonly_start:kwonly_start + kwonly_count]}
            local_frame[varkw_name] = remaining_kwargs or {}

        for name, value in kwargs.items():
            if name in varnames[:arg_count]:
                if local_frame[name] is not None and args:
                    raise TypeError(f"{self.name}() got multiple values for argument '{name}'")
                local_frame[name] = value

        new_env_stack = self.interpreter.env_stack[:] + [local_frame]
        new_interp = self.interpreter.spawn_from_env(new_env_stack)
        if self.code.co_freevars and self.closure:
            for name, cell in zip(self.code.co_freevars, self.closure):
                new_interp.cells[name] = cell

        # Update the function's globals with the interpreter's environment
        self.__globals__.update(self.interpreter.env_stack[0])

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
    final_result = interpreter.env_stack[-1].get('result', result)
    if asyncio.iscoroutine(final_result):
        return await final_result
    return final_result

def interpret_ast(ast_tree: Any, allowed_modules: List[str], source: str = "") -> Any:
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # Create a new event loop if there's no current loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(interpret_ast_async(ast_tree, allowed_modules, source))
    finally:
        # Don't close the loop - it might be needed for other operations
        pass

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

async def delay_square(x, delay=0):
    await asyncio.sleep(delay)
    return x * x

async def main():
    result = await delay_square(5)
    return result

result = await main()
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