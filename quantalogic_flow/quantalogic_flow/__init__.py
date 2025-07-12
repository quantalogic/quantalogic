"""Quantalogic Flow package"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("quantalogic-flow")
except PackageNotFoundError:
    __version__ = "0.6.8"

from loguru import logger

# Expose key components for easy import
from .flow import Nodes, Workflow, WorkflowEngine
from .flow.flow_extractor import extract_workflow_from_file
from .flow.flow_generator import generate_executable_script
from .flow.flow_manager import WorkflowManager
from .flow.flow_mermaid import generate_mermaid_diagram
from .flow.flow_validator import validate_workflow_definition

__all__ = [
    "WorkflowManager",
    "Nodes",
    "Workflow",
    "WorkflowEngine",
    "generate_mermaid_diagram",
    "extract_workflow_from_file",
    "generate_executable_script",
    "validate_workflow_definition",
]

logger.info("Initializing Quantalogic Flow Package")
