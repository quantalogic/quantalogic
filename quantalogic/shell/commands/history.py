from typing import List


async def history_command(shell, args: List[str]) -> str:
    """Handle the /history command."""
    if not shell.current_message_history:
        return "No history yet."
    
    history = []
    for msg in shell.current_message_history:
        role = "User" if msg["role"] == "user" else "Assistant"
        color = "blue" if role == "User" else "green"
        history.append(f"[{color}]{role}: {msg['content']}[/{color}]")
    
    return "\n".join(history)