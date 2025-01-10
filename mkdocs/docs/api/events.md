# Event System API Reference

QuantaLogic provides a robust event system for monitoring and reacting to agent activities. The event system enables real-time tracking of agent operations, tool executions, and memory management.

## EventEmitter

```python
from quantalogic import EventEmitter
```

Core class for event handling and distribution.

### Constructor

```python
emitter = EventEmitter()
```

### Methods

#### on
```python
def on(self, event_types: list[str], handler: Callable[[dict], None]) -> None:
    """Register event handler.
    
    Args:
        event_types: List of event types to handle
        handler: Callback function
    """
```

#### emit
```python
def emit(self, event_type: str, data: dict) -> None:
    """Emit an event.
    
    Args:
        event_type: Type of event
        data: Event data
    """
```

#### remove_handler
```python
def remove_handler(self, handler: Callable[[dict], None]) -> None:
    """Remove an event handler.
    
    Args:
        handler: Handler to remove
    """
```

## Core Events

### Agent Events

1. **agent_start**
   - Emitted when agent begins task
   - Contains task description and config

2. **agent_end**
   - Emitted when agent completes task
   - Includes final response

3. **agent_error**
   - Indicates agent error
   - Contains error details

```python
def agent_handler(event):
    event_type = event["type"]
    if event_type == "agent_start":
        print(f"Starting task: {event['data']['task']}")
    elif event_type == "agent_end":
        print(f"Task completed: {event['data']['response']}")
    elif event_type == "agent_error":
        print(f"Error: {event['data']['error']}")

agent.event_emitter.on(
    ["agent_start", "agent_end", "agent_error"],
    agent_handler
)
```

### Tool Events

1. **tool_start**
   - Tool execution beginning
   - Tool name and parameters

2. **tool_end**
   - Tool execution complete
   - Result and metrics

3. **tool_error**
   - Tool execution failed
   - Error information

```python
def tool_handler(event):
    if event["type"] == "tool_start":
        tool_name = event["data"]["tool"]
        print(f"Running tool: {tool_name}")
    elif event["type"] == "tool_end":
        print(f"Tool result: {event['data']['result']}")
    elif event["type"] == "tool_error":
        print(f"Tool error: {event['data']['error']}")

agent.event_emitter.on(
    ["tool_start", "tool_end", "tool_error"],
    tool_handler
)
```

### Memory Events

1. **memory_full**
   - Memory capacity reached
   - Current memory size

2. **memory_compacted**
   - Memory optimization complete
   - Optimization details

3. **memory_summary**
   - Memory state overview
   - Usage statistics

```python
def memory_handler(event):
    if event["type"] == "memory_full":
        print("Memory full, optimizing...")
    elif event["type"] == "memory_compacted":
        print(f"Optimized: {event['data']['stats']}")
    elif event["type"] == "memory_summary":
        print(f"Memory state: {event['data']}")

agent.event_emitter.on(
    ["memory_full", "memory_compacted", "memory_summary"],
    memory_handler
)
```

## Event Handling Best Practices

### 1. Focused Handlers
```python
# Separate handlers by concern
def tool_monitor(event):
    """Monitor tool performance."""
    if event["type"] == "tool_end":
        duration = event["data"]["duration"]
        if duration > 5:
            logger.warning(f"Slow tool: {duration}s")

def error_monitor(event):
    """Handle errors."""
    if "error" in event["type"]:
        logger.error(f"Error: {event['data']}")

# Register focused handlers
agent.event_emitter.on(["tool_end"], tool_monitor)
agent.event_emitter.on(
    ["tool_error", "agent_error"],
    error_monitor
)
```

### 2. Event Filtering
```python
def filtered_handler(event):
    """Handle specific events."""
    # Filter by type
    if event["type"] not in ["tool_start", "tool_end"]:
        return
        
    # Filter by data
    if event["data"].get("tool") != "python_tool":
        return
        
    # Process event
    process_python_tool_event(event)

agent.event_emitter.on(
    ["tool_start", "tool_end"],
    filtered_handler
)
```

### 3. Async Handling
```python
async def async_handler(event):
    """Handle events asynchronously."""
    if event["type"] == "tool_end":
        await store_metrics(event["data"])
    elif event["type"] == "agent_end":
        await notify_completion(event["data"])

agent.event_emitter.on(
    ["tool_end", "agent_end"],
    async_handler
)
```

### 4. Event Logging
```python
def log_handler(event):
    """Log events with context."""
    context = {
        "timestamp": datetime.now(),
        "event_type": event["type"],
        "data": event["data"]
    }
    
    if "error" in event["type"]:
        logger.error("Error event", extra=context)
    else:
        logger.info("Normal event", extra=context)

agent.event_emitter.on(["*"], log_handler)
```

## Custom Events

### Creating Custom Events
```python
class CustomTool(Tool):
    def execute(self, **kwargs):
        # Emit custom event
        self.agent.event_emitter.emit(
            "custom_tool_event",
            {
                "tool": self.name,
                "custom_data": "value"
            }
        )
        return result
```

### Handling Custom Events
```python
def custom_handler(event):
    if event["type"] == "custom_tool_event":
        process_custom_event(event["data"])

agent.event_emitter.on(
    ["custom_tool_event"],
    custom_handler
)
```

## Event Visualization

### Console Output
```python
def console_visualizer(event):
    """Visualize events in console."""
    if event["type"] == "tool_start":
        print("⚙️ Starting tool...")
    elif event["type"] == "tool_end":
        print("✅ Tool complete")
    elif "error" in event["type"]:
        print("❌ Error occurred")

agent.event_emitter.on(["*"], console_visualizer)
```

### Web Interface
```python
def web_visualizer(event):
    """Send events to web interface."""
    event_data = {
        "type": event["type"],
        "timestamp": datetime.now().isoformat(),
        "data": event["data"]
    }
    websocket.send(json.dumps(event_data))

agent.event_emitter.on(["*"], web_visualizer)
```

## Next Steps

- Learn about [Memory Management](memory.md)
- Explore [Tool Development](../best-practices/tool-development.md)
- Check [Agent API](agent.md)
