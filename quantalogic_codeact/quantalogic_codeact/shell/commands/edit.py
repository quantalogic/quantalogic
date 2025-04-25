from typing import List

from rich.console import Console
from rich.panel import Panel

console = Console()


async def edit_command(shell, args: List[str]) -> str:
    """Edit a previous user message: /edit [INDEX_OR_ID]"""
    if not args:
        return "Please provide a message index or ID to edit. Use /history to see messages."
    
    identifier = args[0]
    try:
        # Find message by index or nanoid
        history = shell.current_message_history
        if identifier.isdigit():
            index = int(identifier)
            if 0 <= index < len(history):
                message = history[index]
            else:
                return f"Invalid index: {index}. Use /history to see valid indices."
        else:
            for message in history:
                if message["nanoid"] == identifier:
                    break
            else:
                return f"No message found with ID: {identifier}"
        
        # Queue the message content for editing
        shell.next_input_text = message["content"]
        return "Message loaded for editing. Press Enter to submit or edit the text."
    except Exception as e:
        console.print(Panel(f"Error editing message: {e}", title="Error", border_style="red"))
        return f"Error editing message: {e}"