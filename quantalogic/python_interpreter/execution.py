# quantalogic/python_interpreter/execution.py
import ast
import asyncio
import textwrap
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable

from .interpreter_core import ASTInterpreter
from .function_utils import Function, AsyncFunction
from .exceptions import WrappedException

@dataclass
class AsyncExecutionResult:
    result: Any
    error: Optional[str]
    execution_time: float

async def execute_async(
    code: str,
    entry_point: Optional[str] = None,
    args: Optional[Tuple] = None,
    kwargs: Optional[Dict[str, Any]] = None,
    timeout: float = 30,
    allowed_modules: List[str] = ['asyncio'],
    namespace: Optional[Dict[str, Any]] = None
) -> AsyncExecutionResult:
    start_time = time.time()
    try:
        # Parse the code into an AST
        ast_tree = ast.parse(textwrap.dedent(code))
        
        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Create the interpreter with the namespace
        interpreter = ASTInterpreter(
            allowed_modules=allowed_modules,
            restrict_os=True,
            namespace=namespace
        )
        
        # Set the interpreter's loop to be the same as our current loop
        interpreter.loop = loop
        
        # Define the execution function that runs in the same loop context
        async def run_execution():
            return await interpreter.execute_async(ast_tree)
        
        # Execute the module with timeout
        module_result = await asyncio.wait_for(run_execution(), timeout=timeout)
        
        # If an entry_point is specified, execute that function
        if entry_point:
            func = interpreter.env_stack[0].get(entry_point)
            if not func:
                raise NameError(f"Function '{entry_point}' not found in the code")
            args = args or ()
            kwargs = kwargs or {}
            if isinstance(func, AsyncFunction) or asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            elif isinstance(func, Function):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result  # Ensure coroutines are awaited
            # Additional check to handle nested coroutines from method calls
            if asyncio.iscoroutine(result):
                result = await result
        else:
            result = module_result
        
        return AsyncExecutionResult(
            result=result,
            error=None,
            execution_time=time.time() - start_time
        )
    except asyncio.TimeoutError as e:
        return AsyncExecutionResult(
            result=None,
            error=f'{type(e).__name__}: {str(e)}',
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
        return AsyncExecutionResult(
            result=None,
            error=f'{error_type}: {str(e)}',
            execution_time=time.time() - start_time
        )

def interpret_ast(ast_tree: Any, allowed_modules: List[str], source: str = "", restrict_os: bool = False, namespace: Optional[Dict[str, Any]] = None) -> Any:
    interpreter = ASTInterpreter(allowed_modules=allowed_modules, source=source, restrict_os=restrict_os, namespace=namespace)

    async def run_interpreter():
        result = await interpreter.visit(ast_tree, wrap_exceptions=True)
        if asyncio.iscoroutine(result):
            return await result
        elif hasattr(result, '__aiter__'):
            return [val async for val in result]
        return result

    # Use the current event loop if one is running, otherwise create a new one
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # No running event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        interpreter.loop = loop
        try:
            return loop.run_until_complete(run_interpreter())
        finally:
            loop.close()
    else:
        interpreter.loop = loop
        return asyncio.run_coroutine_threadsafe(run_interpreter(), loop).result()

def interpret_code(source_code: str, allowed_modules: List[str], restrict_os: bool = False, namespace: Optional[Dict[str, Any]] = None) -> Any:
    dedented_source = textwrap.dedent(source_code).strip()
    tree: ast.AST = ast.parse(dedented_source)
    return interpret_ast(tree, allowed_modules, source=dedented_source, restrict_os=restrict_os, namespace=namespace)