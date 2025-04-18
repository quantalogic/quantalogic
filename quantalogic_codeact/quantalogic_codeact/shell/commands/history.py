from typing import List

from rich.text import Text


async def history_command(shell, args: List[str]) -> Text:
    """Handle the /history command by formatting and displaying the conversation history."""
    history = shell.history_manager.get_history()
    if not history:
        return Text("No history yet.")
    
    text = Text()
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        color = "blue" if role == "User" else "green"
        text.append(f"{role}: ", style=f"bold {color}")
        text.append(msg["content"] + "\n")
    return text