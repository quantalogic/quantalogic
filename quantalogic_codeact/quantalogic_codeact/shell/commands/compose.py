import os
import subprocess
import tempfile
from typing import List

from loguru import logger
from rich.console import Console

from .chat import chat_command
from .solve import solve_command

console = Console()

async def compose_command(shell, args: List[str]) -> str:
    """Compose multi-line input using an external editor: /compose"""
    editor = os.getenv("EDITOR", "vim")
    console.print("[bold blue]Opening external editor...[/bold blue]")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path) as f:
            content = f.read().strip()
        if not content:
            return "No input provided."
        console.print("[bold blue]Input received from editor.[/bold blue]")
        if shell.state.mode == "codeact":
            await solve_command(shell, [content])
        else:  # react mode
            await chat_command(shell, [content])
        return ""  # Output is handled by solve or chat command
    except subprocess.CalledProcessError as e:
        logger.error(f"Error with editor: {e}")
        return f"Error with editor: {e}"
    except Exception as e:
        logger.error(f"Error in compose command: {e}")
        return f"Error in compose command: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to delete temporary file: {e}")