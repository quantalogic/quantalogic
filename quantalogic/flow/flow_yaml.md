# YAML Workflow DSL Specification

This document provides a full specification for a YAML-based Domain-Specific Language (DSL) designed to define workflows. The DSL enables users to describe workflows consisting of nodes, Python functions, and transitions, supporting sequential, conditional, and parallel executions. Python functions can either be embedded directly within the YAML file or referenced from external sources, such as GitHub repositories. This specification outlines the structure, fields, syntax, and behavior of the DSL, accompanied by multiple examples to illustrate its usage.

## Overview

The YAML Workflow DSL aims to provide a structured, human-readable format for defining workflows that can be saved, loaded, and executed by a workflow engine. A workflow consists of:

*   **Nodes**: Individual tasks or steps in the workflow, each associated with a Python function.
*   **Functions**: The executable logic for nodes, which can be embedded or externally referenced.
*   **Transitions**: Rules defining the flow between nodes, supporting sequential, conditional, and parallel execution.
*   **Context**: A shared dictionary (`ctx`) that stores the workflow's state and node outputs.

The DSL is organized into three top-level sections: `functions`, `nodes`, and `workflow`.

## Top-Level Structure

A valid YAML workflow file must contain the following top-level keys:

*   `functions`: Defines the Python functions available to nodes.
*   `nodes`: Configures the nodes, linking them to functions and specifying execution parameters.
*   `workflow`: Defines the workflow’s starting point and transitions between nodes.

Here’s the basic structure:

```yaml
functions:
  # Function definitions or references
nodes:
  # Node configurations
workflow:
  # Workflow structure with start node and transitions
```

## `functions` Section

The `functions` section is a dictionary where each key is a unique function name, and the value describes the function’s implementation. Functions can be defined in two ways:

*   **Embedded Code**: The Python code is included directly in the YAML as a multi-line string.
*   **External Reference**: The function is referenced from an external module (e.g., a GitHub URL or local file).

### Fields for `functions`

*   `code` (string, optional): A multi-line string containing the Python code for an `async` function. Required if the function is embedded.
*   `module` (string, optional): The path or URL to an external Python module. Required if the function is external.
*   `function` (string, optional): The name of the function within the external module. Required if `module` is used.

### Rules

*   Each function must be asynchronous (defined with `async def`).
*   For embedded functions, the function name in the code must match the key in the `functions` section.
*   Either `code` or both `module` and `function` must be provided, but not both.

### Examples

#### Embedded Function

```yaml
functions:
  greet_user:
    code: |
      async def greet_user(name: str) -> str:
          await anyio.sleep(1)
          return f"Hello, {name}!"
```

#### External Function

```yaml
functions:
  fetch_data:
    module: "https://github.com/user/repo/blob/main/data.py"
    function: "fetch_data"
```

## `nodes` Section

The `nodes` section is a dictionary where each key is a unique node name, and the value is a dictionary configuring the node’s behavior.

### Fields for `nodes`

*   `function` (string, required): The name of the function to execute, as defined in the `functions` section.
*   `inputs` (list of strings, required): Keys in the context (`ctx`) that the function requires as input.
*   `output` (string, required): The key in the context where the function’s result will be stored.
*   `retries` (integer, optional, default: 3): Number of retry attempts if the function fails.
*   `delay` (float, optional, default: 1.0): Delay in seconds between retries.
*   `timeout` (float or null, optional, default: null): Maximum execution time in seconds. If null, no timeout is applied.
*   `parallel` (boolean, optional, default: false): Whether the node can be executed in parallel with others.

### Example

```yaml
nodes:
  greet:
    function: greet_user
    inputs: [user_name]
    output: greeting
    retries: 2
    delay: 0.5
    timeout: 5.0
    parallel: false
```

## `workflow` Section

The `workflow` section defines the workflow’s structure, including its starting point and the transitions between nodes.

### Fields for `workflow`

*   `start` (string, required): The name of the starting node.
*   `transitions` (list, required): A list of transition rules defining the flow between nodes.

### Transition Fields

Each transition is a dictionary with:

*   `from` (string, required): The source node name.
*   `to` (string or list of strings, required): The next node(s) to execute. A string indicates sequential execution; a list indicates parallel execution.
*   `condition` (string, optional): A Python expression that evaluates to a boolean based on the context (`ctx`). If omitted, the transition is unconditional.

### Rules

*   The `start` node must exist in the `nodes` section.
*   All `from` and `to` values must reference valid node names.
*   Conditions use `ctx` to access the context dictionary and must be valid Python expressions.

### Examples

#### Sequential Workflow

```yaml
workflow:
  start: greet
  transitions:
    - from: greet
      to: log_message
```

#### Conditional Workflow

```yaml
workflow:
  start: check_status
  transitions:
    - from: check_status
      to: process
      condition: "ctx.get('status') == 'active'"
    - from: check_status
      to: halt
      condition: "ctx.get('status') != 'active'"
```

#### Parallel Workflow

```yaml
workflow:
  start: prepare
  transitions:
    - from: prepare
      to: [send_email, update_db]
```

## Context (`ctx`)

