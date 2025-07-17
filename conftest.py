import sys
from pathlib import Path

import pytest
from quantalogic_flow.flow.nodes.base import NODE_REGISTRY

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def clear_node_registry():
    """Fixture to clear the node registry after each test."""
    original_registry = NODE_REGISTRY._registry.copy()
    yield
    NODE_REGISTRY._registry.clear()
    NODE_REGISTRY._registry.update(original_registry)


@pytest.fixture
def sample_fixture():
    return "Hello, World!"