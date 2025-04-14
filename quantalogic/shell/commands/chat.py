"""Chat command implementation."""
from typing import List


async def chat_command(shell, args: List[str]) -> str:
    """Handle the /chat command."""
    if not args:
        return "Please provide a message to chat with the agent."
    
    message = " ".join(args)
    shell.message_history.append({"role": "user", "content": message})
    
    try:
        response = await shell.agent.chat(message)
        shell.message_history.append({"role": "assistant", "content": response})
        return response
    except Exception as e:
        return f"Error in chat: {e}"
