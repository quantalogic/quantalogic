from typing import List

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from ...codeact.events import StreamTokenEvent
from ..utils import display_response  # New import

console = Console()

async def chat_command(shell, args: List[str]) -> str:
    """Handle the /chat command with conversation history and streaming, displaying errors in a panel."""
    if not args:
        return "Please provide a message to chat with the agent. For example: /chat Hello, how are you?"
    
    message = " ".join(args)
    try:
        if shell.state.streaming:
            first_token_received = False
            status = console.status("Waiting for first token...", spinner="dots")
            status.start()
            buffer = ""
            live = None

            def stream_observer(event):
                nonlocal buffer, first_token_received, live
                if isinstance(event, StreamTokenEvent) and event.event_type == "StreamToken":
                    if not first_token_received:
                        first_token_received = True
                        status.stop()
                        live = Live(Markdown(buffer), console=console, refresh_per_second=4)
                        live.start()
                    buffer += event.token
                    live.update(Markdown(buffer))
                elif isinstance(event, StreamTokenEvent) and event.event_type == "StreamError":
                    if not first_token_received:
                        first_token_received = True
                        status.stop()
                        display_response(event.token, title="Error", border_style="red", is_error=True)
                        return
                    live.update(Panel(event.token, title="Error", border_style="red"))

            shell.current_agent.add_observer(stream_observer, ["StreamToken", "StreamError"])
            response = await shell.current_agent.chat(
                message,
                history=shell.conversation_manager.get_history(),
                streaming=True
            )
            shell.current_agent.remove_observer(stream_observer)
            shell.conversation_manager.add_message("user", message)
            if not response.startswith("Error:"):
                shell.conversation_manager.add_message("assistant", response)
            if live:
                live.stop()
            elif not first_token_received:
                status.stop()
            if response.startswith("Error:"):
                display_response(response, title="Error", border_style="red", is_error=True)
            else:
                display_response(response, title="Final Answer", border_style="green")
            return None
        else:
            status = console.status("Processing...", spinner="dots")
            status.start()
            response = await shell.current_agent.chat(
                message,
                history=shell.conversation_manager.get_history(),
                streaming=False
            )
            status.stop()
            shell.conversation_manager.add_message("user", message)
            if response.startswith("Error:"):
                display_response(response, title="Error", border_style="red", is_error=True)
            else:
                shell.conversation_manager.add_message("assistant", response)
                display_response(response, title="Final Answer", border_style="green")
            return None
    except Exception as e:
        error_message = f"Error in chat: {e}"
        display_response(error_message, title="Error", border_style="red", is_error=True)
        return None