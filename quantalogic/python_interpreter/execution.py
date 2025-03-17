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

def optimize_ast(tree: ast.AST) -> ast.AST:
    """Perform basic constant folding on the AST."""
    class ConstantFolder(ast.NodeTransformer):
        def visit_BinOp(self, node):
            self.generic_visit(node)
            if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                left, right = node.left.value, node.right.value
                if isinstance(node.op, ast.Add) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return ast.Constant(value=left + right)
                elif isinstance(node.op, ast.Mult) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return ast.Constant(value=left * right)
            return node
    return ConstantFolder().visit(tree)

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
    loop_created = False
    loop = None
    try:
        ast_tree = optimize_ast(ast.parse(textwrap.dedent(code)))
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop_created = True
        
        interpreter = ASTInterpreter(
            allowed_modules=allowed_modules,
            restrict_os=True,
            namespace=namespace
        )
        interpreter.loop = loop
        
        async def run_execution():
            return await interpreter.execute_async(ast_tree)
        
        await asyncio.wait_for(run_execution(), timeout=timeout)
        
        if entry_point:
            func = interpreter.env_stack[0].get(entry_point)
            if not func:
                raise NameError(f"Function '{entry_point}' not found in the code")
            args = args or ()
            kwargs = kwargs or {}
            if isinstance(func, AsyncFunction) or asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            elif isinstance(func, Function):
                result = await func(*args, **kwargs)  # Direct await, no unnecessary wait_for
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await asyncio.wait_for(result, timeout=timeout)
            if asyncio.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=timeout)
        else:
            result = await interpreter.execute_async(ast_tree)  # Capture the module result
        
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
    finally:
        if loop_created and loop and not loop.is_closed():
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
            loop.close()

def interpret_ast(ast_tree: ast.AST, allowed_modules: List[str], source: str = "", restrict_os: bool = False, namespace: Optional[Dict[str, Any]] = None) -> Any:
    ast_tree = optimize_ast(ast_tree)
    interpreter = ASTInterpreter(allowed_modules=allowed_modules, source=source, restrict_os=restrict_os, namespace=namespace)
    loop_created = False

    async def run_interpreter():
        result = await interpreter.visit(ast_tree, wrap_exceptions=True)
        return result

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop_created = True
        interpreter.loop = loop
        try:
            return loop.run_until_complete(run_interpreter())
        finally:
            if not loop.is_closed():
                loop.close()
    else:
        interpreter.loop = loop
        return asyncio.run_coroutine_threadsafe(run_interpreter(), loop).result()

def interpret_code(source_code: str, allowed_modules: List[str], restrict_os: bool = False, namespace: Optional[Dict[str, Any]] = None) -> Any:
    dedented_source = textwrap.dedent(source_code).strip()
    tree: ast.AST = ast.parse(dedented_source)
    return interpret_ast(tree, allowed_modules, source=dedented_source, restrict_os=restrict_os, namespace=namespace)