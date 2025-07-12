"""
Sub-workflow support module.

This module contains the SubWorkflowNode class for embedding workflows within workflows.
"""

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .engine import WorkflowEngine
    from .workflow import Workflow


class SubWorkflowNode:
    """A node that executes a sub-workflow with flexible input mapping."""
    
    def __init__(self, sub_workflow: "Workflow", inputs: Dict[str, Any], output: str):
        """Initialize a sub-workflow node with flexible inputs mapping."""
        self.sub_workflow = sub_workflow
        self.inputs = inputs
        self.output = output

    async def __call__(self, engine: "WorkflowEngine"):
        """Execute the sub-workflow with the engine's context using inputs mapping."""
        sub_context = {}
        for sub_key, mapping in self.inputs.items():
            if callable(mapping):
                sub_context[sub_key] = mapping(engine.context)
            elif isinstance(mapping, str):
                sub_context[sub_key] = engine.context.get(mapping)
            else:
                sub_context[sub_key] = mapping
        sub_engine = self.sub_workflow.build(parent_engine=engine)
        result = await sub_engine.run(sub_context)
        return result.get(self.output)
