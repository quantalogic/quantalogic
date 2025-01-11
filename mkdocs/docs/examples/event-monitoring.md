# Agent Event Monitoring

Learn how to track and monitor your QuantaLogic agent's lifecycle and performance using the built-in event monitoring system.

## Overview

Event monitoring provides real-time insights into agent operations, enabling:
- Debugging and troubleshooting
- Performance tracking
- Detailed operational transparency

## Prerequisites

- Python 3.12 or later
- QuantaLogic library installed
- DeepSeek API key (or alternative LLM provider)

## Setting Up Event Monitoring

```python
import os
from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import LLMTool

# Set API key
os.environ["DEEPSEEK_API_KEY"] = "your-deepseek-key"
```

## Creating an Agent with Event Listeners

```python
# Initialize agent with event monitoring
agent = Agent(
    model_name="deepseek/deepseek-chat",
    tools=[LLMTool(
        model_name="deepseek/deepseek-chat", 
        name="deepseek_llm_tool", 
        on_token=console_print_token
    )]
)

# Configure event listeners
agent.event_emitter.on(
    event=[
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
        "error_max_iterations_reached",
        "memory_full",
        "memory_compacted",
        "memory_summary"
    ],
    listener=console_print_events
)
```

## Supported Event Types

| Event Type | Description |
|-----------|-------------|
| `task_complete` | Triggered when a task is successfully finished |
| `task_think_start` | Marks the beginning of task analysis |
| `task_think_end` | Indicates completion of task analysis |
| `tool_execution_start` | Signals the start of a tool's execution |
| `tool_execution_end` | Marks the end of a tool's execution |
| `error_max_iterations_reached` | Warns about reaching maximum iteration limit |
| `memory_full` | Indicates memory capacity has been reached |
| `memory_compacted` | Shows memory has been optimized |
| `memory_summary` | Provides an overview of memory usage |

## Best Practices

- Use event monitoring for debugging complex tasks
- Monitor performance and identify bottlenecks
- Customize event listeners for specific tracking needs
- Avoid adding too many event listeners to prevent performance overhead

!!! tip "Flexibility"
    Event monitoring can be customized to suit your specific observability requirements.

## Example Task Execution

```python
# Execute a task with event monitoring
result = agent.solve_task("Create a complex data processing script")
print(result)
```

## Customizing Event Listeners

You can create custom event listeners to:
- Log events to a file
- Send notifications
- Perform advanced analytics
- Integrate with monitoring systems

```python
def custom_event_listener(event_data):
    # Implement your custom event handling logic
    print(f"Custom Event: {event_data}")

agent.event_emitter.on(
    event=["task_complete"], 
    listener=custom_event_listener
)
```

!!! warning "Performance Consideration"
    Custom event listeners should be lightweight to avoid impacting agent performance.

## Complete Code

Here's the full example:

```python
import os
from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import LLMTool

# Set API key
os.environ["DEEPSEEK_API_KEY"] = "your-deepseek-key"

# Initialize agent with event monitoring
agent = Agent(
    model_name="deepseek/deepseek-chat",
    tools=[LLMTool(
        model_name="deepseek/deepseek-chat", 
        name="deepseek_llm_tool", 
        on_token=console_print_token
    )]
)

# Configure event listeners
agent.event_emitter.on(
    event=[
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
        "error_max_iterations_reached",
        "memory_full",
        "memory_compacted",
        "memory_summary"
    ],
    listener=console_print_events
)

# Execute a task with event monitoring
result = agent.solve_task("Create a complex data processing script")
print(result)
```

## Next Steps

- Explore [Tool Development](../best-practices/tool-development.md)
- Try [Task Automation](task-automation.md)
