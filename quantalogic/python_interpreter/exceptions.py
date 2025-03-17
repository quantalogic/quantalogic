# quantalogic/python_interpreter/exceptions.py
import ast
from typing import Any, List

class ReturnException(Exception):
    def __init__(self, value: Any) -> None:
        self.value: Any = value

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

class BaseExceptionGroup(Exception):
    def __init__(self, message: str, exceptions: List[Exception]):
        super().__init__(message)
        self.exceptions = exceptions
        self.message = message

    def __str__(self):
        return f"{self.message}: {', '.join(str(e) for e in self.exceptions)}"

class WrappedException(Exception):
    def __init__(self, message: str, original_exception: Exception, lineno: int, col: int, context_line: str):
        super().__init__(message)
        self.original_exception: Exception = original_exception
        self.lineno: int = lineno
        self.col: int = col
        self.context_line: str = context_line
        self.message = str(original_exception)  # Correct variable name

def has_await(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Await):
            return True
    return False