import ast
from typing import Any

from .interpreter_core import ASTInterpreter

async def visit_Import(self: ASTInterpreter, node: ast.Import, wrap_exceptions: bool = True) -> None:
    for alias in node.names:
        module_name: str = alias.name
        asname: str = alias.asname if alias.asname is not None else module_name
        if module_name not in self.allowed_modules:
            raise Exception(
                f"Import Error: Module '{module_name}' is not allowed. Only {self.allowed_modules} are permitted."
            )
        self.set_variable(asname, self.modules[module_name])

async def visit_ImportFrom(self: ASTInterpreter, node: ast.ImportFrom, wrap_exceptions: bool = True) -> None:
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