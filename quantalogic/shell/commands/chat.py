from typing import List


async def chat_command(shell, args: List[str]) -> str:
    """Handle the /chat command with conversation history."""
    if not args:
        return "Please provide a message to chat with the agent."
    
    message = " ".join(args)
    try:
        # Pass the current agent's message_history to the agent for context
        response = await shell.current_agent.chat(
            message,
            history=shell.current_message_history,
            streaming=shell.state.streaming
        )
        # Append user message and agent response to history
        shell.current_message_history.append({"role": "user", "content": message})
        shell.current_message_history.append({"role": "assistant", "content": response})
        return response
    except Exception as e:
        return f"Error in chat: {e}"