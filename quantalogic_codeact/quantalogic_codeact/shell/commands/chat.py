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
            buffer = ""
            with Live(Markdown(buffer), console=console, refresh_per_second=4) as live:
                def stream_observer(event):
                    nonlocal buffer
                    if isinstance(event, StreamTokenEvent):
                        if event.event_type == "StreamToken":
                            buffer += event.token
                            live.update(Markdown(buffer))
                        elif event.event_type == "StreamError":
                            error_message = event.token
                            live.update(Panel(error_message, title="Error", border_style="red"))
                
                shell.current_agent.add_observer(stream_observer, ["StreamToken", "StreamError"])
                response = await shell.current_agent.chat(
                    message,
                    history=shell.history_manager.get_history(),
                    streaming=True
                )
                shell.current_agent.remove_observer(stream_observer)
                shell.history_manager.add_message("user", message)
                if not response.startswith("Error:"):
                    shell.history_manager.add_message("assistant", response)
            if response.startswith("Error:"):
                display_response(response, title="Error", border_style="red", is_error=True)
            else:
                display_response(response, title="Final Answer", border_style="green")
            return None  # Output handled by Live display and display_response
        else:
            response = await shell.current_agent.chat(
                message,
                history=shell.history_manager.get_history(),
                streaming=False
            )
            shell.history_manager.add_message("user", message)
            if response.startswith("Error:"):
                display_response(response, title="Error", border_style="red", is_error=True)
            else:
                shell.history_manager.add_message("assistant", response)
                display_response(response, title="Final Answer", border_style="green")
            return None  # Output handled by display_response
    except Exception as e:
        error_message = f"Error in chat: {e}"
        display_response(error_message, title="Error", border_style="red", is_error=True)
        return None