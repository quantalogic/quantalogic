"""Manages conversation history in LiteLLM message format."""

from dataclasses import dataclass
from typing import List

from loguru import logger


@dataclass
class Message:
    role: str
    content: str

class ConversationHistoryManager:
    """Manages the storage and summarization of conversation history in LiteLLM format."""
    
    def __init__(self, max_tokens: int = 64*1024):
        """
        Initialize with an empty message list and a token limit.

        Args:
            max_tokens (int): Maximum number of tokens for conversation history (default: 65536).
        """
        self.messages: List[Message] = []
        self.max_tokens: int = max_tokens
        logger.debug(f"Initialized ConversationHistoryManager with max_tokens: {max_tokens}")

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            role (str): The role of the message ('user' or 'assistant').
            content (str): The content of the message.
        """
        try:
            self.messages.append(Message(role=role, content=content))
            logger.debug(f"Added message with role '{role}' and content '{content}'")
            # TODO: Add token counting and trimming if exceeding max_tokens
        except Exception as e:
            logger.error(f"Failed to add message: {e}")



    def get_history(self) -> List[Message]:
        """Alias for get_messages."""
        try:
            return self.messages
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []

    def summarize(self, task: str = None) -> str:
        """
        Summarize the conversation history, optionally filtering for relevance to the task.

        Args:
            task (str, optional): The current task to filter relevant messages.

        Returns:
            str: A formatted summary of the conversation history.
        """
        try:
            if not self.messages:
                return "No prior conversation."
            if task:
                # Simple filter: include messages mentioning the task
                relevant = [msg for msg in self.messages if task.lower() in msg.content.lower()]
                if not relevant:
                    return "No relevant prior conversation."
                return "\n".join(f"{msg.role.capitalize()}: {msg.content}" for msg in relevant)
            return "\n".join(f"{msg.role.capitalize()}: {msg.content}" for msg in self.messages)
        except Exception as e:
            logger.error(f"Error summarizing conversation history: {e}")
            return "Error summarizing conversation history."