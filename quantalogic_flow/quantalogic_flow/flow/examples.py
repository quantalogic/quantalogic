"""
Example workflow implementation.

This module contains example workflow definitions and usage patterns.
"""

import asyncio
from typing import Any, Dict, List

from loguru import logger
from pydantic import BaseModel

from .core import Workflow, WorkflowEvent, WorkflowEventType
from .nodes import Nodes
from .template import get_template_path


async def example_workflow():
    """Example workflow demonstrating various node types and workflow patterns."""
    
    class OrderDetails(BaseModel):
        order_id: str
        items_in_stock: List[str]
        items_out_of_stock: List[str]

    async def progress_monitor(event: WorkflowEvent):
        print(f"[{event.event_type.value}] {event.node_name or 'Workflow'}")
        if event.result is not None:
            print(f"Result: {event.result}")
        if event.exception is not None:
            print(f"Exception: {event.exception}")

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
            if event.event_type == WorkflowEventType.WORKFLOW_COMPLETED:
                print(f"Total prompt tokens: {self.total_prompt_tokens}")
                print(f"Total completion tokens: {self.total_completion_tokens}")
                print(f"Total cost: {self.total_cost}")
                for node, usage in self.node_usages.items():
                    print(f"Node {node}: {usage}")

    @Nodes.validate_node(output="validation_result")
    async def validate_order(order: Dict[str, Any]) -> str:
        return "Order validated" if order.get("items") else "Invalid order"

    @Nodes.structured_llm_node(
        system_prompt_file=get_template_path("system_check_inventory.j2"),
        output="inventory_status",
        response_model=OrderDetails,
        prompt_file=get_template_path("prompt_check_inventory.j2"),
    )
    async def check_inventory(items: List[str]) -> OrderDetails:
        return OrderDetails(order_id="123", items_in_stock=["item1"], items_out_of_stock=[])

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

    @Nodes.transform_node(output="transformed_items", transformer=lambda x: [item.upper() for item in x])
    async def transform_items(items: List[str]) -> List[str]:
        return items

    @Nodes.template_node(
        output="formatted_message",
        template="Order contains: {{ items | join(', ') }}",
    )
    async def format_order_message(rendered_content: str, items: List[str]) -> str:
        return rendered_content

    payment_shipping_sub_wf = Workflow("process_payment").sequence("process_payment", "arrange_shipping")

    token_observer = TokenUsageObserver()

    workflow = (
        Workflow("validate_order")
        .add_observer(progress_monitor)
        .add_observer(token_observer)
        .node("validate_order", inputs_mapping={"order": "customer_order"})
        .node("transform_items")
        .node("format_order_message", inputs_mapping={
            "items": "items",
            "template": "Custom order: {{ items | join(', ') }}"
        })
        .node("check_inventory", inputs_mapping={
            "model": lambda ctx: "gemini/gemini-2.0-flash",
            "items": "transformed_items",
            "temperature": 0.5,
            "max_tokens": 1000
        })
        .add_sub_workflow(
            "payment_shipping",
            payment_shipping_sub_wf,
            inputs={"order": lambda ctx: {"items": ctx["items"]}},
            output="shipping_confirmation"
        )
        .branch(
            [
                ("payment_shipping", lambda ctx: len(ctx.get("inventory_status").items_out_of_stock) == 0 if ctx.get("inventory_status") else False),
                ("notify_customer_out_of_stock", lambda ctx: len(ctx.get("inventory_status").items_out_of_stock) > 0 if ctx.get("inventory_status") else True)
            ],
            next_node="update_order_status"
        )
        .converge("update_order_status")
        .sequence("update_order_status", "send_confirmation_email")
    )

    initial_context = {"customer_order": {"items": ["item1", "item2"]}, "items": ["item1", "item2"]}
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")


if __name__ == "__main__":
    logger.info("Initializing Quantalogic Flow Package")
    asyncio.run(example_workflow())
