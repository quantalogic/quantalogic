# quantalogic/flow/flow_manager_schema.py

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, model_validator


class FunctionDefinition(BaseModel):
    type: str
    code: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None


class NodeDefinition(BaseModel):
    function: Optional[str] = None
    sub_workflow: Optional["WorkflowStructure"] = None
    output: Optional[str] = None  # Made optional to align with Node
    retries: int = 3
    delay: float = 1.0
    timeout: Optional[float] = None
    parallel: bool = False

    @model_validator(mode="before")
    @classmethod
    def check_function_or_sub_workflow(cls, data: Any) -> Any:
        """Ensure a node has either a function or a sub-workflow."""
        func = data.get("function")
        sub_wf = data.get("sub_workflow")
        if func is None and sub_wf is None:
            raise ValueError("Node must have either 'function' or 'sub_workflow'")
        if func is not None and sub_wf is not None:
            raise ValueError("Node cannot have both 'function' and 'sub_workflow'")
        return data


class TransitionDefinition(BaseModel):
    from_: str
    to: Union[str, List[str]]
    condition: Optional[str] = None


class WorkflowStructure(BaseModel):
    start: Optional[str] = None
    transitions: List[TransitionDefinition] = []


class WorkflowDefinition(BaseModel):
    functions: Dict[str, FunctionDefinition] = {}
    nodes: Dict[str, NodeDefinition] = {}
    workflow: WorkflowStructure = WorkflowStructure()

# Resolve forward reference
NodeDefinition.model_rebuild()