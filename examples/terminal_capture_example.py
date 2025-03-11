#!/usr/bin/env python3
"""Example script demonstrating the TerminalCaptureTool usage."""

import os
from pathlib import Path
from loguru import logger

from quantalogic.tools.terminal_capture_tool import TerminalCaptureTool

def setup_output_dir() -> Path:
    """Create and return output directory for captures."""
    output_dir = Path(__file__).parent / "captures"
    output_dir.mkdir(exist_ok=True)
    return output_dir

def capture_terminal(
    tool: TerminalCaptureTool, 
    capture_type: str,
    filename: str,
    command: str | None = None,
    duration: int = 10
) -> None:
    """Capture terminal output.
    
    Args:
        tool: Initialized TerminalCaptureTool
        capture_type: Type of capture ('record' or 'screenshot')
        filename: Output filename
        command: Command to record (for recording only)
        duration: Recording duration in seconds (for recording only)
    """
    output_path = setup_output_dir() / filename
    logger.info(f"Capturing terminal {capture_type} to {output_path}")
    
    result = tool.execute(
        capture_type=capture_type,
        output_path=str(output_path),
        command=command,
        duration=duration,
        overwrite=True
    )
    logger.info(f"Result: {result}")

def main():
    """Run terminal capture examples."""
    tool = TerminalCaptureTool()
    
    # Example 1: Take a terminal screenshot
    capture_terminal(
        tool=tool,
        capture_type="screenshot",
        filename="terminal_window.png"
    )
    
    # Example 2: Record a command execution
    capture_terminal(
        tool=tool,
        capture_type="record",
        filename="command_recording.cast",
        command="echo 'Hello!' && ls -la && pwd"
    )
    
    # Show instructions
    logger.info("\nTo view the captures:")
    logger.info("1. Screenshots are saved as PNG files in the captures directory")
    logger.info("2. To play recordings:")
    logger.info("   asciinema play captures/command_recording.cast")

if __name__ == "__main__":
    main()
