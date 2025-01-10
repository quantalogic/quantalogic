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
        message (Message): The message to add to memory.
    """
```

#### reset
```python
def reset(self) -> None:
    """Reset the agent memory."""
```

#### compact
```python
def compact(self, n: int = 2) -> None:
    """Compact the memory to keep only essential messages.
    
    This method keeps:
    - The system message (if present)
    - First two pairs of user-assistant messages
    - Last n pairs of user-assistant messages (default: 2)
    
    Args:
        n (int): Number of last message pairs to keep. Defaults to 2.
    """
```

### Usage Example

```python
from quantalogic import AgentMemory
from quantalogic.types import Message

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
    """Add a value to the variable memory.
    
    Args:
        value (str): The value to add to memory.
        
    Returns:
        str: The key associated with the added value (e.g., 'var1').
    """
```

#### get
```python
def get(self, key: str, default: str | None = None) -> str | None:
    """Get a value from the variable memory.
    
    Args:
        key (str): The key to retrieve.
        default (str | None, optional): Default value if key not found.
        
    Returns:
        str | None: The value associated with the key, or default if not found.
    """
```

#### pop
```python
def pop(self, key: str, default: str | None = None) -> str | None:
    """Remove and return a value for a key.
    
    Args:
        key (str): The key to remove.
        default (str | None, optional): Default value if key not found.
        
    Returns:
        str | None: The value associated with the key, or default if not found.
    """
```

#### update
```python
def update(self, other: dict[str, str] | None = None, **kwargs) -> None:
    """Update the memory with key-value pairs.
    
    Args:
        other (dict[str, str] | None, optional): Dictionary to update from.
        **kwargs: Additional key-value pairs to update.
    """
```

#### reset
```python
def reset(self) -> None:
    """Reset the variable memory."""
```

### Usage Example

```python
# Create variable memory
variables = VariableMemory()

# Store values
key1 = variables.add("Hello World")  # Returns 'var1'
key2 = variables.add("Python")       # Returns 'var2'

# Access values
value1 = variables.get(key1)         # Returns 'Hello World'
value2 = variables.get(key2)         # Returns 'Python'
missing = variables.get('var3', '')   # Returns ''

# Update values
variables.update({'var1': 'Updated'}, var2='New Value')

# Remove values
old_value = variables.pop(key1)      # Returns 'Updated'

# Clear all variables
variables.reset()
```

## Next Steps

- Learn about [Agent API](agent.md)
- Explore [Tool Development](../best-practices/tool-development.md)
