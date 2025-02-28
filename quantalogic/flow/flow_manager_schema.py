from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator


class FunctionDefinition(BaseModel):
    """
    Definition of a function used in the workflow.

    This model supports both embedded functions (inline code) and external functions sourced
    from Python modules, including PyPI packages, local files, or remote URLs.
    """

    type: str = Field(
        ...,
        description="Type of function source. Must be 'embedded' for inline code or 'external' for module-based functions.",
    )
    code: Optional[str] = Field(
        None, description="Multi-line Python code for embedded functions. Required if type is 'embedded'."
    )
    module: Optional[str] = Field(
        None,
        description=(
            "Source of the external module for 'external' functions. Can be:"
            " - A PyPI package name (e.g., 'requests', 'numpy') installed in the environment."
            " - A local file path (e.g., '/path/to/module.py')."
            " - A remote URL (e.g., 'https://example.com/module.py')."
            " Required if type is 'external'."
        ),
    )
    function: Optional[str] = Field(
        None,
        description="Name of the function within the module for 'external' functions. Required if type is 'external'.",
    )

    @model_validator(mode="before")
    @classmethod
    def check_function_source(cls, data: Any) -> Any:
        """Ensure the function definition is valid based on its type."""
        type_ = data.get("type")
        if type_ == "embedded":
            if not data.get("code"):
                raise ValueError("Embedded functions require 'code' to be specified")
            if data.get("module") or data.get("function"):
                raise ValueError("Embedded functions should not specify 'module' or 'function'")
        elif type_ == "external":
            if not data.get("module") or not data.get("function"):
                raise ValueError("External functions require both 'module' and 'function'")
            if data.get("code"):
                raise ValueError("External functions should not specify 'code'")
        else:
            raise ValueError("Function type must be 'embedded' or 'external'")
        return data


class LLMConfig(BaseModel):
    """Configuration for LLM-based nodes."""

    model: str = Field(
        default="gpt-3.5-turbo", description="The LLM model to use (e.g., 'gpt-3.5-turbo', 'gemini/gemini-2.0-flash')."
    )
    system_prompt: Optional[str] = Field(None, description="System prompt defining the LLM's role or context.")
    prompt_template: str = Field(
        default="{{ input }}", description="Jinja2 template for the user prompt (e.g., 'Summarize {{ text }}')."
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Controls randomness of LLM output (0.0 to 1.0)."
    )
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum number of tokens in the response.")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter (0.0 to 1.0).")
    presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Penalty for repeating topics (-2.0 to 2.0)."
    )
    frequency_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="Penalty for repeating words (-2.0 to 2.0)."
    )
    stop: Optional[List[str]] = Field(None, description="List of stop sequences for LLM generation (e.g., ['\\n']).")
    response_model: Optional[str] = Field(
        None,
        description=(
            "Path to a Pydantic model for structured output (e.g., 'my_module:OrderDetails'). "
            "If specified, uses structured_llm_node; otherwise, uses llm_node."
        ),
    )
    api_key: Optional[str] = Field(None, description="Custom API key for the LLM provider, if required.")


class NodeDefinition(BaseModel):
    """
    Definition of a workflow node.

    A node must specify exactly one of 'function', 'sub_workflow', or 'llm_config'.
    """

    function: Optional[str] = Field(
        None, description="Name of the function to execute (references a FunctionDefinition)."
    )
    sub_workflow: Optional["WorkflowStructure"] = Field(
        None, description="Nested workflow definition for sub-workflow nodes."
    )
    llm_config: Optional[LLMConfig] = Field(None, description="Configuration for LLM-based nodes.")
    output: Optional[str] = Field(
        None,
        description=(
            "Context key to store the node's result. Defaults to '<node_name>_result' "
            "for function or LLM nodes if not specified."
        ),
    )
    retries: int = Field(default=3, ge=0, description="Number of retry attempts on failure.")
    delay: float = Field(default=1.0, ge=0.0, description="Delay in seconds between retries.")
    timeout: Optional[float] = Field(
        None, ge=0.0, description="Maximum execution time in seconds (null for no timeout)."
    )
    parallel: bool = Field(default=False, description="Whether the node can execute in parallel with others.")

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
    """Definition of a transition between nodes."""

    from_: str = Field(
        ...,
        description="Source node name for the transition.",
        alias="from",  # Supports YAML aliasing
    )
    to: Union[str, List[str]] = Field(
        ..., description="Target node(s). A string for sequential, a list for parallel execution."
    )
    condition: Optional[str] = Field(
        None, description="Python expression using 'ctx' for conditional transitions (e.g., 'ctx.get(\"in_stock\")')."
    )


class WorkflowStructure(BaseModel):
    """Structure defining the workflow's execution flow."""

    start: Optional[str] = Field(None, description="Name of the starting node.")
    transitions: List[TransitionDefinition] = Field(
        default_factory=list, description="List of transitions between nodes."
    )


class WorkflowDefinition(BaseModel):
    """Top-level definition of the workflow."""

    functions: Dict[str, FunctionDefinition] = Field(
        default_factory=dict, description="Dictionary of function definitions used in the workflow."
    )
    nodes: Dict[str, NodeDefinition] = Field(default_factory=dict, description="Dictionary of node definitions.")
    workflow: WorkflowStructure = Field(
        default_factory=WorkflowStructure, description="Main workflow structure with start node and transitions."
    )
    observers: List[str] = Field(
        default_factory=list, description="List of observer function names to monitor workflow execution."
    )


# Resolve forward reference for sub_workflow in NodeDefinition
NodeDefinition.model_rebuild()
