from typing import List

from rich.text import Text


async def history_command(shell, args: List[str]) -> Text:
    """Handle the /history command by formatting and displaying the conversation history."""
    history = shell.current_message_history
    if args and args[0].isdigit():
        history = history[-int(args[0]):]
    if not history:
        return Text("No history yet.")
    
    text = Text()
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        color = "bright_blue" if shell.high_contrast and role == "User" else "blue" if role == "User" else "bright_green" if shell.high_contrast else "green"
        text.append(f"{role}: ", style=f"bold {color}")
        text.append(msg["content"] + "\n")
    return text