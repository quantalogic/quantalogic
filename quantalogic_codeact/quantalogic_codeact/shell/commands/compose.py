import os
import tempfile
from typing import List

from loguru import logger
from rich.console import Console
from rich.panel import Panel

from ..commands.chat import chat_command
from ..commands.solve import solve_command

console = Console()


async def compose_command(shell, args: List[str]) -> str:
    """Compose input in external editor: /compose"""
    editor = os.environ.get("EDITOR", "vim")
    
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        # Open the editor
        console.print("Opening external editor...")
        os.system(f"{editor} {temp_file_path}")
        
        # Read the edited content
        with open(temp_file_path, "r") as temp_file:
            content = temp_file.read().strip()
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        if not content:
            return "No input provided from editor."
        
        console.print("Input received from editor.")
        logger.debug(f"Composed input: {content}")
        
        # Process the input based on mode
        if shell.agent_config.mode == "codeact":
            return await solve_command(shell, [content])
        else:
            return await chat_command(shell, [content])
    
    except Exception as e:
        logger.error(f"Error in compose command: {e}")
        console.print(Panel(f"Error in compose command: {e}", title="Error", border_style="red"))
        return f"Error in compose command: {e}"
