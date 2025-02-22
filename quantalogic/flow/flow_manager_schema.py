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
    llm_config: Optional[Dict[str, Any]] = None  # Supports LLM parameters like system_prompt, top_p, etc.
    output: Optional[str] = None  # Made optional to align with Node
    retries: int = 3
    delay: float = 1.0
    timeout: Optional[float] = None
    parallel: bool = False

    @model_validator(mode="before")
    @classmethod
    def check_function_or_sub_workflow(cls, data: Any) -> Any:
        """Ensure a node has either a function, sub-workflow, or LLM config, but not more than one."""
        func = data.get("function")
        sub_wf = data.get("sub_workflow")
        llm = data.get("llm_config")
        if all(x is None for x in (func, sub_wf, llm)):
            raise ValueError("Node must have either 'function', 'sub_workflow', or 'llm_config'")
        if sum(x is not None for x in (func, sub_wf, llm)) > 1:
            raise ValueError("Node cannot have more than one of 'function', 'sub_workflow', or 'llm_config'")
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