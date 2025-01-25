#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "textual",
#     "quantalogic"
# ]
# ///

import asyncio
import os
import queue
import threading
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, LoadingIndicator, Markdown

from quantalogic import Agent


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
        self._update_lock = asyncio.Lock()
        self._streaming = True  # Flag to indicate if we're in streaming mode

    def append(self, text: str) -> None:
        """Queue text to be appended to the response."""
        if not self._streaming:
            return  # Don't append if we're not in streaming mode
        
        # Use call_from_thread to schedule async update
        self.app.call_from_thread(self._async_append, text)

    def _async_append(self, text: str) -> None:
        """Async method to append text and update the widget."""
        async def update_content():
            async with self._update_lock:
                self.text_content += text
                if self._streaming:
                    # In streaming mode, wrap in code block
                    await self.update(f"```\n{self.text_content}\n```")
                    
                    # Scroll to the end of the chat view
                    chat_view = self.app.query_one("#chat-view")
                    await chat_view.scroll_end()

        # Create a task to run the async update
        asyncio.create_task(update_content())

    async def update(self, content: str) -> None:
        """Update the markdown content."""
        self._streaming = not content.startswith("**")  # Detect if we're showing formatted content
        await super().update(content)
        self.refresh(layout=True)


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
            if self.current_response:
                # Get the final answer
                final_answer = self.current_response.text_content.strip()

                # Use call_from_thread with an async method
                self.call_from_thread(self._async_handle_task_complete, final_answer)
        elif event == "task_think_start":
            self.call_from_thread(self.toggle_loading, True)
            self.call_from_thread(
                self.add_system_message,
                "🤔 Thinking..."
            )
        elif event == "task_think_end":
            self.call_from_thread(self.toggle_loading, False)
        elif event == "tool_execution_start":
            tool_name = data.get("tool_name") if isinstance(data, dict) else "unknown"
            self.call_from_thread(
                self.add_system_message,
                f"🔧 Using tool: {tool_name}"
            )
        elif event == "error_max_iterations_reached":
            self.call_from_thread(
                self.add_error_message,
                "⚠️ Max iterations reached"
            )
        elif event == "memory_full":
            self.call_from_thread(
                self.add_system_message,
                "💭 Memory full, compacting..."
            )

    def _async_handle_task_complete(self, final_answer: str) -> None:
        """Async method to handle task completion and update UI."""
        async def update_ui():
            # First show completion message
            await self.add_system_message("✅ Task complete!")

            # Get chat view
            chat_view = self.query_one("#chat-view")
            
            # Remove the streaming response widget
            self.current_response.remove()
            
            # Create and mount new formatted response
            response = Response()
            await chat_view.mount(response)
            await response.update(f"**Answer:**\n{final_answer}")
            await chat_view.scroll_end()
            
            # Clear current response reference
            self.current_response = None

            # Toggle input and loading
            await self.toggle_input(True)
            await self.toggle_loading(False)

        # Create task to run the async update
        asyncio.create_task(update_ui())

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
        await self.toggle_input(False)
        await self.toggle_loading(True)

        # Create a new thread for processing the agent's response
        def process_agent_response():
            try:
                task_answer = self.agent.solve_task(input_value, streaming=True)
                self.call_from_thread(
                    self.add_system_message,
                    f"**Task Answer:**\n{task_answer}"
                )
            except Exception as e:
                self.call_from_thread(
                    self.add_error_message,
                    f"⚠️ Error: {str(e)}"
                )
                self.call_from_thread(self.toggle_input, True)
                self.call_from_thread(self.toggle_loading, False)

        thread = threading.Thread(target=process_agent_response, daemon=True)
        thread.start()

    async def toggle_input(self, enabled: bool) -> None:
        """Async method to toggle input field."""
        input_field = self.query_one(Input)
        input_field.disabled = not enabled

    async def toggle_loading(self, visible: bool) -> None:
        """Async method to toggle loading indicator."""
        loading = self.query_one(LoadingIndicator)
        loading.set_class(visible, "visible")

    async def add_system_message(self, text: str) -> None:
        """Async method to add a system message."""
        chat_view = self.query_one("#chat-view")
        message = SystemMessage(text)
        await chat_view.mount(message)
        await chat_view.scroll_end()

    async def add_error_message(self, text: str) -> None:
        """Async method to add an error message."""
        chat_view = self.query_one("#chat-view")
        message = ErrorMessage(text)
        await chat_view.mount(message)
        await chat_view.scroll_end()

    def on_unmount(self) -> None:
        """Clean up worker thread on app exit."""
        pass


if __name__ == "__main__":
    ChatApp().run()