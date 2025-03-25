"""Tool for launching VS Code Server instances."""

import os
import subprocess
import urllib.parse
from typing import Dict, Optional, Union

from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class VSCodeServerTool(Tool):
    """Tool for launching VS Code Server instances with configurable settings."""

    name: str = "vscode_tool"
    description: str = "Launches a VS Code Server instance for remote development."
    need_validation: bool = False
    arguments: list = [
        ToolArgument(
            name="workspace_path",
            arg_type="string",
            description="The path to the workspace directory to open in VS Code.",
            required=True,
            example="/path/to/workspace",
        ),
        ToolArgument(
            name="auth",
            arg_type="string",
            description="Authentication mode for VS Code Server ('none' or 'password').",
            required=False,
            example="none",
            default="none",
        ),
        ToolArgument(
            name="port",
            arg_type="int",
            description="Port number for the VS Code Server.",
            required=False,
            example="8080",
            default="8080",
        ),
    ]

    def execute(
        self,
        workspace_path: str,
        auth: str = "none",
        port: Union[int, str] = 8080,
    ) -> str:
        """Launch a VS Code Server instance with the specified configuration.
        
        Args:
            workspace_path: Directory to open in VS Code
            auth: Authentication mode ('none' or 'password')
            port: Port number for the server
            
        Returns:
            Formatted string containing command output and status
        """
        try:
            # Validate workspace path
            workspace_path = os.path.abspath(workspace_path)
            if not os.path.exists(workspace_path):
                return f"Error: Workspace path does not exist: {workspace_path}"

            # Build the command
            command = [
                "code-server",
                f"--auth={auth}",
                f"--port={port}",
                workspace_path
            ]

            # Launch the server
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8"
            )

            # Wait briefly to check for immediate startup errors
            try:
                stdout, stderr = process.communicate(timeout=2)
                if process.returncode is not None and process.returncode != 0:
                    return f"Failed to start VS Code Server: {stderr}"
            except subprocess.TimeoutExpired:
                # Process is still running (expected behavior)
                pass

            # Create URL with folder parameter
            encoded_path = urllib.parse.quote(workspace_path)
            url = f"http://localhost:{port}/?folder={encoded_path}"

            # Return success message with connection details
            return (
                "<command_output>"
                "<div style='background: #1e1e1e; border-radius: 8px; padding: 20px; margin: 10px 0; font-family: Arial, sans-serif;'>"
                "<div style='color: #3fb950; margin-bottom: 15px;'>"
                "✓ VS Code Server started successfully"
                "</div>"
                "<div style='background: #2d2d2d; padding: 15px; border-radius: 6px; border-left: 4px solid #58a6ff;'>"
                "<div style='color: #8b949e; margin-bottom: 8px;'>Server URL:</div>"
                f"<a href='{url}' style='color: #58a6ff; text-decoration: none; display: block; word-break: break-all;'>"
                f"Display App builder"
                "</a>"
                "</div>"
                "<div style='color: #8b949e; font-size: 0.9em; margin-top: 15px;'>"
                "Click the link above to open VS Code in your browser"
                "</div>"
                "</div>"
                "</command_output>"
            )

        except Exception as e:
            logger.error(f"Error launching VS Code Server: {str(e)}")
            return f"Unexpected error: {str(e)}"


if __name__ == "__main__":
    tool = VSCodeServerTool()
