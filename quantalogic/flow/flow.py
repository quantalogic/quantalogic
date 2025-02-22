from __future__ import annotations

import inspect
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    TypeVar,
)

import anyio
import litellm  # New import for LLM integration
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- Core Definitions ---

class NodeStatus(str, Enum):
    """Enum representing the possible statuses of a workflow node."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"

class WorkflowError(Exception):
    """Custom exception for workflow-related errors."""
    pass

class WorkflowState(BaseModel):
    """State of the workflow, tracking execution details and context."""
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_nodes: Set[str] = Field(default_factory=set)
    context: Dict[str, Any] = Field(default_factory=dict)
    status: Dict[str, NodeStatus] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def update(self, **kwargs):
        """Update the state with new values and refresh the timestamp."""
        self.__dict__.update(kwargs)
        self.updated_at = datetime.now(timezone.utc)

# --- Node Definitions ---

T = TypeVar("T")
R = TypeVar("R")

class Node(BaseModel):
    """Definition of a workflow node, supporting both functions and sub-workflows."""
    name: str
    func: Optional[Callable] = None
    sub_workflow: Optional["Workflow"] = None
    inputs: Set[str]
    output: Optional[str] = None  # Optional to support sub-workflows with implicit outputs
    retries: int = 3
    delay: float = 1.0
    timeout: Optional[float] = None
    parallel: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def check_func_or_sub_workflow(cls, data: Any) -> Any:
        """Ensure a node has either a function or a sub-workflow, but not both."""
        func = data.get("func")
        sub_workflow = data.get("sub_workflow")
        if func is None and sub_workflow is None:
            raise ValueError("Node must have either 'func' or 'sub_workflow'")
        if func is not None and sub_workflow is not None:
            raise ValueError("Node cannot have both 'func' and 'sub_workflow'")
        return data

class Nodes:
    """Registry for workflow nodes with enhanced decorators."""
    _registry: Dict[str, Node] = {}

    @classmethod
    def define(
        cls,
        output: Optional[str] = None,
        retries: int = 3,
        delay: float = 1.0,
        timeout: Optional[float] = None,
        parallel: bool = False,
    ):
        """Base decorator to register a node."""
        def decorator(func: Callable):
            name = func.__name__
            inputs = set(inspect.signature(func).parameters) - {"kwargs"}
            cls._registry[name] = Node(
                name=name,
                func=func,
                inputs=inputs,
                output=output or f"{name}_result",
                retries=retries,
                delay=delay,
                timeout=timeout,
                parallel=parallel,
            )
            return func
        return decorator

    @classmethod
    def validate_node(cls, output: Optional[str] = None, **kwargs):
        """Decorator for validation nodes."""
        return cls.define(output=output, **kwargs)

    @classmethod
    def llm_node(
        cls,
        model: str = "gpt-3.5-turbo",
        system_prompt: Optional[str] = None,  # New: Configurable system prompt
        prompt_template: str = "{input}",
        output: str = "llm_response",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,  # New: Nucleus sampling
        presence_penalty: float = 0.0,  # New: Encourage new topics
        frequency_penalty: float = 0.0,  # New: Reduce repetition
        stop: Optional[List[str]] = None,  # New: Stop sequences
        api_key: Optional[str] = None,  # New: Custom API key
        retries: int = 3,
        delay: float = 1.0,
        timeout: Optional[float] = None,
        parallel: bool = False,
        post_process: Optional[Callable[[str], Any]] = None,
    ):
        """Decorator to register an LLM node with litellm integration."""
        async def call_llm(**kwargs) -> Any:
            # Construct the messages list
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            prompt = prompt_template.format(**kwargs)
            messages.append({"role": "user", "content": prompt})

            # Call litellm with all parameters
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                stop=stop,
                api_key=api_key,
                drop_params=True
            )
            result = response.choices[0].message.content
            return post_process(result) if post_process else result

        def decorator(func: Callable):
            name = func.__name__
            inputs = set(inspect.signature(func).parameters) - {"kwargs"}
            cls._registry[name] = Node(
                name=name,
                func=call_llm,
                inputs=inputs,
                output=output,
                retries=retries,
                delay=delay,
                timeout=timeout,
                parallel=parallel,
            )
            # Define wrapper to expose call_llm for explicit invocation
            async def wrapper(**kwargs):
                return await call_llm(**kwargs)
            wrapper._call_llm = call_llm  # Attach call_llm for use in decorated functions
            return wrapper
        return decorator

    @classmethod
    def get(cls, name: str) -> Node:
        """Retrieve a registered node by name."""
        if name not in cls._registry:
            raise ValueError(f"Node '{name}' not registered")
        return cls._registry[name]

# --- Workflow Definition ---

class Workflow:
    """Class to define the structure of a workflow with reduced boilerplate."""
    def __init__(self, start: str | Callable):
        self.start = start if isinstance(start, str) else start.__name__
        self.nodes: Dict[str, Node] = {}
        self.transitions: Dict[str, List[Callable[[Dict[str, Any]], Optional[Set[str]]]]] = {}

    def node(self, func: Callable | str):
        """Add a node to the workflow."""
        name = func if isinstance(func, str) else func.__name__
        self.nodes[name] = Nodes.get(name)
        self.transitions[name] = []
        return self

    def then(self, target: Callable | str, condition: Callable[[Dict[str, Any]], bool] = lambda _: True):
        """Define a transition to a target node with an optional condition."""
        source = list(self.transitions.keys())[-1]
        target_name = target if isinstance(target, str) else target.__name__
        self.transitions[source].append(lambda ctx: {target_name} if condition(ctx) else set())
        return self

    def parallel(self, *targets: Callable | str, condition: Callable[[Dict[str, Any]], bool] = lambda _: True):
        """Define parallel execution of multiple target nodes."""
        source = list(self.transitions.keys())[-1]
        target_names = {t if isinstance(t, str) else t.__name__ for t in targets}
        self.transitions[source].append(lambda ctx: target_names if condition(ctx) else set())
        return self

    def sequence(self, *nodes: Callable | str):
        """Define a linear sequence of nodes."""
        prev_node = None
        for node in nodes:
            node_name = node if isinstance(node, str) else node.__name__
            if prev_node is None and node_name != self.start:
                raise ValueError(f"Sequence must start with the workflow's start node '{self.start}'")
            self.node(node_name)
            if prev_node:
                self.transitions[prev_node].append(lambda ctx: {node_name})
            prev_node = node_name
        return self

    def loop(self, from_node: Callable | str, to_node: Callable | str, condition: Callable[[Dict[str, Any]], bool]):
        """Define a loop between nodes based on a condition."""
        from_name = from_node if isinstance(from_node, str) else from_node.__name__
        to_name = to_node if isinstance(to_node, str) else to_node.__name__
        self.node(from_name).then(to_name, condition=condition)
        return self

    def add_sub_workflow(self, name: str, sub_wf: "Workflow", inputs: Set[str], output: Optional[str] = None):
        """Add a sub-workflow as a node in the workflow."""
        node = Node(name=name, sub_workflow=sub_wf, inputs=inputs, output=output)
        self.nodes[name] = node
        self.transitions[name] = []
        return self

    def build(self) -> "WorkflowEngine":
        """Build the workflow engine from the defined structure."""
        if self.start not in self.nodes:
            raise ValueError(f"Start node '{self.start}' not defined")
        return WorkflowEngine(self)

# Resolve forward reference for Node
Node.model_rebuild()

# --- Workflow Engine ---

class WorkflowEngine:
    """Engine to execute the workflow."""
    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.state = WorkflowState(current_nodes={workflow.start})

    async def run(self, context: Dict[str, Any] = {}) -> WorkflowState:
        """Run the workflow with the given initial context."""
        self.state.update(context=context)
        while self.state.current_nodes:
            await self._step()
            next_nodes = set()
            for node in self.state.current_nodes:
                for transition in self.workflow.transitions.get(node, []):
                    next_nodes.update(transition(self.state.context))
            self.state.update(current_nodes=next_nodes)
        logger.info(f"Workflow {self.state.execution_id} completed")
        return self.state

    @asynccontextmanager
    async def _node_context(self, node: Node):
        """Manage the execution context of a node."""
        self.state.update(status={**self.state.status, node.name: NodeStatus.RUNNING})
        try:
            yield
            self.state.update(status={**self.state.status, node.name: NodeStatus.SUCCESS})
        except Exception as e:
            self.state.update(status={**self.state.status, node.name: NodeStatus.FAILED})
            raise WorkflowError(f"Node '{node.name}' failed: {e}") from e

    async def _step(self):
        """Execute all current nodes in parallel."""
        async with anyio.create_task_group() as tg:
            for node_name in self.state.current_nodes:
                node = self.workflow.nodes[node_name]
                tg.start_soon(self._execute_node, node)

    async def _execute_node(self, node: Node):
        """Execute a single node with retries and timeout handling, supporting sub-workflows."""
        logger.info(f"Running {node.name}")

        # Check if all required inputs are present
        required_inputs = node.inputs
        available_inputs = set(self.state.context.keys())
        missing = required_inputs - available_inputs
        if missing:
            raise WorkflowError(f"Missing inputs for node '{node.name}': {missing}")

        async def execute_single():
            if node.sub_workflow:
                sub_engine = WorkflowEngine(node.sub_workflow)
                await sub_engine.run(self.state.context)  # Share parent context
                if node.output and node.output not in self.state.context:
                    raise WorkflowError(f"Sub-workflow '{node.name}' did not set output '{node.output}'")
            else:
                args = {k: self.state.context[k] for k in node.inputs}
                if node.timeout:
                    with anyio.fail_after(node.timeout):
                        return await node.func(**args)
                return await node.func(**args)

        async with self._node_context(node):
            for attempt_num in range(node.retries):
                try:
                    result = await execute_single()
                    if node.func and node.output:
                        self.state.context[node.output] = result  # Update context in place
                    return
                except Exception as e:
                    if attempt_num == node.retries - 1:
                        raise
                    logger.warning(f"Retry {attempt_num + 1}/{node.retries} for {node.name}")
                    await anyio.sleep(node.delay * (2**attempt_num))

# --- E-commerce Workflow Nodes ---

@Nodes.validate_node(output="is_valid")
async def validate_order(order: dict) -> bool:
    """Validate the customer order."""
    await anyio.sleep(1)  # Simulate async validation
    return bool(order.get("customer"))

@Nodes.define(output="in_stock")
async def check_inventory(order: dict) -> bool:
    """Check if all items in the order are in stock."""
    await anyio.sleep(1)  # Simulate inventory check
    return len(order["items"]) <= 2

@Nodes.define(output="payment_success", retries=3)
async def process_payment(order: dict) -> bool:
    """Process the customer's payment."""
    await anyio.sleep(1)  # Simulate payment processing
    return order["customer"] == "John Doe"

