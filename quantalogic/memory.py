"""Memory for the agent."""

from pydantic import BaseModel


class Message(BaseModel):
    """Represents a message in the agent's memory."""

    role: str
    content: str


class AgentMemory:
    """Memory for the agent."""

    def __init__(self):
        """Initialize the agent memory."""
        self.memory: list[Message] = []

    def add(self, message: Message):
        """Add a message to the agent memory.

        Args:
            message (Message): The message to add to memory.
        """
        self.memory.append(message)

    def reset(self):
        """Reset the agent memory."""
        self.memory.clear()

    def compact(self, n: int = 2):
        """Compact the memory to keep only essential messages.

        This method keeps:
        - The system message (if present)
        - First two pairs of user-assistant messages
        - Last n pairs of user-assistant messages (default: 2)

        Args:
            n (int): Number of last message pairs to keep. Defaults to 2.
        """
        if not self.memory:
            return

        # Keep system message if present
        compacted_memory = []
        if self.memory and self.memory[0].role == "system":
            compacted_memory.append(self.memory[0])
            messages = self.memory[1:]
        else:
            messages = self.memory[:]

        # Extract user-assistant pairs
        pairs = []
        i = 0
        while i < len(messages) - 1:
            if messages[i].role == "user" and messages[i + 1].role == "assistant":
                pairs.append((messages[i], messages[i + 1]))
            i += 2

        # Keep first two and last n pairs
        total_pairs_to_keep = 2 + n
        if len(pairs) <= total_pairs_to_keep:
            for user_msg, assistant_msg in pairs:
                compacted_memory.extend([user_msg, assistant_msg])
        else:
            # Add first two pairs
            for pair in pairs[:2]:
                compacted_memory.extend(pair)
            # Add last n pairs
            for pair in pairs[-n:]:
                compacted_memory.extend(pair)

        self.memory = compacted_memory


class VariableMemory:
    """Memory for a variable."""

    def __init__(self):
        """Initialize the variable memory."""
        self.memory: dict[str, tuple[str, str]] = {}
        self.counter: int = 0

    def add(self, value: str) -> str:
        """Add a value to the variable memory.

        Args:
            value (str): The value to add to memory.

        Returns:
            str: The key associated with the added value.
        """
        self.counter += 1
        key = f"var{self.counter}"
        self.memory[key] = (key, value)
        return key

    def reset(self):
        """Reset the variable memory."""
        self.memory.clear()
        self.counter = 0

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a value from the variable memory.

        Args:
            key (str): The key of the value to retrieve.
            default (str, optional): Default value if key is not found. Defaults to None.

        Returns:
            str | None: The value associated with the key, or default if not found.
        """
        return self.memory.get(key, default)[1] if key in self.memory else default

    def __getitem__(self, key: str) -> str:
        """Get a value using dictionary-style access.

        Args:
            key (str): The key of the value to retrieve.

        Returns:
            str: The value associated with the key.

        Raises:
            KeyError: If the key is not found.
        """
        return self.memory[key][1]

    def __setitem__(self, key: str, value: str):
        """Set a value using dictionary-style assignment.

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.
        """
        self.memory[key] = (key, value)

    def __delitem__(self, key: str):
        """Delete a key-value pair using dictionary-style deletion.

        Args:
            key (str): The key to delete.

        Raises:
            KeyError: If the key is not found.
        """
        del self.memory[key]

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the memory.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        return key in self.memory

    def __len__(self) -> int:
        """Get the number of items in the memory.

        Returns:
            int: Number of items in the memory.
        """
        return len(self.memory)

    def keys(self):
        """Return a view of the memory's keys.

        Returns:
            dict_keys: A view of the memory's keys.
        """
        return self.memory.keys()

    def values(self):
        """Return a view of the memory's values.

        Returns:
            dict_values: A view of the memory's values.
        """
        return (value[1] for value in self.memory.values())

    def items(self):
        """Return a view of the memory's items.

        Returns:
            dict_items: A view of the memory's items.
        """
        return ((key, value[1]) for key, value in self.memory.items())

    def pop(self, key: str, default: str | None = None) -> str | None:
        """Remove and return a value for a key.

        Args:
            key (str): The key to remove.
            default (str, optional): Default value if key is not found. Defaults to None.

        Returns:
            str | None: The value associated with the key, or default if not found.
        """
        return self.memory.pop(key, (None, default))[1] if default is not None else self.memory.pop(key)[1]

    def update(self, other: dict[str, str] | None = None, **kwargs):
        """Update the memory with key-value pairs from another dictionary.

        Args:
            other (dict, optional): Dictionary to update from. Defaults to None.
            **kwargs: Additional key-value pairs to update.
        """
        if other is not None:
            for key, value in other.items():
                self.memory[key] = (key, value)
        for key, value in kwargs.items():
            self.memory[key] = (key, value)
