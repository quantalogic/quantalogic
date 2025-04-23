import os
import subprocess
import tempfile
from typing import List

from loguru import logger
from rich.console import Console

console = Console()

async def edit_command(shell, args: List[str]) -> str:
    """Edit the last user message in an external editor: /edit"""
    history = shell.current_message_history
    # Collect all user messages
    user_msgs = [m for m in history if m.get("role") == "user"]
    if not user_msgs:
        return "No user message found to edit."
    # Determine target index (1-based), default to last
    if args and args[0].isdigit():
        idx = int(args[0]) - 1
        if idx < 0 or idx >= len(user_msgs):
            return f"Invalid message index {args[0]}; there are {len(user_msgs)} user messages."
    else:
        idx = len(user_msgs) - 1
    last_msg = user_msgs[idx]
    old_content = last_msg.get("content", "")

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
        # Update history and queue next input
        last_msg["content"] = new_content
        console.print("[bold green]Edited content updated (not resubmitted).[/bold green]")
        # Prefill next prompt with edited content (manual submit)
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
