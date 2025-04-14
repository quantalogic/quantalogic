"""Chat command implementation."""
from typing import List


async def chat_command(shell, args: List[str]) -> str:
    """Handle the /chat command with conversation history."""
    if not args:
        return "Please provide a message to chat with the agent."
    
    message = " ".join(args)
    try:
        # Pass the current message_history to the agent for context
        response = await shell.agent.chat(
            message,
            history=shell.message_history,
            streaming=shell.streaming
        )
        # Append user message and agent response to history
        shell.message_history.append({"role": "user", "content": message})
        shell.message_history.append({"role": "assistant", "content": response})
        return response
    except Exception as e:
        return f"Error in chat: {e}"