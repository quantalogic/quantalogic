from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FunctionDefinition(BaseModel):
    """Definition of a function used in the workflow."""
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
        """Ensure the function definition is valid based on its type.

        Args:
            data: Raw data to validate.

        Returns:
            Validated data.

        Raises:
            ValueError: If the function source configuration is invalid.
        """
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
        default="gpt-3.5-turbo",
        description=(
            "The LLM model to use. Can be a static model name (e.g., 'gpt-3.5-turbo', 'gemini/gemini-2.0-flash') "
            "or a lambda expression (e.g., 'lambda ctx: ctx.get(\"model_name\")') for dynamic selection."
        ),
    )
    system_prompt: Optional[str] = Field(None, description="System prompt defining the LLM's role or context.")
    system_prompt_file: Optional[str] = Field(
        None,
        description="Path to an external Jinja2 template file for the system prompt. Takes precedence over system_prompt."
    )
    prompt_template: str = Field(
        default="{{ input }}", description="Jinja2 template for the user prompt. Ignored if prompt_file is set."
    )
    prompt_file: Optional[str] = Field(
        None, description="Path to an external Jinja2 template file. Takes precedence over prompt_template."
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
    stop: Optional[List[str]] = Field(None, description="List of stop sequences for LLM generation.")
    response_model: Optional[str] = Field(
        None,
        description="Path to a Pydantic model for structured output (e.g., 'my_module:OrderDetails')."
    )
    api_key: Optional[str] = Field(None, description="Custom API key for the LLM provider, if required.")

    @model_validator(mode="before")
    @classmethod
    def check_prompt_source(cls, data: Any) -> Any:
        """Ensure prompt_file and prompt_template are used appropriately.

        Args:
            data: Raw data to validate.

        Returns:
            Validated data.

        Raises:
            ValueError: If prompt configuration is invalid.
        """
        prompt_file = data.get("prompt_file")
        if prompt_file and not isinstance(prompt_file, str):
            raise ValueError("prompt_file must be a string path to a Jinja2 template file")
        return data


class TemplateConfig(BaseModel):
    """Configuration for template-based nodes."""
    template: str = Field(
        default="", description="Jinja2 template string to render. Ignored if template_file is set."
    )
    template_file: Optional[str] = Field(
        None, description="Path to an external Jinja2 template file. Takes precedence over template."
    )

    @model_validator(mode="before")
    @classmethod
    def check_template_source(cls, data: Any) -> Any:
        """Ensure template_file and template are used appropriately.

        Args:
            data: Raw data to validate.

        Returns:
            Validated data.

        Raises:
            ValueError: If template configuration is invalid.
        """
        template_file = data.get("template_file")
        template = data.get("template")
        if not template and not template_file:
            raise ValueError("Either 'template' or 'template_file' must be provided")
        if template and template_file:
            raise ValueError("Cannot provide both 'template' and 'template_file' - they are mutually exclusive")
        if template_file and not isinstance(template_file, str):
            raise ValueError("template_file must be a string path to a Jinja2 template file")
        return data


class NodeDefinition(BaseModel):
    """Definition of a workflow node with template_node and inputs_mapping support."""
    
    model_config = ConfigDict(extra="allow")  # Allow extra fields like 'requirements'
    
    function: Optional[str] = Field(
        None, description="Name of the function to execute (references a FunctionDefinition)."
    )
    sub_workflow: Optional["WorkflowStructure"] = Field(
        None, description="Nested workflow definition for sub-workflow nodes."
    )
    llm_config: Optional[LLMConfig] = Field(None, description="Configuration for LLM-based nodes.")
    template_config: Optional[TemplateConfig] = Field(None, description="Configuration for template-based nodes.")
    inputs_mapping: Optional[Dict[str, str]] = Field(
        None,
        description="Mapping of node inputs to context keys or stringified lambda expressions (e.g., 'lambda ctx: value')."
    )
    output: Optional[str] = Field(
        None,
        description="Context key to store the node's result. Defaults to '<node_name>_result' if applicable."
    )
    retries: int = Field(default=3, ge=0, description="Number of retry attempts on failure.")
    delay: float = Field(default=1.0, ge=0.0, description="Delay in seconds between retries.")
    timeout: Optional[float] = Field(
        None, ge=0.0, description="Maximum execution time in seconds (null for no timeout)."
    )
    parallel: bool = Field(default=False, description="Whether the node can execute in parallel with others.")

    @model_validator(mode="before")
    @classmethod
    def check_function_or_sub_workflow_or_llm_or_template(cls, data: Any) -> Any:
        """Ensure a node has exactly one of 'function', 'sub_workflow', 'llm_config', or 'template_config'.

        Args:
            data: Raw data to validate.

        Returns:
            Validated data.

        Raises:
            ValueError: If node type configuration is invalid.
        """
        func = data.get("function")
        sub_wf = data.get("sub_workflow")
        llm = data.get("llm_config")
        template = data.get("template_config")
        if sum(x is not None for x in (func, sub_wf, llm, template)) != 1:
            raise ValueError("Node must have exactly one of 'function', 'sub_workflow', 'llm_config', or 'template_config'")
        return data


class BranchCondition(BaseModel):
    """Definition of a branch condition for a transition."""
    to_node: str = Field(
        ..., description="Target node name for this branch."
    )
    condition: Optional[str] = Field(
        None, description="Python expression using 'ctx' for conditional branching."
    )


class TransitionDefinition(BaseModel):
    """Definition of a transition between nodes."""
    from_node: str = Field(
        ...,
        description="Source node name for the transition.",
    )
    to_node: Union[str, List[Union[str, BranchCondition]]] = Field(
        ...,
        description=(
            "Target node(s). Can be: a string, list of strings (parallel), or list of BranchCondition (branching)."
        ),
    )
    condition: Optional[str] = Field(
        None,
        description="Python expression using 'ctx' for simple transitions."
    )


class LoopDefinition(BaseModel):
    """Definition of a loop within the workflow, supports nesting."""
    nodes: List[str] = Field(..., description="List of node names in the loop.")
    condition: str = Field(..., description="Python expression using 'ctx' for the loop condition (when to exit).")
    exit_node: str = Field(..., description="Node to transition to when the loop ends.")
    entry_node: Optional[str] = Field(None, description="Node that enters the loop (defaults to first node).")
    nested_loops: List["LoopDefinition"] = Field(
        default_factory=list, description="List of nested loops within this loop."
    )
    loop_id: Optional[str] = Field(None, description="Unique identifier for the loop (auto-generated if not provided).")


class WorkflowStructure(BaseModel):
    """Structure defining the workflow's execution flow."""
    start: Optional[str] = Field(None, description="Name of the starting node.")
    transitions: List[TransitionDefinition] = Field(
        default_factory=list, description="List of transitions between nodes."
    )
    loops: List[LoopDefinition] = Field(
        default_factory=list, description="List of loop definitions (optional, for explicit loop support)."
    )
    convergence_nodes: List[str] = Field(
        default_factory=list, description="List of nodes where branches converge."
    )

    # @model_validator(mode="before")
    # @classmethod
    # def check_loop_nodes(cls, data: Any) -> Any:
    #     """Ensure all nodes in loops exist in the workflow.
    #
    #     Args:
    #         data: Raw data to validate.
    #
    #     Returns:
    #         Validated data.
    #
    #     Raises:
    #         ValueError: If loop nodes are not defined.
    #     """
    #     loops = data.get("loops", [])
    #     nodes = set(data.get("nodes", {}).keys())
    #     for loop in loops:
    #         for node in loop["nodes"] + [loop["exit_node"]]:
    #             if node not in nodes:
    #                 raise ValueError(f"Loop node '{node}' not defined in nodes")
    #     return data


class WorkflowDefinition(BaseModel):
    """Top-level definition of the workflow."""
    
    model_config = ConfigDict(extra="allow")  # Allow extra fields for compatibility
    
    functions: Dict[str, FunctionDefinition] = Field(
        default_factory=dict, description="Dictionary of function definitions."
    )
    nodes: Dict[str, NodeDefinition] = Field(default_factory=dict, description="Dictionary of node definitions.")
    workflow: WorkflowStructure = Field(
        default_factory=lambda: WorkflowStructure(start=None), description="Main workflow structure."
    )
    observers: List[str] = Field(
        default_factory=list, description="List of observer function names."
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of Python module dependencies."
    )


NodeDefinition.model_rebuild()
LoopDefinition.model_rebuild()