"""Tool for capturing terminal recordings and screenshots."""

import os
import shlex
import subprocess
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

from quantalogic.tools.execute_bash_command_tool import ExecuteBashCommandTool
from quantalogic.tools.tool import Tool, ToolArgument


class CaptureType(str, Enum):
    """Type of terminal capture."""
    RECORD = "record"
    SCREENSHOT = "screenshot"


class TerminalCaptureTool(Tool):
    """Tool for capturing terminal output as recordings or screenshots."""

    name: str = "terminal_capture_tool"
    description: str = "Captures terminal output as recordings or screenshots."
    need_validation: bool = False
    arguments: list = [
        ToolArgument(
            name="capture_type",
            arg_type="string",
            description="Type of capture ('record' or 'screenshot')",
            required=True,
            example="screenshot",
        ),
        ToolArgument(
            name="output_path",
            arg_type="string",
            description="Path where to save the capture (use .cast for recordings, .png for screenshots)",
            required=True,
            example="/path/to/output.png",
        ),
        ToolArgument(
            name="command",
            arg_type="string",
            description="Command to execute and capture (only for recording)",
            required=False,
            example="ls -la",
        ),
        ToolArgument(
            name="duration",
            arg_type="int",
            description="Duration in seconds for recording (only for recording)",
            required=False,
            default="30",
        ),
        ToolArgument(
            name="overwrite",
            arg_type="boolean",
            description="Whether to overwrite existing file",
            required=False,
            default="true",
        ),
    ]

    def __init__(self):
        """Initialize with ExecuteBashCommandTool for command execution."""
        super().__init__()
        self.bash_tool = ExecuteBashCommandTool()

    def _ensure_dependencies(self, capture_type: CaptureType) -> bool:
        """Check if required dependencies are installed.
        
        Args:
            capture_type: Type of capture to check dependencies for
        """
        if capture_type == CaptureType.RECORD:
            try:
                # Check for asciinema using poetry run
                result = subprocess.run(
                    ["poetry", "run", "which", "asciinema"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and result.stdout:
                    logger.info(f"Found asciinema at: {result.stdout.strip()}")
                    return True

                # If not found, try installing it
                logger.info("Installing asciinema...")
                install_result = subprocess.run(
                    ["poetry", "add", "asciinema"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if install_result.returncode == 0:
                    logger.info("Successfully installed asciinema")
                    return True
                    
                logger.error(f"Failed to install asciinema: {install_result.stderr}")
                return False
                
            except Exception as e:
                logger.error(f"Error checking/installing asciinema: {e}")
                return False
                
        elif capture_type == CaptureType.SCREENSHOT:
            try:
                # Try gnome-screenshot first
                result = subprocess.run(
                    ["which", "gnome-screenshot"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    logger.info("Found gnome-screenshot")
                    return True
                    
                # Try import from ImageMagick as fallback
                result = subprocess.run(
                    ["which", "import"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    logger.info("Found ImageMagick import")
                    return True
                
                logger.error("Neither gnome-screenshot nor ImageMagick found")
                return False
                
            except Exception as e:
                logger.error(f"Error checking screenshot dependencies: {e}")
                return False

    def _capture_screenshot(
        self,
        output_path: str,
        overwrite: bool = True
    ) -> str:
        """Capture terminal screenshot.
        
        Args:
            output_path: Path to save screenshot
            overwrite: Whether to overwrite existing file
        """
        try:
            # Ensure output directory exists
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if file exists and handle overwrite
            if output_path.exists():
                if not overwrite:
                    return f"File {output_path} already exists and overwrite=False"
                try:
                    output_path.unlink()
                except OSError as e:
                    return f"Failed to remove existing file: {str(e)}"
            
            # Get active window ID
            window_id = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if window_id.returncode != 0:
                return "Failed to get active window ID"
            
            # Try gnome-screenshot first
            if subprocess.run(["which", "gnome-screenshot"], capture_output=True).returncode == 0:
                cmd = f"gnome-screenshot --window --file={shlex.quote(str(output_path))}"
            else:
                # Fallback to ImageMagick's import
                cmd = f"import -window {window_id.stdout.strip()} {shlex.quote(str(output_path))}"
            
            logger.debug(f"Running command: {cmd}")
            result = self.bash_tool.execute(command=cmd)
            
            if output_path.exists():
                return f"Screenshot saved to {output_path}"
            else:
                return f"Failed to capture screenshot: {result}"
                
        except Exception as e:
            return f"Failed to capture screenshot: {str(e)}"

    def _record_terminal(
        self, 
        output_path: str, 
        command: str,
        duration: int = 30,
        overwrite: bool = True
    ) -> str:
        """Record terminal session using asciinema.
        
        Args:
            output_path: Path to save recording (.cast file)
            command: Command to execute
            duration: Recording duration in seconds
            overwrite: Whether to overwrite existing file
        """
        try:
            # Ensure output directory exists
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if file exists and handle overwrite
            if output_path.exists():
                if not overwrite:
                    return f"File {output_path} already exists and overwrite=False"
                try:
                    output_path.unlink()
                except OSError as e:
                    return f"Failed to remove existing file: {str(e)}"
            
            # Properly escape the command for shell execution
            escaped_command = shlex.quote(command)
            
            # Record terminal session using poetry run to ensure correct virtualenv
            record_cmd = (
                f"poetry run asciinema rec -c {escaped_command} "
                f"-t 'Terminal Recording {datetime.now()}' "
                f"{shlex.quote(str(output_path))}"
            )
            logger.debug(f"Running command: {record_cmd}")
            
            result = self.bash_tool.execute(
                command=record_cmd,
                timeout=duration
            )
            
            if output_path.exists():
                return f"Recording saved to {output_path}"
            else:
                return f"Failed to record: {result}"
                
        except Exception as e:
            return f"Failed to record terminal: {str(e)}"

    def execute(
        self,
        capture_type: str,
        output_path: str,
        command: Optional[str] = None,
        duration: Optional[int] = 30,
        overwrite: Optional[bool] = True,
    ) -> str:
        """Execute the terminal capture.

        Args:
            capture_type: Type of capture ('record' or 'screenshot')
            output_path: Path where to save the capture
            command: Command to execute and capture (only for recording)
            duration: Duration in seconds for recording (only for recording)
            overwrite: Whether to overwrite existing file

        Returns:
            A string indicating success or failure
        """
        try:
            capture_type_enum = CaptureType(capture_type.lower())
        except ValueError:
            return f"Invalid capture type: {capture_type}. Must be 'record' or 'screenshot'"
            
        if not self._ensure_dependencies(capture_type_enum):
            if capture_type_enum == CaptureType.RECORD:
                return "asciinema not found and failed to install it. Please install manually: poetry add asciinema"
            else:
                return "Screenshot tools not found. Please install: sudo apt install gnome-screenshot"
            
        if capture_type_enum == CaptureType.SCREENSHOT:
            return self._capture_screenshot(output_path, overwrite)
        else:
            if not command:
                return "Command is required for recording"
            return self._record_terminal(output_path, command, duration, overwrite)


if __name__ == "__main__":
    tool = TerminalCaptureTool()
    print(tool.to_markdown())
