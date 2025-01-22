"""Tool for executing bash commands with interactive input support."""

import os
import pty
import select
import signal
import subprocess
import sys
from typing import Dict, Optional, Union

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
        ),
        ToolArgument(
            name="timeout",
            arg_type="int",
            description="Maximum time in seconds to wait for the command to complete. Defaults to 60 seconds.",
            required=False,
            example="60",
        ),
    ]

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
                    
                    # Check if process completed or EOF received
                    if break_loop or proc.poll() is not None:
                        # Read any remaining output
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

            stdout_content = ''.join(stdout_buffer)
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


if __name__ == "__main__":
    tool = ExecuteBashCommandTool()
    print(tool.to_markdown())