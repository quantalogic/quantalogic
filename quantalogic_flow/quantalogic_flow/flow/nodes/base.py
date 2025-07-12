"""
Base nodes module.

This module contains the base node functionality and registry.
"""

from typing import Callable, Dict, List, Tuple


class NodeRegistry:
    """Registry for workflow nodes."""
    
    def __init__(self):
        self._registry: Dict[str, Tuple[Callable, List[str], str | None]] = {}
    
    def register(self, name: str, func: Callable, inputs: List[str], output: str | None):
        """Register a node in the registry."""
        self._registry[name] = (func, inputs, output)
    
    def get(self, name: str) -> Tuple[Callable, List[str], str | None] | None:
        """Get a node from the registry."""
        return self._registry.get(name)
    
    def __contains__(self, name: str) -> bool:
        """Check if a node is registered."""
        return name in self._registry
    
    def __getitem__(self, name: str) -> Tuple[Callable, List[str], str | None]:
        """Get a node from the registry using bracket notation."""
        return self._registry[name]


# Global node registry
NODE_REGISTRY = NodeRegistry()
