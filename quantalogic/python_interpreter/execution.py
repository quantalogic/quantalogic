import ast
import asyncio
import textwrap
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .interpreter_core import ASTInterpreter
from .function_utils import Function, AsyncFunction
from .exceptions import WrappedException

@dataclass
class AsyncExecutionResult:
    result: Any
    error: Optional[str]
    execution_time: float
    local_variables: Optional[Dict[str, Any]] = None  # Added to store local variables

def optimize_ast(tree: ast.AST) -> ast.AST:
    """Perform constant folding and basic optimizations on the AST."""
    class ConstantFolder(ast.NodeTransformer):
        def visit_BinOp(self, node):
            self.generic_visit(node)
            if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                left, right = node.left.value, node.right.value
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    if isinstance(node.op, ast.Add):
                        return ast.Constant(value=left + right)
                    elif isinstance(node.op, ast.Sub):
                        return ast.Constant(value=left - right)
                    elif isinstance(node.op, ast.Mult):
                        return ast.Constant(value=left * right)
                    elif isinstance(node.op, ast.Div) and right != 0:
                        return ast.Constant(value=left / right)
            return node

        def visit_If(self, node):
            self.generic_visit(node)
            if isinstance(node.test, ast.Constant):
                if node.test.value:
                    return ast.Module(body=node.body, type_ignores=[])
                else:
                    return ast.Module(body=node.orelse, type_ignores=[])
            return node

    return ConstantFolder().visit(tree)

class ControlledEventLoop:
    """Encapsulated event loop management to prevent unauthorized access"""
    def __init__(self):
        self._loop = None
        self._created = False
        self._lock = asyncio.Lock()

    async def get_loop(self) -> asyncio.AbstractEventLoop:
        async with self._lock:
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                self._created = True
            return self._loop

    async def cleanup(self):
        async with self._lock:
            if self._created and self._loop and not self._loop.is_closed():
                for task in asyncio.all_tasks(self._loop):
                    task.cancel()
                await asyncio.gather(*asyncio.all_tasks(self._loop), return_exceptions=True)
                self._loop.close()
                self._loop = None
                self._created = False

    async def run_task(self, coro, timeout: float) -> Any:
        return await asyncio.wait_for(coro, timeout=timeout)

async def execute_async(
    code: str,
    entry_point: Optional[str] = None,
    args: Optional[Tuple] = None,
    kwargs: Optional[Dict[str, Any]] = None,
    timeout: float = 30,
    allowed_modules: List[str] = ['asyncio'],
    namespace: Optional[Dict[str, Any]] = None,
    max_memory_mb: int = 1024
) -> AsyncExecutionResult:
    start_time = time.time()
    event_loop_manager = ControlledEventLoop()
    
    try:
        ast_tree = optimize_ast(ast.parse(textwrap.dedent(code)))
        loop = await event_loop_manager.get_loop()
        
        # Remove direct asyncio access from builtins
        safe_namespace = namespace.copy() if namespace else {}
        safe_namespace.pop('asyncio', None)  # Prevent direct asyncio access
        
        interpreter = ASTInterpreter(
            allowed_modules=allowed_modules,
            restrict_os=True,
            namespace=safe_namespace,
            max_memory_mb=max_memory_mb,
            source=code  # Pass source code for better error context
        )
        interpreter.loop = loop
        
        async def run_execution():
            return await interpreter.execute_async(ast_tree)
        
        await event_loop_manager.run_task(run_execution(), timeout=timeout)
        
        if entry_point:
            func = interpreter.env_stack[0].get(entry_point)
            if not func:
                raise NameError(f"Function '{entry_point}' not found in the code")
            args = args or ()
            kwargs = kwargs or {}
            if isinstance(func, AsyncFunction) or asyncio.iscoroutinefunction(func):
                # Expect a tuple (result, local_vars) from AsyncFunction
                execution_result = await event_loop_manager.run_task(func(*args, **kwargs), timeout=timeout)
                if isinstance(execution_result, tuple) and len(execution_result) == 2:
                    result, local_vars = execution_result
                else:
                    result, local_vars = execution_result, {}
            elif isinstance(func, Function):
                result = await func(*args, **kwargs)
                local_vars = {}  # Non-async functions don't yet support local var return
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await event_loop_manager.run_task(result, timeout=timeout)
                local_vars = {}
            if asyncio.iscoroutine(result):
                result = await event_loop_manager.run_task(result, timeout=timeout)
        else:
            result = await interpreter.execute_async(ast_tree)
            local_vars = {k: v for k, v in interpreter.env_stack[-1].items() if not k.startswith('__')}
        
        # Filter out internal variables if not already filtered
        filtered_local_vars = local_vars if local_vars else {}
        if not entry_point:  # Apply filtering only for module-level execution
            filtered_local_vars = {k: v for k, v in local_vars.items() if not k.startswith('__')}
        
        return AsyncExecutionResult(
            result=result,
            error=None,
            execution_time=time.time() - start_time,
            local_variables=filtered_local_vars
        )
    except asyncio.TimeoutError as e:
        return AsyncExecutionResult(
            result=None,
            error=f'TimeoutError: Execution exceeded {timeout} seconds',
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
        error_msg = f'{error_type}: {str(e)}'
        if hasattr(e, 'lineno') and hasattr(e, 'col_offset'):
            error_msg += f' at line {e.lineno}, col {e.col_offset}'
        return AsyncExecutionResult(
            result=None,
            error=error_msg,
            execution_time=time.time() - start_time
        )
    finally:
        await event_loop_manager.cleanup()

def interpret_ast(ast_tree: ast.AST, allowed_modules: List[str], source: str = "", restrict_os: bool = False, namespace: Optional[Dict[str, Any]] = None) -> Any:
    ast_tree = optimize_ast(ast_tree)
    event_loop_manager = ControlledEventLoop()
    
    # Remove asyncio from namespace
    safe_namespace = namespace.copy() if namespace else {}
    safe_namespace.pop('asyncio', None)
    
    interpreter = ASTInterpreter(allowed_modules=allowed_modules, source=source, restrict_os=restrict_os, namespace=safe_namespace)
    
    async def run_interpreter():
        loop = await event_loop_manager.get_loop()
        interpreter.loop = loop
        result = await interpreter.visit(ast_tree, wrap_exceptions=True)
        return result

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        interpreter.loop = loop
        result = loop.run_until_complete(run_interpreter())
        return result
    finally:
        if not loop.is_closed():
            loop.close()

def interpret_code(source_code: str, allowed_modules: List[str], restrict_os: bool = False, namespace: Optional[Dict[str, Any]] = None) -> Any:
    dedented_source = textwrap.dedent(source_code).strip()
    tree: ast.AST = ast.parse(dedented_source)
    return interpret_ast(tree, allowed_modules, source=dedented_source, restrict_os=restrict_os, namespace=namespace)