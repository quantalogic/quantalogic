from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, model_validator


class FunctionDefinition(BaseModel):
    type: str
    code: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None


class LLMConfig(BaseModel):
    """Configuration for LLM-based nodes."""
    model: str = "gpt-3.5-turbo"
    system_prompt: Optional[str] = None
    prompt_template: str = "{{ input }}"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    stop: Optional[List[str]] = None
    response_model: Optional[str] = None  # e.g., "path.to.module:ClassName" for structured_llm_node
    api_key: Optional[str] = None


class NodeDefinition(BaseModel):
    function: Optional[str] = None
    sub_workflow: Optional["WorkflowStructure"] = None
    llm_config: Optional[LLMConfig] = None
    output: Optional[str] = None
    retries: int = 3
    delay: float = 1.0
    timeout: Optional[float] = None
    parallel: bool = False

    @model_validator(mode="before")
    @classmethod
    def check_function_or_sub_workflow_or_llm(cls, data: Any) -> Any:
        """Ensure a node has exactly one of 'function', 'sub_workflow', or 'llm_config'."""
        func = data.get("function")
        sub_wf = data.get("sub_workflow")
        llm = data.get("llm_config")
        if sum(x is not None for x in (func, sub_wf, llm)) != 1:
            raise ValueError("Node must have exactly one of 'function', 'sub_workflow', or 'llm_config'")
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


# Resolve forward reference for sub_workflow
NodeDefinition.model_rebuild()