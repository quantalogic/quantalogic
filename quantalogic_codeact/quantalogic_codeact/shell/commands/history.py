from typing import List

from rich.console import Group
from rich.markdown import Markdown
from rich.rule import Rule
from rich.text import Text


async def history_command(shell, args: List[str]) -> Group:
    """Handle the /history command by formatting and displaying the conversation history."""
    history_list = shell.current_message_history
    if args:
        if args[0].isdigit():
            n = int(args[0])
            history_list = history_list[-n:]
        else:
            return Text("Invalid argument. Usage: /history [n] where n is a number.", style="red")
    
    if not history_list:
        return Text("No history yet.")
    
    # UX: group consecutive messages (user + assistant) and separate with rules
    pairs = [history_list[i : i + 2] for i in range(0, len(history_list), 2)]
    blocks = []
    # Title header
    blocks.append(Text(f"Conversation History ({len(history_list)} messages)", style="bold underline cyan"))
    # Note: nanoid shown per message below instead of a global list
    # Build each pair
    for idx, pair in enumerate(pairs, start=1):
        # User part
        user_msg = pair[0]
        blocks.append(Text(f"[{idx * 2 - 1}] User (id={user_msg['nanoid']}): ", style="bold blue"))
        blocks.append(Markdown(user_msg["content"]))
        # Assistant part
        if len(pair) > 1:
            assistant_msg = pair[1]
            blocks.append(Text(f"[{idx * 2}] Assistant (id={assistant_msg['nanoid']}): ", style="bold green"))
            blocks.append(Markdown(assistant_msg["content"]))
        # Separator rule
        blocks.append(Rule(style="dim"))
    return Group(*blocks)