# YAML Workflow DSL Specification

This document outlines the YAML-based Domain-Specific Language (DSL) for defining workflows in the Quantalogic Flow system. The DSL supports nodes, asynchronous Python functions, and transitions for sequential, conditional, and parallel execution, with functions either embedded in the YAML or referenced externally.

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

The Quantalogic Flow YAML DSL enables users to define workflows in a human-readable format, supporting:

*   Embedded or external async Python functions.
*   Sequential, conditional, and parallel node transitions.
*   Context management for workflow state.
*   Retry and timeout configurations.
*   Programmatic management via WorkflowManager.

This specification aligns with the system's implementation as of February 22, 2025.

## Workflow Structure

A YAML workflow file consists of three sections:

*   `functions`: Defines Python functions.
*   `nodes`: Configures nodes with execution details.
*   `workflow`: Specifies the start node and transitions.

```yaml
functions:
  # Function definitions
nodes:
  # Node configurations
workflow:
  # Start node and transitions
```

## Functions

The `functions` section maps function names to their implementations, either embedded or external.

### Fields

*   `code` (string, optional): Multi-line async Python code. Required for embedded functions.
*   `module` (string, optional): External module path (e.g., GitHub URL). Required for external functions.
*   `function` (string, optional): Function name in the module. Required with `module`.

### Rules

*   Functions must be async (`async def`).
*   Embedded function names must match their dictionary key.
*   Use either `code` or `module`+`function`, not both.

### Examples

#### Embedded

```yaml
functions:
  greet_user:
    code: |
      async def greet_user(name: str) -> str:
          await anyio.sleep(1)
          return f"Hello, {name}!"
```

#### External

```yaml
functions:
  fetch_data:
    module: "https://github.com/user/repo/blob/main/data.py"
    function: "fetch_data"
```

## Nodes

Nodes are tasks linked to functions, defined in YAML or via `Nodes.define` decorators in code.

### Fields

*   `function` (string, required): Name of the linked function.
*   `inputs` (list, required): Context keys required by the function.
*   `output` (string, required): Context key for the result.
*   `retries` (int, optional, default: 3): Retry attempts on failure.
*   `delay` (float, optional, default: 1.0): Seconds between retries.
*   `timeout` (float/null, optional, default: null): Max execution time.
*   `parallel` (bool, optional, default: false): Allow parallel execution.

### Example

```yaml
nodes:
  greet:
    function: greet_user
    inputs: [name]
    output: greeting
    retries: 2
    delay: 0.5
    timeout: 5.0
```

## Workflow

The `workflow` section defines the flow, with a start node and transitions.

### Fields

*   `start` (string, required): Starting node name.
*   `transitions` (list, required): Transition rules.

### Transition Fields

*   `from` (string, required): Source node.
*   `to` (string/list, required): Target node(s) — string for sequential, list for parallel.
*   `condition` (string, optional): Python expression using `ctx`.

### Examples

#### Sequential

```yaml
workflow:
  start: greet
  transitions:
    - from: greet
      to: log
```

#### Conditional

```yaml
workflow:
  start: check
  transitions:
    - from: check
      to: process
      condition: "ctx.get('status') == 'active'"
```

#### Parallel

```yaml
workflow:
  start: prepare
  transitions:
    - from: prepare
      to: [email, update]
```

## Context

The context (`ctx`) is a dictionary storing node outputs, accessible in conditions. Example: `ctx["greeting"] = "Hello, Alice!"`.

## Execution Flow

The WorkflowEngine executes the workflow:

1.  Starts at `workflow.start`.
2.  Executes nodes, storing outputs in `ctx`.
3.  Evaluates transitions:
    *   If conditional, checks `ctx` against the condition.
    *   Schedules to nodes (sequential or parallel).
4.  Continues until no transitions remain.

## WorkflowManager

The `WorkflowManager` class enables programmatic workflow management:

*   Add/update/remove nodes and transitions.
*   Load/save YAML files.
*   Instantiate Workflow objects.

### Example

```python
manager = WorkflowManager()
manager.add_function("greet", "embedded", code="async def greet(name): return f'Hi, {name}!'")
manager.add_node("start", "greet", output="greeting")
manager.set_start_node("start")
manager.save_to_yaml("workflow.yaml")
```

## Examples

### Example 1: Simple Sequential Workflow

```yaml
functions:
  greet_user:
    code: |
      async def greet_user(name: str) -> str:
          await anyio.sleep(1)
          return f"Hello, {name}!"
  log_message:
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
      to: log
```

### Example 2: E-commerce Workflow

```yaml
functions:
  validate_order:
    code: |
      async def validate_order(order: dict) -> bool:
          return bool(order.get("customer"))
  check_inventory:
    code: |
      async def check_inventory(order: dict) -> bool:
          return len(order["items"]) <= 2
  process_payment:
    code: |
      async def process_payment(order: dict) -> bool:
          return order["customer"] == "John Doe"
nodes:
  validate:
    function: validate_order
    inputs: [order]
    output: is_valid
  inventory:
    function: check_inventory
    inputs: [order]
    output: in_stock
  payment:
    function: process_payment
    inputs: [order]
    output: payment_success
workflow:
  start: validate
  transitions:
    - from: validate
      to: inventory
    - from: inventory
      to: payment
      condition: "ctx.get('in_stock')"
```

Execution with `ctx = {"order": {"items": ["item1"], "customer": "John Doe"}}`:

1.  validate → `ctx["is_valid"] = True`.
2.  inventory → `ctx["in_stock"] = True`.
3.  payment → `ctx["payment_success"] = True`.

## Conclusion

The Quantalogic Flow YAML DSL provides a robust, flexible way to define workflows, integrating seamlessly with the Workflow, WorkflowEngine, and WorkflowManager classes. It supports diverse use cases, from simple sequences to complex conditional flows, as of February 22, 2025.

This Markdown version is streamlined, reflects the provided code, and maintains clarity for users and developers.