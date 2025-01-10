# Agent API Reference

The Agent class is the core component of QuantaLogic, implementing the ReAct (Reasoning & Action) framework. This reference explains its key components and usage.

## Agent Class

```python
from quantalogic import Agent
```

### Constructor

```python
def __init__(
    self,
    model_name: str = "",
    memory: AgentMemory = AgentMemory(),
    tools: list[Tool] = [TaskCompleteTool()],
    ask_for_user_validation: Callable[[str], bool] = console_ask_for_user_validation,
    task_to_solve: str = "",
    specific_expertise: str = "General AI assistant with coding and problem-solving capabilities",
    get_environment: Callable[[], str] = get_environment,
)
```

#### Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `model_name` | str | Name of the LLM to use | `""` |
| `memory` | AgentMemory | Memory management instance | `AgentMemory()` |
| `tools` | list[Tool] | List of tools available to the agent | `[TaskCompleteTool()]` |
| `ask_for_user_validation` | Callable | Function for user validation | `console_ask_for_user_validation` |
| `task_to_solve` | str | Initial task for the agent | `""` |
| `specific_expertise` | str | Agent's specialized knowledge area | `"General AI assistant..."` |
| `get_environment` | Callable | Function to get environment details | `get_environment` |

### Properties

```python
class Agent:
    specific_expertise: str
    model: GenerativeModel
    memory: AgentMemory
    variable_store: VariableMemory
    tools: ToolManager
    event_emitter: EventEmitter
    config: AgentConfig
    task_to_solve: str
    task_to_solve_summary: str
    total_tokens: int
    current_iteration: int
    max_input_tokens: int
    max_output_tokens: int
    max_iterations: int
    system_prompt: str
```

### Methods

#### solve_task

```python
def solve_task(self, task: str, max_iterations: int = 30) -> str:
    """Solve the given task using the ReAct framework.

    Args:
        task: The task description
        max_iterations: Maximum iterations (default: 30)

    Returns:
        str: Final response after task completion
    """
```

Example usage:
```python
agent = Agent(model_name="deepseek/deepseek-chat")
result = agent.solve_task("Create a Python function that calculates prime numbers")
```

## Configuration

### AgentConfig

```python
class AgentConfig:
    environment_details: str  # System environment information
    tools_markdown: str      # Available tools documentation
    system_prompt: str       # System prompt for the agent
```

### Memory Management

```python
class AgentMemory:
    """Manages agent's conversation history and context."""
    def compact_memory(self) -> None:
        """Optimize memory usage."""
    
    def clear(self) -> None:
        """Clear all memory."""
```

### Event System

```python
# Subscribe to events
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
    ],
    your_event_handler
)
```

## Creating Specialized Agents

### Coding Agent

```python
from quantalogic import create_coding_agent

agent = create_coding_agent(
    model_name="deepseek/deepseek-chat",
    vision_model_name=None,  # Optional
    basic=False  # Use full tool set
)
```

### Custom Agent

```python
from quantalogic import Agent
from quantalogic.tools import CustomTool

agent = Agent(
    model_name="your-model",
    tools=[
        CustomTool(),
        AnotherTool(),
    ],
    specific_expertise="Your specialized domain"
)
```

## Best Practices

### 1. Memory Management
```python
# Monitor memory usage
agent.event_emitter.on("memory_full", handle_memory_full)

# Compact memory when needed
if memory_intensive_task:
    agent.memory.compact_memory()
```

### 2. Error Handling
```python
try:
    result = agent.solve_task("Complex task")
except Exception as e:
    logger.error(f"Task failed: {e}")
    # Handle error appropriately
```

### 3. Tool Management
```python
# Add tools dynamically
agent.tools.add_tool(new_tool)

# Remove tools if needed
agent.tools.remove_tool("tool_name")
```

### 4. Event Monitoring
```python
def monitor_performance(event):
    if event["type"] == "tool_execution_end":
        duration = event["data"].get("duration")
        logger.info(f"Tool execution took {duration}s")

agent.event_emitter.on("*", monitor_performance)
```

## Examples

### 1. Basic Task
```python
agent = Agent(model_name="deepseek/deepseek-chat")
result = agent.solve_task("Write a hello world program")
```

### 2. Complex Task with Tools
```python
agent = Agent(
    model_name="deepseek/deepseek-chat",
    tools=[
        CodeGenerationTool(),
        FileManagementTool(),
        TestingTool()
    ]
)

result = agent.solve_task("""
1. Create a REST API
2. Add authentication
3. Write tests
""")
```

### 3. Event-Driven Task
```python
def track_progress(event):
    if event["type"] == "task_think_start":
        print("Thinking about:", event["data"])
    elif event["type"] == "task_complete":
        print("Task completed:", event["data"])

agent = Agent(model_name="deepseek/deepseek-chat")
agent.event_emitter.on(["task_think_start", "task_complete"], track_progress)
result = agent.solve_task("Your task here")
```

## Error Handling

Common exceptions and how to handle them:

```python
from quantalogic.exceptions import (
    ToolExecutionError,
    MemoryFullError,
    MaxIterationsError
)

try:
    result = agent.solve_task("Task")
except ToolExecutionError as e:
    # Handle tool failure
    logger.error(f"Tool failed: {e}")
except MemoryFullError:
    # Handle memory issues
    agent.memory.compact_memory()
except MaxIterationsError:
    # Handle iteration limit
    logger.warning("Task too complex")
```

## Next Steps

- Learn about [Tool Development](../best-practices/tool-development.md)
- Explore Memory Management
- Check Event System
