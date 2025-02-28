#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio",
#     "jinja2",
#     "instructor[litellm]"  # Required for structured_llm_node
# ]
# ///

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import instructor
from jinja2 import Template
from litellm import acompletion
from loguru import logger
from pydantic import BaseModel, ValidationError


# Define event types and structure for observer system
class WorkflowEventType(Enum):
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    TRANSITION_EVALUATED = "transition_evaluated"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    SUB_WORKFLOW_ENTERED = "sub_workflow_entered"
    SUB_WORKFLOW_EXITED = "sub_workflow_exited"


@dataclass
class WorkflowEvent:
    event_type: WorkflowEventType
    node_name: Optional[str]
    context: Dict[str, Any]
    result: Optional[Any] = None
    exception: Optional[Exception] = None
    transition_from: Optional[str] = None
    transition_to: Optional[str] = None
    sub_workflow_name: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None  # Added to store token usage and cost


WorkflowObserver = Callable[[WorkflowEvent], None]


# Define a class for sub-workflow nodes
class SubWorkflowNode:
    def __init__(self, sub_workflow: "Workflow", inputs: Dict[str, str], output: str):
        """Initialize a sub-workflow node."""
        self.sub_workflow = sub_workflow
        self.inputs = inputs
        self.output = output

    async def __call__(self, engine: "WorkflowEngine", **kwargs):
        """Execute the sub-workflow with the engine's context."""
        sub_context = {sub_key: kwargs[main_key] for main_key, sub_key in self.inputs.items()}
        sub_engine = self.sub_workflow.build(parent_engine=engine)
        result = await sub_engine.run(sub_context)
        return result.get(self.output)


