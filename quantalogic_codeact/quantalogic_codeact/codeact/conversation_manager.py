"""Manages conversation history in LiteLLM message format."""

from typing import Dict, List

from loguru import logger

from .message import Message


class ConversationManager:
    """Manages the storage and summarization of conversation history in LiteLLM format."""
    
    def __init__(self, max_tokens: int = 64*1024):
        """
        Initialize with an empty message list and a token limit.

        Args:
            max_tokens (int): Maximum number of tokens for conversation history (default: 65536).
        """
        self.messages: List[Message] = []
        self.message_dict: Dict[str, Message] = {}
        self.max_tokens: int = max_tokens
        logger.debug(f"Initialized ConversationManager with max_tokens: {max_tokens}")

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            role (str): The role of the message ('user' or 'assistant').
            content (str): The content of the message.
        """
        try:
            message = Message(role=role, content=content)
            self.messages.append(message)
            self.message_dict[message.nanoid] = message
            logger.debug(f"Added message with nanoid '{message.nanoid}' and role '{role}'")
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

    def clear_history(self) -> None:
        """Clear the conversation history."""
        try:
            self.messages.clear()
            self.message_dict.clear()
            logger.debug("Cleared conversation history.")
        except Exception as e:
            logger.error(f"Failed to clear conversation history: {e}")