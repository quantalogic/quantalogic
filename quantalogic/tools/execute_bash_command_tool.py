"""Tool for executing bash commands with interactive input support."""

import os
import select
import signal
import subprocess
import sys
from typing import Dict, Optional, Union
from pathlib import Path
from datetime import datetime
import shutil
import re

from loguru import logger

# Platform-specific imports
try:
    if sys.platform != "win32":
        import pty
except ImportError as e:
    logger.warning(f"Could not import platform-specific module: {e}")
    pty = None

from quantalogic.tools.tool import Tool, ToolArgument


class ExecuteBashCommandTool(Tool):
    """Tool for executing bash commands with real-time I/O handling."""

    name: str = "execute_bash_tool"
    description: str = "Executes a bash command and returns its output. All commands are executed in /tmp for security."
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
            name="timeout",
            arg_type="int",
            description="Maximum time in seconds to wait for the command to complete. Defaults to 60 seconds.",
            required=False,
            example="60",
            default="60",
        ),
    ]

    def _validate_command(self, command: str) -> None:
        """Validate the command for potential security risks."""
        forbidden_commands = ["rm -rf /", "mkfs", "dd", ":(){ :|:& };:"]
        for cmd in forbidden_commands:
            if cmd in command.lower():
                raise ValueError(f"Command '{command}' contains forbidden operation")

    def _handle_mkdir_command(self, command: str) -> str:
        """Handle mkdir command with automatic cleanup and date suffix.
        
        Args:
            command: The original mkdir command
            
        Returns:
            Modified command that handles existing directories and adds date suffix
        """
        try:
            # Extract directory name from mkdir command
            mkdir_pattern = r'mkdir\s+(?:-p\s+)?["\']?([^"\'>\n]+)["\']?'
            match = re.search(mkdir_pattern, command)
            if not match:
                return command
                
            dir_name = match.group(1)
            # Add timestamp suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_dir_name = f"{dir_name}_{timestamp}"
            
            # Create cleanup and mkdir commands
            cleanup_cmd = f'rm -rf "{dir_name}" 2>/dev/null; '
            mkdir_cmd = command.replace(dir_name, new_dir_name)
            
            return cleanup_cmd + mkdir_cmd
            
        except Exception as e:
            logger.warning(f"Error processing mkdir command: {e}")
            return command

    def _format_output(self, stdout: str, return_code: int, error: Optional[str] = None) -> str:
        """Format command output with stdout, return code, and optional error."""
        formatted_result = "<command_output>\n"
        formatted_result += f" <stdout>{stdout.strip()}</stdout>\n"
        formatted_result += f" <returncode>{return_code}</returncode>\n"
        if error:
            formatted_result += f" <error>{error}</error>\n"
        formatted_result += "</command_output>"
        return formatted_result

    def _execute_windows(
        self,
        command: str,
        timeout_seconds: int,
        env_vars: Dict[str, str],
        cwd: Optional[str] = None,
    ) -> str:
        """Execute command on Windows platform."""
        try:
            # Handle mkdir commands
            if "mkdir" in command:
                command = self._handle_mkdir_command(command)

            # On Windows, use subprocess with pipes
            process = subprocess.Popen(
                command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd="/tmp",  # cwd, Force /tmp directory
                env=env_vars,
                text=True,
                encoding="utf-8",
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                return_code = process.returncode
                return self._format_output(stdout, return_code, stderr if stderr else None)

            except subprocess.TimeoutExpired:
                process.kill()
                return self._format_output("", 1, f"Command timed out after {timeout_seconds} seconds")

        except Exception as e:
            return self._format_output("", 1, f"Unexpected error executing command: {str(e)}")

    def _execute_unix(
        self,
        command: str,
        timeout_seconds: int,
        env_vars: Dict[str, str],
    ) -> str:
        """Execute command on Unix platform."""
        try:
            # Handle mkdir commands
            if "mkdir" in command:
                command = self._handle_mkdir_command(command)

            master, slave = pty.openpty()
            proc = subprocess.Popen(
                command,
                shell=True,
                stdin=slave,
                stdout=slave,
                stderr=subprocess.STDOUT,
                cwd="/tmp",                # cwd=cwd, # Force /tmp directory
                env=env_vars,
                preexec_fn=os.setsid,
                close_fds=True,
            )
            os.close(slave)

            stdout_buffer = []
            break_loop = False

            try:
                while True:
                    rlist, _, _ = select.select([master, sys.stdin], [], [], timeout_seconds)
                    if not rlist:
                        if proc.poll() is not None:
                            break
                        raise subprocess.TimeoutExpired(command, timeout_seconds)

                    for fd in rlist:
                        if fd == master:
                            try:
                                data = os.read(master, 1024).decode()
                                if not data:
                                    break_loop = True
                                    break
                                stdout_buffer.append(data)
                                sys.stdout.write(data)
                                sys.stdout.flush()
                            except (OSError, UnicodeDecodeError) as e:
                                logger.warning(f"Error reading output: {e}")
                                break_loop = True
                                break
                        elif fd == sys.stdin:
                            try:
                                user_input = os.read(sys.stdin.fileno(), 1024)
                                os.write(master, user_input)
                            except OSError as e:
                                logger.warning(f"Error handling input: {e}")

                    if break_loop or proc.poll() is not None:
                        try:
                            while True:
                                data = os.read(master, 1024).decode()
                                if not data:
                                    break
                                stdout_buffer.append(data)
                                sys.stdout.write(data)
                                sys.stdout.flush()
                        except (OSError, UnicodeDecodeError):
                            pass
                        break

            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                return self._format_output("", 1, f"Command timed out after {timeout_seconds} seconds")
            except EOFError:
                pass
            finally:
                os.close(master)
                proc.wait()

            stdout_content = "".join(stdout_buffer)
            return_code = proc.returncode
            return self._format_output(stdout_content, return_code)

        except Exception as e:
            return self._format_output("", 1, f"Unexpected error executing command: {str(e)}")

    def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,  # Kept for backward compatibility but ignored
        timeout: Union[int, str, None] = 60,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        """Executes a bash command with interactive input handling in /tmp directory."""
        # Ensure /tmp exists and is writable
        tmp_dir = Path("/tmp")
        if not (tmp_dir.exists() and os.access(tmp_dir, os.W_OK)):
            return self._format_output("", 1, "Error: /tmp directory is not accessible")

        # Validate command
        try:
            self._validate_command(command)
        except ValueError as e:
            return self._format_output("", 1, str(e))

        timeout_seconds = int(timeout) if timeout else 60
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)

        if sys.platform == "win32":
            return self._execute_windows(command, timeout_seconds, env_vars)
        else:
            if not pty:
                logger.warning("PTY module not available, falling back to Windows-style execution")
                return self._execute_windows(command, timeout_seconds, env_vars)
            return self._execute_unix(command, timeout_seconds, env_vars)


if __name__ == "__main__":
    tool = ExecuteBashCommandTool()
    print(tool.to_markdown())
