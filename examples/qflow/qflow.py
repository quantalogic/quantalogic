from __future__ import annotations

import inspect
import traceback
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import anyio
from loguru import logger
from pydantic import BaseModel, Field, validator


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class WorkflowError(Exception):
    """Base exception for workflow-related errors"""

    pass


class MissingInputsError(WorkflowError):
    """Raised when required inputs are missing for a node"""

    pass


class NodeExecutionError(WorkflowError):
    """Raised when a node fails after maximum retries"""

    pass


class WorkflowState(BaseModel):
    """Represents the current state of a workflow execution"""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_node: str
    node_status: Dict[str, Tuple[NodeStatus, str]] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    execution_log: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())

    @validator("current_node")
    def validate_current_node(cls, v):  # noqa: N805
        if not v:
            raise ValueError("Current node cannot be empty")
        return v


class NodeSpec(BaseModel):
    """Specification for a workflow node"""

    name: str
    inputs: Set[str]
    output: str
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: Optional[float] = None
    description: Optional[str] = None


class TransitionSpec(BaseModel):
    """Specification for a workflow transition"""

    source: str
    condition: str
    target: str


class Workflow(BaseModel):
    """Complete workflow definition"""

    nodes: Dict[str, Tuple[Callable, NodeSpec]] = Field(default_factory=dict)
    transitions: List[TransitionSpec] = Field(default_factory=list)
    entry_node: Optional[str] = None
    version: str = "1.0.0"

    def add_node(
        self,
        name: str,
        func: Callable,
        inputs: List[str],
        output: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        description: Optional[str] = None,
    ):
        """Add a new node to the workflow with parameter validation"""
        sig = inspect.signature(func)
        parameters = sig.parameters

        # Analyze function parameters
        relevant_params = []
        required_params = []
        for param_name, param in parameters.items():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue  # Skip *args and **kwargs
            relevant_params.append(param_name)
            if param.default is inspect.Parameter.empty:
                required_params.append(param_name)

        # Check for **kwargs
        has_kwargs = any(p.kind == p.VAR_KEYWORD for p in parameters.values())

        # Validate inputs against parameters unless **kwargs exists
        if not has_kwargs:
            invalid_inputs = set(inputs) - set(relevant_params)
            if invalid_inputs:
                raise ValueError(
                    f"Node '{name}' has invalid inputs {invalid_inputs} "
                    f"not present in function '{func.__name__}' parameters"
                )

        # Validate required parameters
        missing_required = set(required_params) - set(inputs)
        if missing_required:
            raise ValueError(
                f"Node '{name}' missing required inputs {missing_required} " f"for function '{func.__name__}'"
            )

        node_spec = NodeSpec(
            name=name,
            inputs=set(inputs),
            output=output,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            description=description,
        )
        self.nodes[name] = (func, node_spec)

    def add_transition(self, source: str, condition: str, target: str):
        """Add a transition between nodes"""
        self.transitions.append(TransitionSpec(source=source, condition=condition, target=target))


