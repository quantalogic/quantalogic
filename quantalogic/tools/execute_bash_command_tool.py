"""Tool for executing bash commands and capturing their output."""

import os
import subprocess
from typing import Dict, Optional, Union

from quantalogic.tools.tool import Tool, ToolArgument


class ExecuteBashCommandTool(Tool):
    """Tool for executing bash commands and capturing their output."""

    name: str = "execute_bash_tool"
    description: str = "Executes a bash command and returns its output."
    need_validation: bool = True
    arguments: list = [
        ToolArgument(
            name="command",
            arg_type="string",
            description="The bash command to execute.",
            required=True,
            example="ls -la",
        ),
        ToolArgument(
            name="working_dir",
            arg_type="string",
            description="The working directory where the command will be executed. Defaults to the current directory.",
            required=False,
            example="/path/to/directory",
        ),
        ToolArgument(
            name="timeout",
            arg_type="int",
            description="Maximum time in seconds to wait for the command to complete. Defaults to 60 seconds.",
            required=False,
            example="60",
        ),
        # Removed the `env` argument from ToolArgument since it doesn't support `dict` type
    ]

    def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: Union[int, str, None] = 60,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        """Executes a bash command and returns its output.

        Args:
            command (str): The bash command to execute.
            working_dir (str, optional): Working directory for command execution. Defaults to the current directory.
            timeout (int or str, optional): Maximum execution time in seconds. Defaults to 60 seconds.
            env (dict, optional): Environment variables to set for the command execution. Defaults to the current environment.

        Returns:
            str: The command output or error message.

        Raises:
            subprocess.TimeoutExpired: If the command execution exceeds the timeout.
            subprocess.CalledProcessError: If the command returns a non-zero exit status.
            ValueError: If the timeout cannot be converted to an integer.
        """
        # Convert timeout to integer, defaulting to 60 if None or invalid
        try:
            timeout_seconds = int(timeout) if timeout else 60
        except (ValueError, TypeError):
            timeout_seconds = 60

        # Use the current working directory if no working directory is specified
        cwd = working_dir if working_dir else os.getcwd()

        # Use the current environment if no custom environment is specified
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)

        try:
            # Execute the command with specified timeout, working directory, and environment
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env_vars,
            )

            formated_result = (
                "<command_output>"
                f" <stdout>"
                f"{result.stdout.strip()}"
                f" </stdout>"
                f" <stderr>"
                f"{result.stderr.strip()}"
                f" </stderr>"
                f" <returncode>"
                f" {result.returncode}"
                f" </returncode>"
                f"</command_output>"
            )

            return formated_result

        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout_seconds} seconds."
        except subprocess.CalledProcessError as e:
            return f"Command failed with error: {e.stderr.strip()}"
        except Exception as e:
            return f"Unexpected error executing command: {str(e)}"


if __name__ == "__main__":
    tool = ExecuteBashCommandTool()
    print(tool.to_markdown())
