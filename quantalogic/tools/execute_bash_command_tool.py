"""Tool for executing bash commands with interactive input support."""

import os
import select
import signal
import subprocess
import sys
from typing import Dict, Optional, Union

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
            default=os.getcwd(),
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

    def _execute_windows(
        self,
        command: str,
        cwd: str,
        timeout_seconds: int,
        env_vars: Dict[str, str],
    ) -> str:
        """Execute command on Windows platform."""
        try:
            # On Windows, use subprocess with pipes
            process = subprocess.Popen(
                command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=env_vars,
                text=True,
                encoding="utf-8",
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                return_code = process.returncode

                if return_code != 0 and stderr:
                    logger.warning(f"Command failed with error: {stderr}")

                formatted_result = (
                    "<command_output>"
                    f" <stdout>{stdout.strip()}</stdout>"
                    f" <returncode>{return_code}</returncode>"
                    f"</command_output>"
                )
                return formatted_result

            except subprocess.TimeoutExpired:
                process.kill()
                return f"Command timed out after {timeout_seconds} seconds."

        except Exception as e:
            return f"Unexpected error executing command: {str(e)}"

    def _execute_unix(
        self,
        command: str,
        cwd: str,
        timeout_seconds: int,
        env_vars: Dict[str, str],
    ) -> str:
        """Execute command on Unix platform."""
        try:
            master, slave = pty.openpty()
            proc = subprocess.Popen(
                command,
                shell=True,
                stdin=slave,
                stdout=slave,
                stderr=subprocess.STDOUT,
                cwd=cwd,
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
                            break  # Process completed but select timed out
                        raise subprocess.TimeoutExpired(command, timeout_seconds)

                    for fd in rlist:
                        if fd == master:
                            data = os.read(master, 1024).decode()
                            if not data:
                                break_loop = True
                                break
                            stdout_buffer.append(data)
                            sys.stdout.write(data)
                            sys.stdout.flush()
                        elif fd == sys.stdin:
                            user_input = os.read(sys.stdin.fileno(), 1024)
                            os.write(master, user_input)

                    if break_loop or proc.poll() is not None:
                        while True:
                            data = os.read(master, 1024).decode()
                            if not data:
                                break
                            stdout_buffer.append(data)
                            sys.stdout.write(data)
                            sys.stdout.flush()
                        break

            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                return f"Command timed out after {timeout_seconds} seconds."
            except EOFError:
                pass  # Process exited normally
            finally:
                os.close(master)
                proc.wait()

            stdout_content = "".join(stdout_buffer)
            return_code = proc.returncode
            formatted_result = (
                "<command_output>"
                f" <stdout>{stdout_content.strip()}</stdout>"
                f" <returncode>{return_code}</returncode>"
                f"</command_output>"
            )
            return formatted_result
        except Exception as e:
            return f"Unexpected error executing command: {str(e)}"

    def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: Union[int, str, None] = 60,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        """Executes a bash command with interactive input handling."""
        timeout_seconds = int(timeout) if timeout else 60
        cwd = working_dir or os.getcwd()
        env_vars = os.environ.copy()
        if env:
            env_vars.update(env)

        if sys.platform == "win32":
            return self._execute_windows(command, cwd, timeout_seconds, env_vars)
        else:
            if not pty:
                logger.warning("PTY module not available, falling back to Windows-style execution")
                return self._execute_windows(command, cwd, timeout_seconds, env_vars)
            return self._execute_unix(command, cwd, timeout_seconds, env_vars)


if __name__ == "__main__":
    tool = ExecuteBashCommandTool()
    print(tool.to_markdown())
