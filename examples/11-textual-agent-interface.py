#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "textual",
#     "quantalogic",
#     "loguru"
# ]
# ///

import os
import threading
from typing import Any

from loguru import logger
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
        super().__init__(*args, **kwargs)
        self.text_content = ""
        self._update_lock = threading.Lock()
        self._streaming = True

    def append(self, text: str):
        """Thread-safe text appending"""
        if self._streaming and text:
            self.app.call_from_thread(self._append_text, text)

    def _append_text(self, text: str):
        """Main thread text append operation"""
        with self._update_lock:
            self.text_content += text
            self.update(f"```\n{self.text_content}\n```")
            self.query_one("VerticalScroll", None).scroll_end(animate=False)

    def reset_stream_state(self):
        """Prepare for new streaming session"""
        self.text_content = ""
        self._streaming = True


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
        display: none;
    }
    LoadingIndicator.visible {
        display: block;
    }
    """
    BINDINGS = [("ctrl+c", "quit", "Exit")]

    def __init__(self):
        super().__init__()
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise RuntimeError("Missing DEEPSEEK_API_KEY environment variable")

        self.agent = Agent(model_name="deepseek/deepseek-chat")
        self.current_response = None
        self._response_lock = threading.Lock()

        # Event listeners setup
        self.agent.event_emitter.on("stream_chunk", self.handle_stream_chunk)
        self.agent.event_emitter.on([
            "task_complete", "task_think_start", "task_think_end",
            "tool_execution_start", "error_max_iterations_reached",
            "memory_full"
        ], self.handle_agent_event)

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="chat-view"):
            yield Response("Welcome to DeepSeek TUI! Type your question below.")
        yield Input(placeholder="Ask Quantalogic DeepSeek...")
        yield Footer()
        yield LoadingIndicator()

    def handle_stream_chunk(self, event: str, data: Any):
        """Handle real-time streaming chunks"""
        with self._response_lock:
            if self.current_response and data:
                text = str(data).strip()
                if text:
                    self.current_response.append(text)

    def handle_agent_event(self, event: str, data: Any = None):
        """Centralized event handler"""
        match event:
            case "task_complete":
                if isinstance(data, str):
                    self.app.call_from_thread(self.finalize_response, data)
            case "task_think_start":
                self.app.call_from_thread(self.toggle_loading, True)
                self.app.call_from_thread(
                    self.add_system_message, 
                    "🤔 Thinking..."
                )
            case "tool_execution_start":
                tool = data.get("tool_name", "unknown") if isinstance(data, dict) else "unknown"
                self.app.call_from_thread(
                    self.add_system_message,
                    f"🔧 Using tool: {tool}"
                )
            case "error_max_iterations_reached":
                self.app.call_from_thread(
                    self.add_error_message,
                    "⚠️ Max iterations reached"
                )

    async def finalize_response(self, final_answer: str):
        """Handle final response cleanup"""
        with self._response_lock:
            if not self.current_response:
                return

            try:
                await self.add_system_message("✅ Task complete!")
                chat_view = self.query_one("#chat-view")

                # Create final response box
                final_response = Response()
                await chat_view.mount(final_response)
                await final_response.update(f"**Answer:**\n{final_answer}")
                
                # Remove streaming widget safely
                if self.current_response in chat_view.children:
                    self.current_response.remove()
                self.current_response = None

            except Exception as e:
                logger.error(f"Finalization error: {e}")
            finally:
                await self.toggle_input(True)
                await self.toggle_loading(False)

    async def on_input_submitted(self, event: Input.Submitted):
        """Handle user query submission"""
        query = event.value.strip()
        if not query:
            return

        event.input.value = ""
        await self.toggle_input(False)
        await self.toggle_loading(True)

        chat_view = self.query_one("#chat-view")
        await chat_view.mount(Prompt(query))

        with self._response_lock:
            # Clear previous response if exists
            if self.current_response:
                self.current_response.remove()
                
            # Create new streaming response
            self.current_response = Response()
            await chat_view.mount(self.current_response)
            self.current_response.reset_stream_state()

        # Start processing in background thread
        def process_query():
            try:
                # Synchronous call with streaming enabled
                result = self.agent.solve_task(query, streaming=True)
                if result:
                    self.app.call_from_thread(
                        self.add_system_message,
                        f"**Final Answer:**\n{result}"
                    )
            except Exception as e:
                self.app.call_from_thread(
                    self.add_error_message,
                    f"⚠️ Error: {str(e)}"
                )
            finally:
                self.app.call_from_thread(self.toggle_input, True)
                self.app.call_from_thread(self.toggle_loading, False)

        threading.Thread(target=process_query, daemon=True).start()

    async def toggle_input(self, enabled: bool):
        input_field = self.query_one(Input)
        input_field.disabled = not enabled

    async def toggle_loading(self, visible: bool):
        loading = self.query_one(LoadingIndicator)
        loading.set_class(visible, "visible")

    async def add_system_message(self, text: str):
        chat_view = self.query_one("#chat-view")
        await chat_view.mount(SystemMessage(text))
        chat_view.scroll_end(animate=False)

    async def add_error_message(self, text: str):
        chat_view = self.query_one("#chat-view")
        await chat_view.mount(ErrorMessage(text))
        chat_view.scroll_end(animate=False)

    def on_unmount(self):
        if hasattr(self.agent, "shutdown"):
            self.agent.shutdown()


if __name__ == "__main__":
    ChatApp().run()