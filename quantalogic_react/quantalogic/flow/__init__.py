"""Stub alias for backwards compatibility: re-export Flow API from the quantalogic_flow package."""
from quantalogic_flow import (
    Nodes,
    Workflow,
    WorkflowEngine,
    WorkflowManager,
    extract_workflow_from_file,
    generate_executable_script,
    generate_mermaid_diagram,
    validate_workflow_definition,
)

__all__ = [
    "extract_workflow_from_file",
    "generate_executable_script",
    "generate_mermaid_diagram",
    "Nodes",
    "validate_workflow_definition",
    "Workflow",
    "WorkflowEngine",
    "WorkflowManager",
]
