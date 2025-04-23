import os
import subprocess
import tempfile
from typing import List

from loguru import logger
from rich.console import Console

console = Console()

async def edit_command(shell, args: List[str]) -> str:
    """Edit a previous user message in an external editor.

    Usage:
      /edit [INDEX_OR_ID]

    Examples:
      /edit        # edit last message
      /edit 3      # edit 3rd user message
      /edit -1     # edit last message
      /edit <id>   # edit by message ID
    """
    history = shell.current_message_history
    # Collect all user messages
    user_msgs = [m for m in history if m.get("role") == "user"]
    if not user_msgs:
        return "No user message found to edit."
    # Select message by index or ID
    if args:
        key = args[0]
        try:
            n = int(key)
            idx = n - 1 if n > 0 else len(user_msgs) + n
            if idx < 0 or idx >= len(user_msgs):
                return f"Invalid message index {key}; there are {len(user_msgs)} user messages."
            selected = user_msgs[idx]
        except ValueError:
            selected = next((m for m in user_msgs if m.get("nanoid") == key), None)
            if not selected:
                return f"No user message found with ID {key}."
    else:
        selected = user_msgs[-1]
    nanoid = selected.get("nanoid")
    old_content = selected.get("content", "")

    editor = os.getenv("EDITOR", "vim")
    console.print("[bold blue]Opening external editor for last message...[/bold blue]")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(old_content.encode())
        tmp_path = tmp.name
    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path) as f:
            new_content = f.read().strip()
        if not new_content:
            return "Edited content is empty. Aborting edit."
        # Update conversation manager message object
        msg_obj = shell.conversation_manager.message_dict.get(nanoid)
        if msg_obj:
            msg_obj.content = new_content
        else:
            for m in shell.conversation_manager.messages:
                if m.nanoid == nanoid:
                    m.content = new_content
                    break
        console.print("[bold green]Edited content updated (not resubmitted).[/bold green]")
        shell.next_input_text = new_content
        return ""
    except subprocess.CalledProcessError as e:
        logger.error(f"Error with editor: {e}")
        return f"Error with editor: {e}"
    except Exception as e:
        logger.error(f"Error in edit command: {e}")
        return f"Error in edit command: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
