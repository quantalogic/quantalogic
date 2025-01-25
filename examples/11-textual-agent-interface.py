#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "textual",
#     "quantalogic"
# ]
# ///

import os
import queue
import threading
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, LoadingIndicator, Markdown

from quantalogic import Agent
from quantalogic.tools import LLMTool


class SystemMessage(Markdown):
    DEFAULT_CSS = """
    SystemMessage {
        background: $panel;
        color: $text-muted;
        margin: 1 8;
        padding: 1;
        border: round $primary;
    }
    """

class ErrorMessage(Markdown):
    DEFAULT_CSS = """
    ErrorMessage {
        background: $error 10%;
        color: $text;
        margin: 1 8;
        padding: 1;
        border: round $error;
    }
    """

class Prompt(Markdown):
    DEFAULT_CSS = """
    Prompt {
        background: $primary 10%;
        margin-right: 8;
        padding: 1;
    }
    """

class Response(Markdown):
    BORDER_TITLE = "DeepSeek"
    DEFAULT_CSS = """
    Response {
        border: round $success;
        margin-left: 8;
        padding: 1;
        min-height: 3;
    }
    """

    def __init__(self, *args, **kwargs):
        content = args[0] if args else ""
        super().__init__(content)
        self.text_content = ""
        self._update_queue = queue.Queue()

    def append(self, text: str) -> None:
        """Queue text to be appended to the response."""
        self._update_queue.put(text)
        self.app.call_from_thread(self._process_updates)

    async def _process_updates(self) -> None:
        """Process any pending updates from the queue."""
        updated = False
        while not self._update_queue.empty():
            try:
                text = self._update_queue.get_nowait()
                self.text_content += text
                await self.update(f"```\n{self.text_content}\n```")
                updated = True
            except queue.Empty:
                break
        
        if updated:
            chat_view = self.app.query_one("#chat-view")
            await chat_view.scroll_end()

class ChatApp(App):
    CSS = """
    #chat-view {
        height: 1fr;
    }
    Input {
        dock: bottom;
    }
    LoadingIndicator {
        dock: bottom;
        height: 1;
        display: none;  /* Hidden by default */
    }
    LoadingIndicator.visible {
        display: block;  /* Show when visible class is added */
    }
    """
    BINDINGS = [("ctrl+c", "quit", "Exit")]

    def __init__(self):
        super().__init__()
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise RuntimeError("Missing DEEPSEEK_API_KEY environment variable")

        # Initialize agent with event handling
        self.agent = Agent(model_name="deepseek/deepseek-chat")
        self.current_response = None
        
        # Set up event listeners
        self.agent.event_emitter.on(
            event=["stream_chunk"],
            listener=self.handle_stream_token
        )
        self.agent.event_emitter.on(
            event=[
                "task_complete",
                "task_think_start",
                "task_think_end",
                "tool_execution_start",
                "tool_execution_end",
                "error_max_iterations_reached",
                "memory_full",
                "memory_compacted",
                "memory_summary",
            ],
            listener=self.handle_event
        )

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()
        with VerticalScroll(id="chat-view"):
            yield Response("Welcome to DeepSeek TUI! Type your question below.")
        yield Input(placeholder="Ask Quantalogic DeepSeek...")
        yield Footer()
        yield LoadingIndicator()

    def handle_stream_token(self, event: str, data: Any | None = None) -> None:
        """Handle streaming tokens from the agent."""
        if self.current_response and data:
            # Convert data to string if needed
            text = str(data) if not isinstance(data, str) else data
            self.current_response.append(text)

    def handle_event(self, event: str, data: Any | None = None) -> None:
        """Handle agent events."""
        if event == "task_complete":
            self.call_from_thread(self.toggle_input, True)
            self.call_from_thread(self.toggle_loading, False)
        elif event == "task_think_start":
            self.call_from_thread(self.toggle_loading, True)
        elif event == "task_think_end":
            self.call_from_thread(self.toggle_loading, False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        # Clear input early to prevent double submission
        input_value = event.value
        event.input.value = ""

        # Get chat view
        chat_view = self.query_one("#chat-view")

        # Add prompt
        prompt = Prompt(input_value)
        await chat_view.mount(prompt)

        # Add response
        response = Response()
        self.current_response = response
        await chat_view.mount(response)

        # Disable input and show loading
        self.toggle_input(False)
        self.toggle_loading(True)

        # Create a new thread for processing the agent's response
        def process_agent_response():
            try:
                self.agent.solve_task(input_value, streaming=True)
            except Exception as e:
                self.call_from_thread(
                    self.add_error_message,
                    f"⚠️ Error: {str(e)}"
                )
                self.call_from_thread(self.toggle_input, True)
                self.call_from_thread(self.toggle_loading, False)

        thread = threading.Thread(target=process_agent_response, daemon=True)
        thread.start()

    def toggle_input(self, enabled: bool) -> None:
        """Toggle input field state."""
        self.query_one(Input).disabled = not enabled

    def toggle_loading(self, visible: bool) -> None:
        """Toggle loading indicator visibility."""
        loader = self.query_one(LoadingIndicator)
        loader.set_class(visible, "visible")

    async def add_system_message(self, text: str) -> None:
        """Add a system status message to the chat."""
        chat_view = self.query_one("#chat-view")
        await chat_view.mount(SystemMessage(text))
        await chat_view.scroll_end()

    async def add_error_message(self, text: str) -> None:
        """Add an error message to the chat."""
        chat_view = self.query_one("#chat-view")
        await chat_view.mount(ErrorMessage(text))
        await chat_view.scroll_end()

    def on_unmount(self) -> None:
        """Clean up worker thread on app exit."""
        pass

if __name__ == "__main__":
    ChatApp().run()