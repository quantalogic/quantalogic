"""
Flow Package Initialization

This module initializes the flow package and provides package-level imports.
"""

from loguru import logger

# Expose key components for easy importing
from .flow import Nodes, Workflow, WorkflowEngine
from .flow_manager import WorkflowManager  # Changed from FlowManager to WorkflowManager

# Define which symbols are exported when using `from flow import *`
__all__ = [
    'WorkflowManager',  # Changed from FlowManager to WorkflowManager
    'Nodes',
    'Workflow',
    'WorkflowEngine',
]

# Package-level logger configuration
logger.info("Initializing Quantalogic Flow Package")