class WorkflowEngine:
    def __init__(self, workflow, parent_engine: Optional["WorkflowEngine"] = None):
        """Initialize the WorkflowEngine with a workflow and optional parent for sub-workflows."""
        self.workflow = workflow
        self.context = {}
        self.observers: List[WorkflowObserver] = []
        self.parent_engine = parent_engine  # Link to parent engine for sub-workflow observer propagation

    def add_observer(self, observer: WorkflowObserver) -> None:
        """Register an event observer callback."""
        if observer not in self.observers:
            self.observers.append(observer)
            logger.debug(f"Added observer: {observer}")
        if self.parent_engine:
            self.parent_engine.add_observer(observer)  # Propagate to parent for global visibility

    def remove_observer(self, observer: WorkflowObserver) -> None:
        """Remove an event observer callback."""
        if observer in self.observers:
            self.observers.remove(observer)
            logger.debug(f"Removed observer: {observer}")

    async def _notify_observers(self, event: WorkflowEvent) -> None:
        """Asynchronously notify all observers of an event."""
        tasks = []
        for observer in self.observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    tasks.append(observer(event))
                else:
                    observer(event)
            except Exception as e:
                logger.error(f"Observer {observer} failed for {event.event_type.value}: {e}")
        if tasks:
            await asyncio.gather(*tasks)

    async def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow starting from the entry node with event notifications."""
        self.context = initial_context.copy()
        await self._notify_observers(
            WorkflowEvent(event_type=WorkflowEventType.WORKFLOW_STARTED, node_name=None, context=self.context)
        )

        current_node = self.workflow.start_node
        while current_node:
            logger.info(f"Executing node: {current_node}")
            await self._notify_observers(
                WorkflowEvent(event_type=WorkflowEventType.NODE_STARTED, node_name=current_node, context=self.context)
            )

            node_func = self.workflow.nodes.get(current_node)
            if not node_func:
                logger.error(f"Node {current_node} not found")
                exc = ValueError(f"Node {current_node} not found")
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.NODE_FAILED,
                        node_name=current_node,
                        context=self.context,
                        exception=exc,
                    )
                )
                break

            inputs = {k: self.context[k] for k in self.workflow.node_inputs[current_node] if k in self.context}
            result = None
            exception = None

            # Handle sub-workflow nodes
            if isinstance(node_func, SubWorkflowNode):
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.SUB_WORKFLOW_ENTERED,
                        node_name=current_node,
                        context=self.context,
                        sub_workflow_name=current_node,
                    )
                )

            try:
                if isinstance(node_func, SubWorkflowNode):
                    result = await node_func(self, **inputs)
                    usage = None  # Sub-workflow usage is handled by its own nodes
                else:
                    result = await node_func(**inputs)
                    usage = getattr(node_func, "usage", None)  # Extract usage if set by LLM nodes
                output_key = self.workflow.node_outputs[current_node]
                if output_key:
                    self.context[output_key] = result
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.NODE_COMPLETED,
                        node_name=current_node,
                        context=self.context,
                        result=result,
                        usage=usage,  # Include usage data in the event
                    )
                )
            except Exception as e:
                logger.error(f"Error executing node {current_node}: {e}")
                exception = e
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.NODE_FAILED,
                        node_name=current_node,
                        context=self.context,
                        exception=e,
                    )
                )
                raise
            finally:
                if isinstance(node_func, SubWorkflowNode):
                    await self._notify_observers(
                        WorkflowEvent(
                            event_type=WorkflowEventType.SUB_WORKFLOW_EXITED,
                            node_name=current_node,
                            context=self.context,
                            sub_workflow_name=current_node,
                            result=result,
                            exception=exception,
                        )
                    )

            next_nodes = self.workflow.transitions.get(current_node, [])
            current_node = None
            for next_node, condition in next_nodes:
                await self._notify_observers(
                    WorkflowEvent(
                        event_type=WorkflowEventType.TRANSITION_EVALUATED,
                        node_name=None,
                        context=self.context,
                        transition_from=current_node,
                        transition_to=next_node,
                    )
                )
                if condition is None or condition(self.context):
                    current_node = next_node
                    break

        logger.info("Workflow execution completed")
        await self._notify_observers(
            WorkflowEvent(event_type=WorkflowEventType.WORKFLOW_COMPLETED, node_name=None, context=self.context)
        )
        return self.context


class Workflow:
    def __init__(self, start_node: str):
        """Initialize a workflow with a starting node."""
        self.start_node = start_node
        self.nodes: Dict[str, Callable] = {}
        self.node_inputs: Dict[str, List[str]] = {}
        self.node_outputs: Dict[str, Optional[str]] = {}
        self.transitions: Dict[str, List[Tuple[str, Optional[Callable]]]] = {}
        self.current_node = None
        self._observers: List[WorkflowObserver] = []  # Store observers for later propagation
        self._register_node(start_node)  # Register the start node without setting current_node
        self.current_node = start_node  # Set current_node explicitly after registration

    def _register_node(self, name: str):
        """Register a node without modifying the current node."""
        if name not in Nodes.NODE_REGISTRY:
            raise ValueError(f"Node {name} not registered")
        func, inputs, output = Nodes.NODE_REGISTRY[name]
        self.nodes[name] = func
        self.node_inputs[name] = inputs
        self.node_outputs[name] = output

    def node(self, name: str):
        """Add a node to the workflow chain and set it as the current node."""
        self._register_node(name)
        self.current_node = name
        return self

    def sequence(self, *nodes: str):
        """Add a sequence of nodes to execute in order."""
        if not nodes:
            return self
        for node in nodes:
            if node not in Nodes.NODE_REGISTRY:
                raise ValueError(f"Node {node} not registered")
            func, inputs, output = Nodes.NODE_REGISTRY[node]
            self.nodes[node] = func
            self.node_inputs[node] = inputs
            self.node_outputs[node] = output
        for i in range(len(nodes) - 1):
            self.transitions.setdefault(nodes[i], []).append((nodes[i + 1], None))
        self.current_node = nodes[-1]
        return self

    def then(self, next_node: str, condition: Optional[Callable] = None):
        """Add a transition to the next node with an optional condition."""
        if next_node not in self.nodes:
            self._register_node(next_node)  # Register without changing current_node
        if self.current_node:
            self.transitions.setdefault(self.current_node, []).append((next_node, condition))
            logger.debug(f"Added transition from {self.current_node} to {next_node} with condition {condition}")
        else:
            logger.warning("No current node set for transition")
        self.current_node = next_node
        return self

    def parallel(self, *nodes: str):
        """Add parallel nodes to execute concurrently."""
        if self.current_node:
            for node in nodes:
                self.transitions.setdefault(self.current_node, []).append((node, None))
        self.current_node = None  # Reset after parallel to force explicit next node
        return self

    def add_observer(self, observer: WorkflowObserver) -> "Workflow":
        """Add an event observer callback to the workflow."""
        if observer not in self._observers:
            self._observers.append(observer)
            logger.debug(f"Added observer to workflow: {observer}")
        return self  # Support chaining

    def add_sub_workflow(self, name: str, sub_workflow: "Workflow", inputs: Dict[str, str], output: str):
        """Add a sub-workflow as a node."""
        sub_node = SubWorkflowNode(sub_workflow, inputs, output)
        self.nodes[name] = sub_node
        self.node_inputs[name] = list(inputs.keys())
        self.node_outputs[name] = output
        self.current_node = name
        return self

    def build(self, parent_engine: Optional["WorkflowEngine"] = None) -> WorkflowEngine:
        """Build and return a WorkflowEngine instance with registered observers."""
        engine = WorkflowEngine(self, parent_engine=parent_engine)
        for observer in self._observers:
            engine.add_observer(observer)
        return engine


class Nodes:
    NODE_REGISTRY = {}  # Registry to hold node functions and metadata

    @classmethod
    def define(cls, output: Optional[str] = None):
        """Decorator for defining simple workflow nodes."""

        def decorator(func: Callable) -> Callable:
            async def wrapped_func(**kwargs):
                try:
                    result = await func(**kwargs)
                    logger.debug(f"Node {func.__name__} executed with result: {result}")
                    return result
                except Exception as e:
                    logger.error(f"Error in node {func.__name__}: {e}")
                    raise

            inputs = list(func.__annotations__.keys())
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func

        return decorator

    @classmethod
    def validate_node(cls, output: str):
        """Decorator for nodes that validate inputs."""

        def decorator(func: Callable) -> Callable:
            async def wrapped_func(**kwargs):
                try:
                    result = await func(**kwargs)
                    if not isinstance(result, str):
                        raise ValueError(f"Validation node {func.__name__} must return a string")
                    logger.info(f"Validation result from {func.__name__}: {result}")
                    return result
                except Exception as e:
                    logger.error(f"Validation error in {func.__name__}: {e}")
                    raise

            inputs = list(func.__annotations__.keys())
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func

        return decorator

    @classmethod
    def llm_node(
        cls,
        model: str,
        system_prompt: str,
        prompt_template: str,
        output: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        **kwargs,
    ):
        """Decorator for creating LLM nodes with plain text output."""

        def decorator(func: Callable) -> Callable:
            async def wrapped_func(**kwargs):
                prompt = cls._render_prompt(prompt_template, kwargs)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]
                try:
                    response = await acompletion(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        presence_penalty=presence_penalty,
                        frequency_penalty=frequency_penalty,
                        drop_params=True,
                        **kwargs,
                    )
                    content = response.choices[0].message.content.strip()
                    # Attach usage metadata to the function
                    wrapped_func.usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "cost": getattr(response, "cost", None),  # Include cost if available
                    }
                    logger.debug(f"LLM output from {func.__name__}: {content[:50]}...")
                    return content
                except Exception as e:
                    logger.error(f"Error in LLM node {func.__name__}: {e}")
                    raise

            inputs = list(func.__annotations__.keys())
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func

        return decorator

    @classmethod
    def structured_llm_node(
        cls,
        model: str,
        system_prompt: str,
        prompt_template: str,
        response_model: Type[BaseModel],
        output: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        **kwargs,
    ):
        """Decorator for creating LLM nodes with structured output using instructor."""
        try:
            client = instructor.from_litellm(acompletion)
        except ImportError:
            logger.error("Instructor not installed. Install with 'pip install instructor[litellm]'")
            raise ImportError("Instructor is required for structured_llm_node")

        def decorator(func: Callable) -> Callable:
            async def wrapped_func(**kwargs):
                prompt = cls._render_prompt(prompt_template, kwargs)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]
                try:
                    # Use instructor with completion to get both structured output and raw response
                    structured_response, raw_response = await client.chat.completions.create_with_completion(
                        model=model,
                        messages=messages,
                        response_model=response_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        presence_penalty=presence_penalty,
                        frequency_penalty=frequency_penalty,
                        drop_params=True,
                        **kwargs,
                    )
                    # Attach usage metadata to the function
                    wrapped_func.usage = {
                        "prompt_tokens": raw_response.usage.prompt_tokens,
                        "completion_tokens": raw_response.usage.completion_tokens,
                        "total_tokens": raw_response.usage.total_tokens,
                        "cost": getattr(raw_response, "cost", None),  # Include cost if available
                    }
                    logger.debug(f"Structured output from {func.__name__}: {structured_response}")
                    return structured_response
                except ValidationError as e:
                    logger.error(f"Validation error in {func.__name__}: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Error in structured LLM node {func.__name__}: {e}")
                    raise

            inputs = list(func.__annotations__.keys())
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            cls.NODE_REGISTRY[func.__name__] = (wrapped_func, inputs, output)
            return wrapped_func

        return decorator

    @staticmethod
    def _render_prompt(template: str, context: Dict[str, Any]) -> str:
        """Render a Jinja2 template with the given context."""
        try:
            return Template(template).render(**context)
        except Exception as e:
            logger.error(f"Error rendering prompt template: {e}")
            raise


# Example workflow with observer integration and updated structured node
async def example_workflow():
    # Define Pydantic model for structured output
    class OrderDetails(BaseModel):
        order_id: str
        items: List[str]
        in_stock: bool

    # Define an example observer for progress
    async def progress_monitor(event: WorkflowEvent):
        print(f"[{event.event_type.value}] {event.node_name or 'Workflow'}")
        if event.result is not None:
            print(f"Result: {event.result}")
        if event.exception is not None:
            print(f"Exception: {event.exception}")

    # Define an observer for token usage
    class TokenUsageObserver:
        def __init__(self):
            self.total_prompt_tokens = 0
            self.total_completion_tokens = 0
            self.total_cost = 0.0
            self.node_usages = {}

        def __call__(self, event: WorkflowEvent):
            if event.event_type == WorkflowEventType.NODE_COMPLETED and event.usage:
                usage = event.usage
                self.total_prompt_tokens += usage.get("prompt_tokens", 0)
                self.total_completion_tokens += usage.get("completion_tokens", 0)
                if usage.get("cost") is not None:
                    self.total_cost += usage["cost"]
                self.node_usages[event.node_name] = usage
            # Print summary at workflow completion
            if event.event_type == WorkflowEventType.WORKFLOW_COMPLETED:
                print(f"Total prompt tokens: {self.total_prompt_tokens}")
                print(f"Total completion tokens: {self.total_completion_tokens}")
                print(f"Total cost: {self.total_cost}")
                for node, usage in self.node_usages.items():
                    print(f"Node {node}: {usage}")

    # Define nodes
    @Nodes.validate_node(output="validation_result")
    async def validate_order(order: Dict[str, Any]) -> str:
        return "Order validated" if order.get("items") else "Invalid order"

    @Nodes.structured_llm_node(
        model="gemini/gemini-2.0-flash",
        system_prompt="You are an inventory checker. Respond with a JSON object containing 'order_id', 'items', and 'in_stock' (boolean).",
        prompt_template="Check if the following items are in stock: {{ items }}. Return the result in JSON format with 'order_id' set to '123'.",
        response_model=OrderDetails,
        output="inventory_status",
    )
    async def check_inventory(items: List[str]) -> OrderDetails:
        pass

    @Nodes.define(output="payment_status")
    async def process_payment(order: Dict[str, Any]) -> str:
        return "Payment processed"

    @Nodes.define(output="shipping_confirmation")
    async def arrange_shipping(order: Dict[str, Any]) -> str:
        return "Shipping arranged"

    @Nodes.define(output="order_status")
    async def update_order_status(shipping_confirmation: str) -> str:
        return "Order updated"

    @Nodes.define(output="email_status")
    async def send_confirmation_email(shipping_confirmation: str) -> str:
        return "Email sent"

    @Nodes.define(output="notification_status")
    async def notify_customer_out_of_stock(inventory_status: OrderDetails) -> str:
        return "Customer notified of out-of-stock"

    # Sub-workflow for payment and shipping
    payment_shipping_sub_wf = Workflow("process_payment").sequence("process_payment", "arrange_shipping")

    # Instantiate token usage observer
    token_observer = TokenUsageObserver()

    # Main workflow incorporating the sub-workflow
    workflow = (
        Workflow("validate_order")
        .add_observer(progress_monitor)  # Add progress observer
        .add_observer(token_observer)  # Add token usage observer
        .add_sub_workflow(
            "payment_shipping", payment_shipping_sub_wf, inputs={"order": "order"}, output="shipping_confirmation"
        )
        .sequence("validate_order", "check_inventory")
        .then(
            "payment_shipping",
            condition=lambda ctx: ctx.get("inventory_status").in_stock if ctx.get("inventory_status") else False,
        )
        .then(
            "notify_customer_out_of_stock",
            condition=lambda ctx: not ctx.get("inventory_status").in_stock if ctx.get("inventory_status") else True,
        )
        .parallel("update_order_status", "send_confirmation_email")
        .node("update_order_status")
        .node("send_confirmation_email")
        .node("notify_customer_out_of_stock")
    )

    # Execute workflow
    initial_context = {"order": {"items": ["item1", "item2"]}, "items": ["item1", "item2"]}
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")


if __name__ == "__main__":
    asyncio.run(example_workflow())
