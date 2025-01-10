# Event Monitoring

Learn how to monitor your agent's activities in real-time. Event monitoring helps you understand what your agent is thinking and doing at each step.

## Why Monitor Events?

- Debug agent behavior
- Track task progress
- Understand decision-making
- Optimize performance
- Handle errors gracefully

## Setting Up Event Monitoring

First, import the necessary components:

```python
from quantalogic import Agent, console_print_events
from quantalogic.tools import LLMTool
```

Create an agent with the LLM tool:

```python
agent = Agent(
    model_name="deepseek/deepseek-chat",
    tools=[LLMTool(model_name="deepseek/deepseek-chat")]
)
```

### Configure Event Listeners

Set up listeners for important events:

```python
agent.event_emitter.on(
    [
        "task_complete",        # Task finished
        "task_think_start",     # Agent starts thinking
        "task_think_end",       # Agent finishes thinking
        "tool_execution_start", # Tool starts running
        "tool_execution_end",   # Tool finishes running
        "error_max_iterations_reached",  # Too many iterations
        "memory_full",          # Memory limit reached
        "memory_compacted",     # Memory optimized
        "memory_summary",       # Memory state
    ],
    console_print_events,  # Print events to console
)
```

## Example Task

Let's run a complex task that demonstrates various events:

```python
result = agent.solve_task(
    "1. Write a poem in English about a dog. "
    "2. Translate the poem into French. "
    "3. Choose 2 French authors "
    "4. Rewrite the translated poem with the style of the chosen authors. "
)
```

### Sample Output

You'll see events like this:

```text
[Task Think Start] Analyzing poetry task requirements...
[Tool Execution Start] Using LLM to generate English poem...
[Tool Execution End] English poem generated
[Task Think Start] Planning translation approach...
[Tool Execution Start] Translating to French...
[Tool Execution End] French translation complete
[Memory Summary] Current context: 2 poems stored
[Task Complete] All poetry variations generated
```

## Available Events

| Event | Description |
|-------|-------------|
| `task_complete` | Task has finished successfully |
| `task_think_start` | Agent begins reasoning about next step |
| `task_think_end` | Agent has decided on action |
| `tool_execution_start` | Tool begins operation |
| `tool_execution_end` | Tool has completed operation |
| `error_max_iterations_reached` | Task exceeded iteration limit |
| `memory_full` | Memory capacity reached |
| `memory_compacted` | Memory has been optimized |
| `memory_summary` | Current memory state |

## Custom Event Handlers

Create your own handler:

```python
def my_event_handler(event):
    """Custom event handler."""
    event_type = event.get("type")
    event_data = event.get("data")
    
    if event_type == "task_complete":
        print(f"✅ Task completed: {event_data}")
    elif event_type == "error_max_iterations_reached":
        print(f"⚠️ Warning: {event_data}")

# Use your custom handler
agent.event_emitter.on(["task_complete"], my_event_handler)
```

## Complete Code

Here's the full example:

```python
import os
from quantalogic import Agent, console_print_events
from quantalogic.tools import LLMTool

# Verify API key
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Create agent
agent = Agent(
    model_name="deepseek/deepseek-chat",
    tools=[LLMTool(model_name="deepseek/deepseek-chat")]
)

# Set up event monitoring
agent.event_emitter.on(
    [
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
        "error_max_iterations_reached",
        "memory_full",
        "memory_compacted",
        "memory_summary",
    ],
    console_print_events,
)

# Run complex task
result = agent.solve_task(
    "1. Write a poem in English about a dog. "
    "2. Translate the poem into French. "
    "3. Choose 2 French authors "
    "4. Rewrite the translated poem with the style of the chosen authors. "
)
print(result)
```

## Best Practices

1. **Monitor Critical Events**: Always track task completion and errors
2. **Custom Handlers**: Create specific handlers for your use case
3. **Log Important Data**: Save event data for analysis
4. **Handle Errors**: React to error events appropriately
5. **Memory Management**: Watch memory-related events

## Next Steps

- Learn about [Memory Management](../components/memory.md)
- Explore [Tool Development](../best-practices/tool-development.md)
- Try [Task Automation](task-automation.md)