The workflow maintains a context dictionary (`ctx`) that stores the state and outputs of executed nodes. Each node’s output is saved under the key specified in its `output` field. Conditions in transitions can access this context using `ctx`.

For example:

If a node `greet` stores `"Hello, Alice!"` in `ctx["greeting"]`, a condition like `"ctx.get('greeting').startswith('Hello')"` would evaluate to `True`.

## Execution Flow

1.  The workflow begins at the node specified in `workflow.start`.
2.  After a node executes, its output is stored in the context under its `output` key.
3.  The engine evaluates all transitions where the `from` field matches the completed node:
    *   If a `condition` is present, it is evaluated using the current context.
    *   If the condition is `True` (or no condition exists), the `to` node(s) are scheduled.
    *   If `to` is a list, the listed nodes execute in parallel; otherwise, execution is sequential.
4.  The workflow continues until no further transitions are triggered.

## Additional Notes

*   **Async Functions**: All functions must be asynchronous to support I/O operations or delays.
*   **Error Handling**: If a node fails after all retries, the workflow engine should define the failure behavior (e.g., terminate or transition to an error node).
*   **Security**: Embedded Python code should come from trusted sources. For untrusted YAML, prefer external references and validate conditions.

## Examples

Below are detailed examples showcasing different use cases of the DSL.

### Example 1: Simple Sequential Workflow

A basic workflow that greets a user and logs the result.

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
          await anyio.sleep(1)
          print(f"Logged: {message}")
          return True

nodes:
  greet:
    function: greet_user
    inputs: [user_name]
    output: greeting
  log:
    function: log_message
    inputs: [greeting]
    output: logged

workflow:
  start: greet
  transitions:
    - from: greet
      to: log
```

**Execution:**

1.  `greet` runs with `user_name` from the initial context, storing the result in `ctx["greeting"]`.
2.  `log` runs with `ctx["greeting"]`, printing the message and storing `True` in `ctx["logged"]`.

### Example 2: Conditional Order Processing

An e-commerce workflow with conditional transitions based on inventory and payment status.

```yaml
functions:
  check_inventory:
    code: |
      async def check_inventory(order: dict) -> bool:
          await anyio.sleep(1)
          return order["quantity"] <= 5
  process_payment:
    code: |
      async def process_payment(order: dict) -> bool:
          await anyio.sleep(1)
          return order["card_valid"]
  ship_order:
    code: |
      async def ship_order(order: dict) -> str:
          await anyio.sleep(1)
          return "Shipped"

nodes:
  inventory:
    function: check_inventory
    inputs: [order]
    output: in_stock
  payment:
    function: process_payment
    inputs: [order]
    output: paid
  ship:
    function: ship_order
    inputs: [order]
    output: shipping_status

workflow:
  start: inventory
  transitions:
    - from: inventory
      to: payment
      condition: "ctx.get('in_stock')"
    - from: payment
      to: ship
      condition: "ctx.get('paid')"
```

**Execution with `ctx = {"order": {"quantity": 3, "card_valid": True}}`:**

1.  `inventory` checks stock, sets `ctx["in_stock"] = True`.
2.  `payment` processes payment, sets `ctx["paid"] = True`.
3.  `ship` ships the order, sets `ctx["shipping_status"] = "Shipped"`.

### Example 3: Parallel Task Execution

A workflow that processes a file and performs two tasks in parallel.

```yaml
functions:
  read_file:
    code: |
      async def read_file(path: str) -> str:
          await anyio.sleep(1)
          return "File contents"
  compress_data:
    code: |
      async def compress_data(data: str) -> str:
          await anyio.sleep(1)
          return f"Compressed: {data}"
  encrypt_data:
    code: |
      async def encrypt_data(data: str) -> str:
          await anyio.sleep(1)
          return f"Encrypted: {data}"

nodes:
  read:
    function: read_file
    inputs: [file_path]
    output: data
  compress:
    function: compress_data
    inputs: [data]
    output: compressed_data
  encrypt:
    function: encrypt_data
    inputs: [data]
    output: encrypted_data

workflow:
  start: read
  transitions:
    - from: read
      to: [compress, encrypt]
```

**Execution with `ctx = {"file_path": "/example.txt"}`:**

1.  `read` sets `ctx["data"] = "File contents".
2.  `compress` and `encrypt` run in parallel, setting `ctx["compressed_data"]` and `ctx["encrypted_data"]`.

### Example 4: External Function Reference

A workflow using an external function from GitHub.

```yaml
functions:
  fetch_weather:
    module: "https://github.com/user/repo/blob/main/weather.py"
    function: "get_weather"

nodes:
  weather:
    function: fetch_weather
    inputs: [city]
    output: temperature

workflow:
  start: weather
  transitions: []
```

**Execution with `ctx = {"city": "London"}`:**

1.  `weather` calls the external `get_weather` function, storing the result in `ctx["temperature"]`.

## Conclusion

This YAML Workflow DSL provides a flexible, extensible way to define workflows with support for embedded and external functions, sequential and parallel execution, and conditional transitions. The examples demonstrate its applicability to various scenarios, from simple tasks to complex conditional workflows. The specification ensures clarity and consistency, making it suitable for both human authors and automated workflow engines.