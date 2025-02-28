"""RAG Tool and related components."""

import importlib
import sys
from typing import Any


class LazyLoader:
    """
    Lazily import a module only when its attributes are accessed.
    This helps reduce startup time by deferring imports until needed.
    """
    def __init__(self, module_path: str):
        self.module_path = module_path
        self._module = None

    def __getattr__(self, name: str) -> Any:
        if self._module is None:
            self._module = importlib.import_module(self.module_path)
        return getattr(self._module, name)


# Map of class names to their import paths
_IMPORTS = {
    "DocumentMetadata": ".document_metadata",
    "QueryResponse": ".query_response",
    "RagTool": ".rag_tool"
}

# Create lazy loaders for each module
_lazy_modules = {}
for cls_name, path in _IMPORTS.items():
    full_path = f"{__package__}{path}"
    if (full_path not in _lazy_modules):
        _lazy_modules[full_path] = LazyLoader(full_path)

# Map each class to its lazy module
_class_to_lazy_module = {}
for cls_name, path in _IMPORTS.items():
    full_path = f"{__package__}{path}"
    _class_to_lazy_module[cls_name] = _lazy_modules[full_path]

# Define __all__ so that import * works properly
__all__ = list(_IMPORTS.keys())

# Set up lazy loading for each class
for cls_name, lazy_module in _class_to_lazy_module.items():
    setattr(sys.modules[__name__], cls_name, getattr(lazy_module, cls_name))
