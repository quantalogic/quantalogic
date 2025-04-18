from typing import List, Dict

class HistoryManager:
    """Manages the conversation history for the shell."""
    
    def __init__(self):
        self._history: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the history."""
        self._history.append({"role": role, "content": content})

    def get_history(self) -> List[Dict[str, str]]:
        """Retrieve the entire conversation history."""
        return self._history

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._history = []