@Nodes.define(output="shipping_confirmation")
async def ship_order(order: dict) -> str:
    """Ship the order and return confirmation."""
    await anyio.sleep(1)  # Simulate shipping
    return "Shipped"

@Nodes.define(output="notified_out_of_stock")
async def notify_customer_out_of_stock(order: dict) -> bool:
    """Notify customer if items are out of stock."""
    await anyio.sleep(1)  # Simulate notification
    return True

@Nodes.define(output="notified_payment_failed")
async def notify_customer_payment_failed(order: dict) -> bool:
    """Notify customer if payment fails."""
    await anyio.sleep(1)  # Simulate notification
    return True

@Nodes.define(output="order_status_updated")
async def update_order_status(order: dict) -> bool:
    """Update the order status in the system."""
    await anyio.sleep(1)  # Simulate status update
    return True

@Nodes.define(output="confirmation_email_sent")
async def send_confirmation_email(order: dict) -> bool:
    """Send a confirmation email to the customer."""
    await anyio.sleep(1)  # Simulate email sending
    return True

# --- Workflow Definition with Nested Flow ---

# Define a sub-workflow for payment and shipping
payment_shipping_sub_wf = (
    Workflow("process_payment")
    .node("process_payment")
    .then("ship_order", condition=lambda ctx: ctx.get("payment_success"))
    .then("notify_customer_payment_failed", condition=lambda ctx: not ctx.get("payment_success"))
    .node("ship_order")
    .node("notify_customer_payment_failed")
)

# Main workflow incorporating the sub-workflow
workflow = (
    Workflow("validate_order")
    .sequence(
        "validate_order",
        "check_inventory"
    )
    .then("payment_shipping", condition=lambda ctx: ctx.get("in_stock"))
    .then("notify_customer_out_of_stock", condition=lambda ctx: not ctx.get("in_stock"))
    .add_sub_workflow("payment_shipping", payment_shipping_sub_wf, inputs={"order"}, output="shipping_confirmation")
    .parallel("update_order_status", "send_confirmation_email")
    .node("update_order_status")
    .node("send_confirmation_email")
    .node("notify_customer_out_of_stock")
)

# --- Main Execution ---

async def main():
    """Run the e-commerce workflow with a sample order."""
    engine = workflow.build()
    order = {
        "items": ["item1", "item2"],  # 2 items (in stock)
        "customer": "John Doe",  # Payment will succeed
        "payment_info": "credit_card",
    }
    result = await engine.run({"order": order})
    print("Workflow Result:")
    print(result.model_dump())

if __name__ == "__main__":
    anyio.run(main)