class WorkflowEngine:
    """Execution engine for workflows"""

    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.state: Optional[WorkflowState] = None

    async def execute(self, initial_context: Dict[str, Any]) -> WorkflowState:
        """Execute the workflow with the provided initial context"""
        if not self.workflow.entry_node:
            raise ValueError("Workflow has no entry node defined")

        self.state = WorkflowState(current_node=self.workflow.entry_node, context=initial_context.copy())

        while True:
            node_name = self.state.current_node
            logger.info(f"Executing node: {node_name}")

            if node_name not in self.workflow.nodes:
                raise ValueError(f"Undefined node: {node_name}")

            func, node_spec = self.workflow.nodes[node_name]
            self._update_node_status(node_name, NodeStatus.RUNNING)

            try:
                result = await self._execute_node(func, node_spec)
                self._update_context(node_spec.output, result)

                # Use node output as transition condition if available
                transition_condition = "success"
                if isinstance(result, str) and result in ["next", "complete"]:
                    transition_condition = result

                next_node = self._get_next_node(node_name, transition_condition)
                self._update_node_status(node_name, NodeStatus.SUCCESS)
            except Exception as e:
                logger.error(
                    "Node execution failed",
                    node=node_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    context=self.state.context,
                    state=self.state.dict(),
                )
                self._handle_node_error(node_name, e)
                next_node = self._get_next_node(node_name, "failed")
                if not next_node:
                    raise WorkflowError(f"Workflow failed at node {node_name}") from e

            if not next_node:
                logger.success("Workflow completed successfully")
                break

            self._advance_to_node(next_node)

        return self.state

    def _update_context(self, output_key: str, value: Any) -> None:
        """Update workflow context with node output"""
        logger.debug(f"Updating context with {output_key}={value}")
        self.state.context[output_key] = value
        self.state.updated_at = datetime.now()

    def _advance_to_node(self, next_node: str):
        """Move workflow to the next node"""
        self.state.current_node = next_node
        self.state.updated_at = datetime.now()

    def _update_node_status(self, node_name: str, status: NodeStatus, message: str = ""):
        """Update the status of a node in the workflow state"""
        self.state.node_status[node_name] = (status, message)
        self.state.execution_log.append(
            {"timestamp": datetime.now(), "node": node_name, "status": status, "message": message}
        )

    def _handle_node_error(self, node_name: str, error: Exception):
        """Handle node execution errors and update state"""
        error_info = {
            "error_type": type(error).__name__,
            "message": str(error),
            "node": node_name,
            "timestamp": datetime.now().isoformat(),
            "context": self.state.context,
            "stack_trace": traceback.format_exc(),
        }

        logger.error("Node execution failed", **error_info, state=self.state.dict(exclude={"context"}))

        self._update_node_status(node_name, NodeStatus.FAILED, f"{error_info['error_type']}: {error_info['message']}")

    async def _execute_node(self, func: Callable, node_spec: NodeSpec) -> Any:
        """Execute a node with retry logic and timeout handling"""
        self._validate_node_inputs(node_spec)
        args = self._prepare_node_arguments(node_spec)

        for attempt in range(node_spec.max_retries + 1):
            try:
                return await self._run_node_with_timeout(func, args, node_spec.timeout)
            except Exception as e:
                if attempt == node_spec.max_retries:
                    raise NodeExecutionError(
                        f"Node {node_spec.name} failed after {node_spec.max_retries} attempts"
                    ) from e
                await self._handle_retry(node_spec, attempt, e)

        raise RuntimeError("Unreachable code")

    def _validate_node_inputs(self, node_spec: NodeSpec):
        """Validate that all required inputs are present in the context"""
        missing = node_spec.inputs - self.state.context.keys()
        if missing:
            raise MissingInputsError(f"Missing inputs for {node_spec.name}: {missing}")

    def _prepare_node_arguments(self, node_spec: NodeSpec) -> Dict[str, Any]:
        """Prepare arguments for node execution from context"""
        return {k: self.state.context[k] for k in node_spec.inputs}

    async def _run_node_with_timeout(self, func: Callable, args: Dict[str, Any], timeout: Optional[float]):
        """Execute node function with optional timeout"""
        if timeout:
            with anyio.fail_after(timeout):
                return await func(**args)
        return await func(**args)

    async def _handle_retry(self, node_spec: NodeSpec, attempt: int, error: Exception):
        """Handle retry logic with exponential backoff"""
        self._update_node_status(node_spec.name, NodeStatus.RETRYING, str(error))
        delay = node_spec.retry_delay * (2**attempt)
        logger.warning(f"Retry {attempt+1}/{node_spec.max_retries} for {node_spec.name}")
        await anyio.sleep(delay)

    def _get_next_node(self, current: str, outcome: str) -> Optional[str]:
        """Determine the next node based on current node and outcome"""
        for transition in self.workflow.transitions:
            if transition.source == current and transition.condition == outcome:
                return transition.target
        return None
