# YAML Workflow DSL Specification

This document details the YAML-based Domain-Specific Language (DSL) for defining workflows within the Quantalogic Flow system. The DSL facilitates the creation of workflows composed of nodes executing asynchronous Python functions, transitions enabling sequential, conditional, and parallel execution, and nested workflows for defining hierarchical flow structures. Functions can be directly embedded within the YAML or referenced from external sources.

## Table of Contents

1.  [Introduction](#introduction)
2.  [Workflow Structure](#workflow-structure)
3.  [Functions](#functions)
4.  [Nodes](#nodes)
5.  [Workflow](#workflow)
6.  [Context](#context)
7.  [Execution Flow](#execution-flow)
8.  [WorkflowManager](#workflowmanager)
9.  [Examples](#examples)
10. [Conclusion](#conclusion)

## Introduction

The Quantalogic Flow YAML DSL empowers users to define workflows in a human-readable format, offering support for:

*   Embedded or external asynchronous Python functions.
*   Sequential, conditional, and parallel node transitions.
*   Nested workflows as sub-workflows within nodes.
*   Context management for workflow state.
*   Retry and timeout configurations.
*   Programmatic management via `WorkflowManager`.

This specification reflects the system's implementation as of February 22, 2025, and includes enhancements for nested workflows.

## Workflow Structure

A YAML workflow file is structured into three primary sections:

*   `functions`: Defines Python functions that nodes will utilize.
*   `nodes`: Configures nodes, specifying their execution details, including any sub-workflows they may contain.
*   `workflow`: Defines the overall flow, including the start node and transitions between nodes.

```yaml
functions:
  # Function definitions
nodes:
  # Node configurations
workflow:
  # Start node and transitions
```

## Functions

The `functions` section maps function names to their corresponding implementations, which can be either embedded directly in the YAML or referenced externally.

### Fields

*   `type` (string, required): Specifies the function type: `"embedded"` for inline code or `"external"` for module references.
*   `code` (string, optional): Multi-line asynchronous Python code (required when `type: embedded`).
*   `module` (string, optional): The module path (e.g., a GitHub URL or a Python module) (required when `type: external`).
*   `function` (string, optional): The function name within the specified module (required when `module` is specified).

### Rules

*   Functions must be asynchronous (defined using `async def`).
*   For embedded functions, the function name must match the dictionary key.
*   Use either `code` or `module` + `function`; do not use both.

### Examples

#### Embedded

```yaml
functions:
  validate_order:
    type: embedded
    code: |
      async def validate_order(order: dict) -> bool:
          await anyio.sleep(1)
          return bool(order.get("customer"))
```

#### External

```yaml
functions:
  fetch_data:
    type: external
    module: "https://github.com/user/repo/blob/main/data.py"
    function: "fetch_data"
```

## Nodes

Nodes represent individual tasks that are linked to either functions or sub-workflows. They can be defined in the YAML file or programmatically using `Nodes.define` decorators in code.

### Fields

*   `function` (string, optional): The name of the linked function (mutually exclusive with `sub_workflow`).
*   `sub_workflow` (object, optional): The definition of a nested workflow (mutually exclusive with `function`).
    *   `start` (string, required): The starting node of the sub-workflow.
    *   `transitions` (list): Transition rules within the sub-workflow (see [Workflow](#workflow)).
*   `inputs` (list, required): A list of context keys that the function or sub-workflow's start node requires as input.
*   `output` (string, optional): The context key to store the result of the function or sub-workflow (required for functions, optional for sub-workflows).
*   `retries` (int, optional, default: 3): The number of retry attempts in case of failure.
*   `delay` (float, optional, default: 1.0): The delay in seconds between retry attempts.
*   `timeout` (float/null, optional, default: null): The maximum execution time in seconds. A value of null indicates no timeout.
*   `parallel` (bool, optional, default: false): Whether to allow parallel execution of the node.

### Rules

*   A node must specify either `function` or `sub_workflow`, but not both.
*   For sub-workflows, the `inputs` must match the requirements of the sub-workflow's start node. The `output` is optional if the sub-workflow sets multiple context keys.

### Examples

#### Function Node

```yaml
nodes:
  validate:
    function: validate_order
    inputs: [order]
    output: is_valid
    retries: 2
    delay: 0.5
    timeout: 5.0
```

#### Sub-Workflow Node

```yaml
nodes:
  payment_shipping:
    sub_workflow:
      start: process_payment
      transitions:
        - from: process_payment
          to: ship_order
          condition: "ctx.get('payment_success')"
    inputs: [order]
    output: shipping_confirmation
```

## Workflow

The `workflow` section defines the top-level flow of execution, including the starting node and the transitions between nodes.

### Fields

*   `start` (string, required): The name of the starting node.
*   `transitions` (list, required): A list of transition rules.

### Transition Fields

*   `from` (string, required): The source node for the transition.
*   `to` (string/list, required): The target node(s) for the transition. Use a string for sequential execution and a list for parallel execution.
*   `condition` (string, optional): A Python expression using `ctx` to access the context (e.g., `"ctx.get('in_stock')" `). The transition will only occur if the condition evaluates to `True`.

### Examples

#### Sequential

```yaml
workflow:
  start: validate
  transitions:
    - from: validate
      to: inventory
```

#### Conditional

```yaml
workflow:
  start: inventory
  transitions:
    - from: inventory
      to: payment
      condition: "ctx.get('in_stock')"
```

#### Parallel

```yaml
workflow:
  start: ship
  transitions:
    - from: ship
      to: [update_status, send_email]
```

## Context

The context (`ctx`) is a dictionary that stores node outputs and is shared across the main workflow and any sub-workflows. For example, if a sub-workflow sets `ctx["shipping_confirmation"] = "Shipped"`, this value is accessible in the main workflow's conditions or subsequent nodes.

## Execution Flow

The `WorkflowEngine` executes the workflow as follows:

1.  Starts at the node specified by `workflow.start`.
2.  Executes nodes, storing their outputs in the `ctx` dictionary:
    *   Function nodes directly set their `output` key in the context.
    *   Sub-workflow nodes execute their internal flow, updating the context with their results.
3.  Evaluates transitions:
    *   If a transition has a `condition`, the condition is checked against the current context.
    *   Schedules the target node(s) for execution, either sequentially or in parallel, based on the `to` field.
4.  Continues until no transitions remain to be executed.

## WorkflowManager

The `WorkflowManager` class provides programmatic control over workflows:

*   Add, update, and remove nodes and transitions.
*   Load and save workflows to and from YAML files.
*   Instantiate `Workflow` objects, including nested workflows.

### Example

```python
manager = WorkflowManager()
manager.add_function("validate", "embedded", code="async def validate(order): return bool(order)")
manager.add_node("start", function="validate", output="is_valid", inputs=["order"])
manager.set_start_node("start")
manager.save_to_yaml("workflow.yaml")
```

## Examples

### Example 1: Simple Sequential Workflow

```yaml
functions:
  greet_user:
    type: embedded
    code: |
      async def greet_user(name: str) -> str:
          await anyio.sleep(1)
          return f"Hello, {name}!"
  log_message:
    type: embedded
    code: |
      async def log_message(message: str) -> bool:
          print(f"Logged: {message}")
          return True
nodes:
  greet:
    function: greet_user
    inputs: [name]
    output: greeting
  log:
    function: log_message
    inputs: [message]
    output: logged
workflow:
  start: greet
  transitions:
    - from: greet
      to: log```

**Execution with `ctx = {"name": "Alice"}`:**

1.  `greet` → `ctx["greeting"] = "Hello, Alice!"`.
2.  `log` → `ctx["logged"] = True`.

### Example 2: E-commerce Workflow with Nested Flow

```yaml
functions:
  validate_order:
    type: embedded
    code: |
      async def validate_order(order: dict) -> bool:
          await anyio.sleep(1)
          return bool(order.get("customer"))
  check_inventory:
    type: embedded
    code: |
      async def check_inventory(order: dict) -> bool:
          await anyio.sleep(1)
          return len(order["items"]) <= 2
  process_payment:
    type: embedded
    code: |
      async def process_payment(order: dict) -> bool:
          await anyio.sleep(1)
          return order["customer"] == "John Doe"
  ship_order:
    type: embedded
    code: |
      async def ship_order(order: dict) -> str:
          await anyio.sleep(1)
          return "Shipped"
  update_order_status:
    type: embedded
    code: |
      async def update_order_status(order: dict) -> bool:
          await anyio.sleep(1)
          return True
  send_confirmation_email:
    type: embedded
    code: |
      async def send_confirmation_email(order: dict) -> bool:
          await anyio.sleep(1)
          return True
nodes:
  validate:
    function: validate_order
    inputs: [order]
    output: is_valid
  inventory:
    function: check_inventory
    inputs: [order]
    output: in_stock
  payment_shipping:
    sub_workflow:
      start: payment
      transitions:
        - from: payment
          to: shipping
          condition: "ctx.get('payment_success')"
    inputs: [order]
    output: shipping_confirmation
  payment:
    function: process_payment
    inputs: [order]
    output: payment_success
  shipping:
    function: ship_order
    inputs: [order]
    output: shipping_confirmation
  update_status:
    function: update_order_status
    inputs: [order]
    output: order_status_updated
  send_email:
    function: send_confirmation_email
    inputs: [order]
    output: confirmation_email_sent
workflow:
  start: validate
  transitions:
    - from: validate
      to: inventory
    - from: inventory
      to: payment_shipping
      condition: "ctx.get('in_stock')"
    - from: payment_shipping
      to: [update_status, send_email]
```

**Execution with `ctx = {"order": {"items": ["item1"], "customer": "John Doe"}}`:**

1.  `validate` → `ctx["is_valid"] = True`.
2.  `inventory` → `ctx["in_stock"] = True`.
3.  `payment_shipping` (sub-workflow):
    *   `payment` → `ctx["payment_success"] = True`.
    *   `shipping` → `ctx["shipping_confirmation"] = "Shipped"`.
4.  Parallel: `update_status` → `ctx["order_status_updated"] = True`, `send_email` → `ctx["confirmation_email_sent"] = True`.

## Conclusion

The Quantalogic Flow YAML DSL offers a powerful and flexible approach to defining workflows. As of February 22, 2025, it is enhanced with support for nested workflows. The DSL integrates seamlessly with the `Workflow`, `WorkflowEngine`, and `WorkflowManager` classes, supporting a wide range of use cases, from simple sequential processes to complex hierarchical flows, with minimal boilerplate code.