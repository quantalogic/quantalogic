#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio",
#     "jinja2",
#     "instructor[litellm]"  # Added for structured_llm_node support
# ]
# ///

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import instructor
from jinja2 import Template
from litellm import acompletion
from loguru import logger
from pydantic import BaseModel, ValidationError


class WorkflowEngine:
    def __init__(self, workflow):
        self.workflow = workflow
        self.context = {}

    async def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow starting from the entry node."""
        self.context = initial_context.copy()
        current_node = self.workflow.start_node

        while current_node:
            logger.info(f"Executing node: {current_node}")
            node_func = self.workflow.nodes.get(current_node)
            if not node_func:
                logger.error(f"Node {current_node} not found")
                break

            try:
                inputs = {k: self.context[k] for k in self.workflow.node_inputs[current_node] if k in self.context}
                result = await node_func(**inputs)
                output_key = self.workflow.node_outputs[current_node]
                if output_key:
                    self.context[output_key] = result
            except Exception as e:
                logger.error(f"Error executing node {current_node}: {e}")
                raise

            next_nodes = self.workflow.transitions.get(current_node, [])
            current_node = None
            for next_node, condition in next_nodes:
                if condition is None or condition(self.context):
                    current_node = next_node
                    break

        logger.info("Workflow execution completed")
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

    def node(self, name: str):
        """Add a node to the workflow chain."""
        if name not in Nodes.NODE_REGISTRY:
            raise ValueError(f"Node {name} not registered")
        func, inputs, output = Nodes.NODE_REGISTRY[name]
        self.nodes[name] = func
        self.node_inputs[name] = inputs
        self.node_outputs[name] = output
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
        if self.current_node:
            self.transitions.setdefault(self.current_node, []).append((next_node, condition))
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

    def add_sub_workflow(self, name: str, sub_workflow: 'Workflow', inputs: Dict[str, str], output: str):
        """Add a sub-workflow as a node."""
        async def sub_workflow_node(**kwargs):
            sub_context = {sub_key: kwargs[main_key] for main_key, sub_key in inputs.items()}
            sub_engine = sub_workflow.build()
            result = await sub_engine.run(sub_context)
            return result.get(output)
        
        self.nodes[name] = sub_workflow_node
        self.node_inputs[name] = list(inputs.keys())
        self.node_outputs[name] = output
        self.current_node = name
        return self

    def build(self) -> WorkflowEngine:
        """Build and return a WorkflowEngine instance."""
        return WorkflowEngine(self)

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
        **kwargs
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
                        **kwargs
                    )
                    content = response.choices[0].message.content.strip()
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
        **kwargs
    ):
        """Decorator for creating LLM nodes with structured output using Instructor."""
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
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        response_model=response_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        presence_penalty=presence_penalty,
                        frequency_penalty=frequency_penalty,
                        drop_params=True,
                        **kwargs
                    )
                    logger.debug(f"Structured output from {func.__name__}: {response}")
                    return response
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

# Example workflow matching the provided structure
async def example_workflow():
    # Define Pydantic model for structured output
    class OrderDetails(BaseModel):
        order_id: str
        items: List[str]
        in_stock: bool

    # Define nodes
    @Nodes.validate_node(output="validation_result")
    async def validate_order(order: Dict[str, Any]) -> str:
        return "Order validated" if order.get("items") else "Invalid order"

    @Nodes.structured_llm_node(
        model="gemini/gemini-2.0-flash",
        system_prompt="Check inventory for items.",
        prompt_template="Check if {{ items }} are in stock.",
        response_model=OrderDetails,
        output="inventory_status"
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
    payment_shipping_sub_wf = (
        Workflow("process_payment")
        .sequence("process_payment", "arrange_shipping")
    )

    # Main workflow incorporating the sub-workflow
    workflow = (
        Workflow("validate_order")
        .sequence("validate_order", "check_inventory")
        .then("payment_shipping", condition=lambda ctx: ctx.get("inventory_status").in_stock if ctx.get("inventory_status") else False)
        .then("notify_customer_out_of_stock", condition=lambda ctx: not ctx.get("inventory_status").in_stock if ctx.get("inventory_status") else True)
        .add_sub_workflow("payment_shipping", payment_shipping_sub_wf, inputs={"order": "order"}, output="shipping_confirmation")
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