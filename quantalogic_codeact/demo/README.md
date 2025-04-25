# demo v0.1.0

A custom toolbox for Quantalogic.

## Installation

```bash
pip install -e .
```

## Features

This toolbox demonstrates several features of the Quantalogic toolbox system:

### Basic Tools

- `echo_tool`: A simple example that returns the input message

### Confirmation System

The confirmation system ensures that potentially destructive operations require user approval before execution. This toolbox includes examples of both static and dynamic confirmation messages:

#### Static Confirmation

```python
async def delete_item(item_name: str) -> bool:
    """A sensitive tool that demonstrates confirmation functionality."""
    # Implementation here
    return True

# Mark the tool as requiring confirmation
delete_item.requires_confirmation = True
delete_item.confirmation_message = "Are you sure you want to delete this item?"
```

#### Dynamic Confirmation

```python
def get_dynamic_confirmation_message():
    return "This is a dynamic confirmation message that could include runtime information."

async def modify_item(item_name: str, new_value: str) -> bool:
    """Another example tool demonstrating dynamic confirmation messages."""
    # Implementation here
    return True

# Use a callable for the confirmation message
modify_item.requires_confirmation = True
modify_item.confirmation_message = get_dynamic_confirmation_message
```

## Usage

To use this toolbox with Quantalogic CodeAct:

1. Install the toolbox
2. Enable it in your Quantalogic configuration:

```bash
quantalogic_codeact toolbox install demo
```

3. Run Quantalogic CodeAct with the `deepseek/deepseek-chat` model for best performance:

```bash
quantalogic_codeact --model deepseek/deepseek-chat
```