# quantalogic/shell.py
"""Quantalogic Shell CLI system integrated with the Quantalogic CodeAct agent."""
import asyncio
from importlib.metadata import entry_points
from pathlib import Path
from typing import Dict, List, Optional

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

from .command_registry import CommandRegistry
from .commands import (
    chat_command,
    clear_command,
    exit_command,
    help_command,
    history_command,
    mode_command,
    solve_command,
    stream_command,
)


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
        """Register all built-in commands."""
        self.command_registry.register("help", lambda args: help_command(self, args), "Show help for commands: /help [command]")
        self.command_registry.register("chat", lambda args: chat_command(self, args), "Chat with the agent: /chat <message>")
        self.command_registry.register("solve", lambda args: solve_command(self, args), "Solve a task: /solve <task>")
        self.command_registry.register("exit", lambda args: exit_command(self, args), "Exit the shell: /exit")
        self.command_registry.register("history", lambda args: history_command(self, args), "Show conversation history: /history")
        self.command_registry.register("clear", lambda args: clear_command(self, args), "Clear conversation history: /clear")
        self.command_registry.register("stream", lambda args: stream_command(self, args), "Toggle streaming: /stream on|off")
        self.command_registry.register("mode", lambda args: mode_command(self, args), "Set or show the current mode: /mode [react|codeact]")

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

    async def _stream_token_observer(self, event: object) -> None:
        """Observer for streaming tokens."""
        if isinstance(event, StreamTokenEvent) and self.streaming:
            print(event.token, end="", flush=True)

    async def _on_step_started(self, event: StepStartedEvent) -> None:
        rprint(f"[bold yellow]Step {event.step_number}: Started[/bold yellow]")

    async def _on_thought_generated(self, event: ThoughtGeneratedEvent) -> None:
        rprint(f"[bold blue]Thought:[/bold blue] {event.thought}")

    async def _on_action_generated(self, event: ActionGeneratedEvent) -> None:
        rprint(f"[bold magenta]Action:[/bold magenta] {event.action}")

    async def _on_action_executed(self, event: ActionExecutedEvent) -> None:
        rprint(f"[bold green]Action Executed:[/bold green] {event.output}")

    async def _on_step_completed(self, event: StepCompletedEvent) -> None:
        if event.final_answer:
            rprint(event.final_answer)
        else:
            rprint(f"[bold yellow]Step {event.step_number}: Completed[/bold yellow]")

    async def _on_task_completed(self, event: TaskCompletedEvent) -> None:
        rprint("[bold green]Task Completed[/bold green]")
        if event.final_answer:
            rprint(f"[bold]Final Answer:[/bold] {event.final_answer}")
        else:
            rprint(f"[bold red]Reason for incompletion:[/bold red] {event.reason}")
        rprint()

    async def _on_error_occurred(self, event: ErrorOccurredEvent) -> None:
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
                        result = await solve_command(self, [user_input])
                    else:  # react mode
                        result = await chat_command(self, [user_input])
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