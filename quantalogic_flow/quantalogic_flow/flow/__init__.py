"""
Flow Package Initialization

This module initializes the flow package and provides package-level imports.
Now supports nested workflows for hierarchical flow definitions.

Key Visualization Utilities:
- generate_mermaid_diagram(): Convert workflow definitions to visual Mermaid flowcharts
    - Supports pastel-colored node styling
    - Generates interactive, readable workflow diagrams
    - Handles complex workflows with multiple node types

    - Generates descriptive labels
    - Supports conditional node detection
"""

from loguru import logger

# Expose key components for easy importing
from .flow import Nodes, Workflow, WorkflowEngine
from .flow import WorkflowEvent, WorkflowEventType
from .flow_extractor import extract_workflow_from_file
from .flow_generator import generate_executable_script
from .flow_manager import WorkflowManager
from .flow_mermaid import generate_mermaid_diagram
from .flow_validator import validate_workflow_definition

# Define which symbols are exported when using `from flow import *`
__all__ = [
    "WorkflowManager",
    "Nodes",
    "Workflow",
    "WorkflowEngine",
    "WorkflowEvent",
    "WorkflowEventType",
    "generate_mermaid_diagram",
    "extract_workflow_from_file",
    "generate_executable_script",
    "validate_workflow_definition"
]

# Package-level logger configuration
logger.info("Initializing Quantalogic Flow Package")
