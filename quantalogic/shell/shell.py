# quantalogic/shell.py
"""Quantalogic Shell CLI system integrated with the Quantalogic CodeAct agent."""
import asyncio
from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable, Dict, List, Optional

from loguru import logger
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich import print as rprint

from quantalogic.codeact.agent import Agent, AgentConfig
from quantalogic.codeact.events import (
    ActionExecutedEvent,
    ActionGeneratedEvent,
    ErrorOccurredEvent,
    StepCompletedEvent,
    StepStartedEvent,
    StreamTokenEvent,
    TaskCompletedEvent,
    ThoughtGeneratedEvent,
)
from quantalogic.codeact.xml_utils import XMLResultHandler


class CommandRegistry:
    """Manages registration and storage of shell commands."""
    def __init__(self):
        self.commands: Dict[str, Dict[str, Callable | str]] = {}

    def register(self, name: str, func: Callable, help_text: str) -> None:
        self.commands[name] = {"func": func, "help": help_text}
        logger.debug(f"Registered command: {name}")


class Shell:
    """Interactive CLI shell for dialog with Quantalogic agents."""
    def __init__(self, agent_config: Optional[AgentConfig] = None):
        self.agent = Agent(config=agent_config or AgentConfig(enabled_toolboxes=None, tools_config=None))
        self.message_history: List[Dict[str, str]] = []
        self.streaming: bool = True
        self.mode: str = "codeact"  # Default mode set to "codeact"
        self.command_registry = CommandRegistry()
        self._register_builtin_commands()
        self._load_plugin_commands()

    def _register_builtin_commands(self) -> None:
        """Register all built-in commands, including the new /mode command."""
        self.command_registry.register("help", self.help_command, "Show help for commands: /help [command]")
        self.command_registry.register("chat", self.chat_command, "Chat with the agent: /chat <message>")
        self.command_registry.register("solve", self.solve_command, "Solve a task: /solve <task>")
        self.command_registry.register("exit", self.exit_command, "Exit the shell: /exit")
        self.command_registry.register("history", self.history_command, "Show conversation history: /history")
        self.command_registry.register("clear", self.clear_command, "Clear conversation history: /clear")
        self.command_registry.register("stream", self.stream_command, "Toggle streaming: /stream on|off")
        self.command_registry.register("mode", self.mode_command, "Set or show the current mode: /mode [react|codeact]")

    def _load_plugin_commands(self) -> None:
        """Load plugin commands from entry points."""
        try:
            eps = entry_points(group="quantalogic.shell.commands")
            for ep in eps:
                try:
                    cmd_func = ep.load()
                    self.command_registry.register(ep.name, cmd_func, f"Plugin command: {ep.name}")
                except Exception as e:
                    logger.error(f"Failed to load plugin command {ep.name}: {e}")
        except Exception as e:
            logger.error(f"Error retrieving shell command entry points: {e}")

    async def help_command(self, args: List[str]) -> str:
        """Display help text, including mode information."""
        if args:
            command = args[0]
            if command in self.command_registry.commands:
                return self.command_registry.commands[command]["help"]
            return f"Command '/{command}' not found."
        help_text = "Available commands:\n" + "\n".join(
            f"- /{cmd}: {info['help']}" for cmd, info in self.command_registry.commands.items()
        )
        mode_info = (
            f"\n\nCurrent mode: {self.mode}\n"
            f"- In 'codeact' mode, plain messages are treated as tasks to solve.\n"
            f"- In 'react' mode, plain messages are treated as chat messages.\n"
            f"Use /mode [react|codeact] to switch modes."
        )
        return help_text + mode_info

    async def chat_command(self, args: List[str]) -> Optional[str]:
        """Handle the /chat command."""
        if not args:
            return "Error: Please provide a message (e.g., Hello or /chat Hello)"
        message = args[0]  # Entire input is the message
        user_message = {"role": "user", "content": message}
        self.message_history.append(user_message)
        try:
            if self.streaming:
                self.agent.add_observer(self._stream_token_observer, ["StreamToken"])
                response = await self.agent.chat(
                    message,
                    use_tools=False,
                    streaming=True
                )
                self.agent._observers = [obs for obs in self.agent._observers if obs[0] != self._stream_token_observer]
                rprint()
                return None
            else:
                response = await self.agent.chat(
                    message,
                    use_tools=False,
                    streaming=False
                )
                self.message_history.append({"role": "assistant", "content": response})
                return response
        except Exception as e:
            error_msg = f"Chat error: {str(e)}"
            self.message_history.append({"role": "assistant", "content": error_msg})
            return error_msg

    async def solve_command(self, args: List[str]) -> Optional[str]:
        """Handle the /solve command."""
        if not args:
            return "Error: Please provide a task (e.g., /solve Calculate 2 + 2)"
        task = args[0]  # Entire input after '/solve' is the task
        try:
            if self.streaming:
                observers_to_add = [
                    (self._stream_token_observer, ["StreamToken"]),
                    (self._on_step_started, ["StepStarted"]),
                    (self._on_thought_generated, ["ThoughtGenerated"]),
                    (self._on_action_generated, ["ActionGenerated"]),
                    (self._on_action_executed, ["ActionExecuted"]),
                    (self._on_step_completed, ["StepCompleted"]),
                    (self._on_task_completed, ["TaskCompleted"]),
                    (self._on_error_occurred, ["ErrorOccurred"]),
                ]
                for observer, event_types in observers_to_add:
                    self.agent.add_observer(observer, event_types)

            history = await self.agent.solve(task, streaming=self.streaming)

            if self.streaming:
                for observer, _ in observers_to_add:
                    self.agent._observers = [obs for obs in self.agent._observers if obs[0] != observer]
                rprint()  # Add a newline for clean output

            # Handle non-streaming case
            if not self.streaming:
                if history and "result" in history[-1]:
                    final_answer = self._extract_final_answer(history[-1]["result"])
                    self.message_history.append({"role": "user", "content": task})
                    self.message_history.append({"role": "assistant", "content": final_answer})
                    return final_answer
                else:
                    error_msg = "Task did not complete successfully."
                    self.message_history.append({"role": "user", "content": task})
                    self.message_history.append({"role": "assistant", "content": error_msg})
                    return error_msg
            else:
                # When streaming, output is handled by observers
                return None
        except Exception as e:
            error_msg = f"Solve error: {str(e)}"
            self.message_history.append({"role": "user", "content": task})
            self.message_history.append({"role": "assistant", "content": error_msg})
            return error_msg if not self.streaming else None

    async def exit_command(self, args: List[str]) -> None:
        """Handle the /exit command."""
        raise SystemExit

    async def history_command(self, args: List[str]) -> str:
        """Handle the /history command."""
        if not self.message_history:
            return "No conversation history."
        return "\n".join(f"{msg['role']}: {msg['content']}" for msg in self.message_history)

    async def clear_command(self, args: List[str]) -> str:
        """Handle the /clear command."""
        self.message_history = []
        return "Conversation history cleared."

    async def stream_command(self, args: List[str]) -> str:
        """Handle the /stream command."""
        if not args or args[0] not in ["on", "off"]:
            return "Usage: /stream on|off"
        self.streaming = args[0] == "on"
        return f"Streaming {'enabled' if self.streaming else 'disabled'}."

    async def mode_command(self, args: List[str]) -> str:
        """Handle the /mode command to switch or display the current mode."""
        if not args:
            return f"Current mode: {self.mode}"
        mode = args[0]
        if mode in ["react", "codeact"]:
            self.mode = mode
            return f"Mode set to {self.mode}."
        else:
            return "Usage: /mode react|codeact"

    async def _stream_token_observer(self, event: object) -> None:
        """Observer for streaming tokens."""
        if isinstance(event, StreamTokenEvent):
            rprint(event.token, end="", flush=True)

    async def _on_step_started(self, event: StepStartedEvent):
        rprint(f"[bold yellow]Starting Step {event.step_number}[/bold yellow]")

    async def _on_thought_generated(self, event: ThoughtGeneratedEvent):
        rprint(f"[bold cyan]Step {event.step_number}: Thought[/bold cyan]")
        rprint(event.thought)
        rprint()

    async def _on_action_generated(self, event: ActionGeneratedEvent):
        rprint(f"[bold blue]Step {event.step_number}: Action[/bold blue]")
        rprint(event.action_code)
        rprint()

    async def _on_action_executed(self, event: ActionExecutedEvent):
        summary = XMLResultHandler.format_result_summary(event.result_xml)
        rprint(f"[bold magenta]Step {event.step_number}: Result[/bold magenta]")
        rprint(summary)
        rprint()

    async def _on_step_completed(self, event: StepCompletedEvent):
        if event.is_complete:
            rprint(f"[bold green]Step {event.step_number}: Completed with final answer[/bold green]")
            rprint(event.final_answer)
        else:
            rprint(f"[bold yellow]Step {event.step_number}: Completed[/bold yellow]")

    async def _on_task_completed(self, event: TaskCompletedEvent):
        rprint("[bold green]Task Completed[/bold green]")
        if event.final_answer:
            rprint(f"[bold]Final Answer:[/bold] {event.final_answer}")
        else:
            rprint(f"[bold red]Reason for incompletion:[/bold red] {event.reason}")
        rprint()

    async def _on_error_occurred(self, event: ErrorOccurredEvent):
        rprint(f"[bold red]Error at Step {event.step_number}: {event.error_message}[/bold red]")

    def _extract_final_answer(self, result: str) -> str:
        """Extract the final answer from a solve result."""
        try:
            from lxml import etree
            root = etree.fromstring(result)
            final_answer = root.findtext("FinalAnswer") or root.findtext("Value") or "No final answer found."
            return final_answer.strip()
        except Exception as e:
            logger.error(f"Failed to parse result XML: {e}")
            return result

    async def run(self) -> None:
        """Run the interactive shell loop."""
        history_file = Path.home() / ".quantalogic_shell_history"
        # Define custom key bindings
        kb = KeyBindings()
        @kb.add('enter')
        def _(event):
            event.app.current_buffer.validate_and_handle()  # Submit on Enter
        @kb.add(Keys.ControlJ)  # Ctrl+J for newline
        def _(event):
            event.app.current_buffer.insert_text('\n')

        session = PromptSession(
            message=f"[{self.agent.name or 'Agent'}]> ",
            completer=NestedCompleter({cmd: None for cmd in self.command_registry.commands}),
            multiline=False,  # Single-line by default, newlines via Ctrl+J
            history=FileHistory(str(history_file)),
            key_bindings=kb
        )
        rprint("Welcome to Quantalogic Shell.")
        rprint(f"Mode: {self.mode} - plain messages are {'tasks to solve' if self.mode == 'codeact' else 'chat messages'}.")
        rprint("Type /help for commands. Press Enter to send, Ctrl+J for new lines.")
        while True:
            try:
                user_input = await session.prompt_async()
                user_input = user_input.strip()
                if not user_input:
                    continue
                # Handle commands (start with /) or default to mode-based action
                if user_input.startswith('/'):
                    command_input = user_input[1:].strip()  # Remove leading /
                    if not command_input:
                        rprint("Error: No command provided. Try /help.")
                        continue
                    parts = command_input.split(maxsplit=1)
                    command_name = parts[0]
                    args = [parts[1]] if len(parts) > 1 else []  # Preserve newlines
                    if command_name in self.command_registry.commands:
                        result = await self.command_registry.commands[command_name]["func"](args)
                        if result:
                            rprint(result)
                    else:
                        rprint(f"Unknown command: /{command_name}. Try /help.")
                else:
                    # Default action based on current mode
                    if self.mode == "codeact":
                        result = await self.solve_command([user_input])
                    else:  # react mode
                        result = await self.chat_command([user_input])
                    if result:
                        rprint(result)
            except KeyboardInterrupt:
                rprint("\nUse '/exit' to quit the shell.")
            except SystemExit:
                rprint("Goodbye!")
                break
            except Exception as e:
                rprint(f"Error: {e}")


def main() -> None:
    shell = Shell()
    asyncio.run(shell.run())


if __name__ == "__main__":
    main()