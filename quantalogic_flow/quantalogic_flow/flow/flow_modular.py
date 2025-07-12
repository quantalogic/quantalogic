#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru>=0.7.2",              # Logging utility
#     "litellm>=1.0.0",             # LLM integration
#     "pydantic>=2.0.0",            # Data validation and settings
#     "anyio>=4.0.0",               # Async utilities
#     "jinja2>=3.1.0",              # Templating engine
#     "instructor"  # Structured LLM output with litellm integration
# ]
# ///

"""
Modular Flow Package - Compatibility Layer

This module maintains 100% API compatibility with the original flow.py while
using a modular architecture underneath. All imports and usage patterns remain identical.
"""

import asyncio

from loguru import logger

# Import all components from the modular structure
from .core import (
    SubWorkflowNode,
    Workflow,
    WorkflowEngine,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowObserver,
)
from .examples import example_workflow
from .nodes import Nodes
from .template import TEMPLATES_DIR, get_template_path

# Re-export everything to maintain API compatibility
__all__ = [
    'WorkflowEventType', 'WorkflowEvent', 'WorkflowObserver',
    'SubWorkflowNode', 'WorkflowEngine', 'Workflow', 
    'Nodes', 'get_template_path', 'TEMPLATES_DIR',
    'example_workflow'
]

# Main execution for backward compatibility
if __name__ == "__main__":
    logger.info("Initializing Quantalogic Flow Package")
    asyncio.run(example_workflow())
