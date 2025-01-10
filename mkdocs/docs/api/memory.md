# Memory API Reference

QuantaLogic provides sophisticated memory management through two main components: `AgentMemory` for conversation history and `VariableMemory` for variable storage.

## AgentMemory

```python
from quantalogic import AgentMemory
```

Manages the agent's conversation history and context.

### Constructor

```python
memory = AgentMemory()
```

### Methods

#### add
```python
def add(self, message: Message) -> None:
    """Add a message to memory.
    
    Args:
        message: Message to store
    """
```

#### reset
```python
def reset(self) -> None:
    """Clear all memory."""
```

#### compact
```python
def compact(self, n: int = 2) -> None:
    """Optimize memory by keeping essential messages.
    
    Keeps:
    - System message (if present)
    - First two user-assistant pairs
    - Last n pairs (default: 2)
    
    Args:
        n: Number of recent pairs to keep
    """
```

### Usage Example

```python
# Create memory instance
memory = AgentMemory()

# Add messages
memory.add(Message(role="system", content="You are an AI assistant"))
memory.add(Message(role="user", content="Hello!"))
memory.add(Message(role="assistant", content="Hi there!"))

# Optimize memory when it grows large
memory.compact(n=3)  # Keep last 3 pairs

# Clear memory
memory.reset()
```

## VariableMemory

```python
from quantalogic import VariableMemory
```

Manages variable storage for the agent.

### Constructor

```python
variables = VariableMemory()
```

### Methods

#### add
```python
def add(self, value: str) -> str:
    """Store a value and return its key.
    
    Args:
        value: Value to store
        
    Returns:
        str: Generated key (e.g., 'var1')
    """
```

#### pop
```python
def pop(self, key: str, default: str | None = None) -> str | None:
    """Remove and return a value.
    
    Args:
        key: Variable key
        default: Default if key not found
        
    Returns:
        str | None: Value or default
    """
```

#### reset
```python
def reset(self) -> None:
    """Clear all variables."""
```

### Usage Example

```python
# Create variable store
variables = VariableMemory()

# Store values
key1 = variables.add("Hello World")  # Returns 'var1'
key2 = variables.add("Python")       # Returns 'var2'

# Retrieve and remove
value = variables.pop('var1')  # Returns 'Hello World'
default_value = variables.pop('unknown', 'Not Found')

# Clear all variables
variables.reset()
```

## Memory Management Best Practices

### 1. Regular Optimization
```python
# Monitor memory size
if len(agent.memory.memory) > 100:
    # Keep important context
    agent.memory.compact(n=3)
```

### 2. Context Preservation
```python
# Save critical context before reset
important_context = agent.memory.memory[-2:]
agent.memory.reset()
for msg in important_context:
    agent.memory.add(msg)
```

### 3. Variable Lifecycle
```python
# Use variables for temporary storage
file_key = agent.variable_store.add(file_content)
try:
    # Process file
    process_file(file_content)
finally:
    # Clean up
    agent.variable_store.pop(file_key)
```

### 4. Memory Events
```python
# Monitor memory operations
agent.event_emitter.on(
    [
        "memory_full",
        "memory_compacted",
        "memory_summary"
    ],
    handle_memory_event
)
```

## Integration with Agent

### 1. Basic Setup
```python
from quantalogic import Agent, AgentMemory

agent = Agent(
    model_name="your-model",
    memory=AgentMemory()
)
```

### 2. Custom Memory Management
```python
class CustomMemory(AgentMemory):
    def compact(self, n: int = 2):
        """Custom memory optimization."""
        # Your optimization logic
        pass

agent = Agent(memory=CustomMemory())
```

### 3. Memory-Aware Tools
```python
class MemoryAwareTool(Tool):
    def execute(self, **kwargs):
        # Access agent memory
        memory = self.agent.memory
        # Use memory content
        return process_with_context(memory)
```

## Memory Events

### Event Types

1. **memory_full**
   - Triggered when memory reaches capacity
   - Suggests compaction needed

2. **memory_compacted**
   - Fired after successful compaction
   - Includes optimization details

3. **memory_summary**
   - Provides memory state overview
   - Useful for monitoring

### Handling Events
```python
def memory_handler(event):
    event_type = event["type"]
    if event_type == "memory_full":
        logger.warning("Memory full, compacting...")
        agent.memory.compact()
    elif event_type == "memory_compacted":
        logger.info("Memory optimized")
    elif event_type == "memory_summary":
        logger.info(f"Memory state: {event['data']}")

agent.event_emitter.on(
    ["memory_full", "memory_compacted", "memory_summary"],
    memory_handler
)
```

## Next Steps

- Learn about [Event System](events.md)
- Explore [Tool Development](../best-practices/tool-development.md)
- Check [Agent API](agent.md)
