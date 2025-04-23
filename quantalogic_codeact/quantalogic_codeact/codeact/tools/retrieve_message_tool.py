"""RetrieveMessageTool definition for Quantalogic CodeAct framework."""

from typing import Any, Dict, Optional

from loguru import logger

from quantalogic.tools import Tool, ToolArgument

from ..conversation_manager import ConversationManager
from ..utils import log_tool_method


class RetrieveMessageTool(Tool):
    """Tool to retrieve the content of messages in the conversation history by their nanoid."""

    def __init__(self, conversation_manager: ConversationManager, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the RetrieveMessageTool with conversation manager."""
        try:
            super().__init__(
                name="retrieve_message",
                description=(
                    "Easily retrieve a past message content from the conversation history by its ID.\n"
                    "Only return the content without the nanoid part."
                    "It is THE MANDATORY tool to retrieve messages in the conversation history."
                ),
                arguments=[
                    ToolArgument(
                        name="nanoid",
                        arg_type="string",
                        description="The nanoid of the message to retrieve",
                        required=True,
                    )
                ],
                return_type="string",
            )
            self.config = config or {}
            self.conversation_manager = conversation_manager
        except Exception as e:
            logger.error(f"Failed to initialize RetrieveMessageTool: {e}")
            raise

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        """Execute the tool to retrieve message content."""
        try:
            nanoid: str = kwargs["nanoid"]
            logger.debug(f"Retrieving message with nanoid '{nanoid}'")

            # First try direct lookup in the message dictionary
            message = self.conversation_manager.message_dict.get(nanoid)

            # If not found directly, try case-insensitive lookup
            if not message:
                for key, msg in self.conversation_manager.message_dict.items():
                    if key.lower() == nanoid.lower():
                        message = msg
                        break

            if message:
                result = message.content
                logger.info(f"Retrieved message with nanoid '{nanoid}'")
                return result

            # Search list of messages by their nanoid attribute (case-insensitive)
            for msg in self.conversation_manager.messages:
                if msg.nanoid.lower() == nanoid.lower():
                    logger.info(f"Found message by nanoid attribute '{nanoid}'")
                    return msg.content

            # If not found, search through all messages for content with embedded nanoid
            for msg in self.conversation_manager.messages:
                # Check if the nanoid is embedded in the message content (e.g., "nanoid:BUMr-9ZYbhjKQtJpSesOa")
                # Use case-insensitive comparison
                if nanoid.lower() in msg.content.lower():
                    logger.info(f"Found message with embedded nanoid '{nanoid}'")
                    # If the nanoid is at the beginning of the content, remove it and any newlines
                    # Case-insensitive startswith check
                    content_lower = msg.content.lower()
                    nanoid_lower = nanoid.lower()
                    if content_lower.startswith(f"nanoid:{nanoid_lower}") or content_lower.startswith(nanoid_lower):
                        # Extract content after the nanoid
                        parts = msg.content.split("\n", 1)
                        if len(parts) > 1:
                            result = parts[1]  # Take everything after the first line
                        else:
                            result = msg.content  # If no newline, return the whole content
                        return result
                    return msg.content

            # If still not found, check if nanoid matches any part of the conversation history
            # This may help with history retrieval where nanoids might be embedded in different formats
            logger.debug(f"Performing broader nanoid search for '{nanoid}'")
            for msg in self.conversation_manager.messages:
                # If we can determine that this message is what we're looking for by any reliable means
                # based on the conversation history analysis, return it
                if msg.role == "assistant" and len(msg.content) > 100:  # Only consider substantive assistant messages
                    # Check if nanoid is part of a potential identifier prefix (without being too specific about format)
                    if any(
                        id_part in msg.content[:50].lower()
                        for id_part in [nanoid.lower(), nanoid.lower().replace("-", "")]
                    ):
                        logger.info(f"Found message with potential matching nanoid in content: '{nanoid}'")
                        return msg.content

            error_msg = f"Message with nanoid '{nanoid}' not found"
            logger.warning(error_msg)
            return error_msg
        except Exception as e:
            logger.error(f"Error retrieving message with nanoid '{kwargs.get('nanoid', 'unknown')}': {e}")
            return f"Error: {str(e)}"
