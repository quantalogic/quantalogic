import ast
from typing import Any, Dict, List

from .function_utils import Function
from .interpreter_core import ASTInterpreter

async def visit_ClassDef(self: ASTInterpreter, node: ast.ClassDef, wrap_exceptions: bool = True) -> Any:
    base_frame = {}
    self.env_stack.append(base_frame)
    bases = [await self.visit(base, wrap_exceptions=True) for base in node.bases]
    try:
        # Removed self.current_class = node; it’s now set in _create_class_instance
        for stmt in node.body:
            await self.visit(stmt, wrap_exceptions=True)
        class_dict = {k: v for k, v in self.env_stack[-1].items() if k not in ["__builtins__"]}
        cls = type(node.name, tuple(bases), class_dict)
        for name, value in class_dict.items():
            if isinstance(value, Function):
                value.defining_class = cls
        self.env_stack[-2][node.name] = cls
        # Change: Rely on _create_class_instance to set self.current_class to cls,
        # avoiding AST node usage here, which aligns with super() expectations.
        return cls
    finally:
        self.env_stack.pop()
        # self.current_class is reset in _create_class_instance, not here