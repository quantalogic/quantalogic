from typing import List

from rich.console import Console
from rich.panel import Panel

from ...codeact.events import StreamTokenEvent
from ..utils import display_response

console = Console()


async def chat_command(shell, args: List[str]) -> str:
    """Handle the /chat command with streaming and history support."""
    if not args:
        return "Please provide a message to chat. For example: /chat Hello, how are you?"
    
    message = " ".join(args)
    try:
        if shell.agent_config.streaming:
            token_buffer = ""
            first_token_received = False
            status = console.status("Waiting for first token...", spinner="dots")
            status.start()
            
            def stream_observer(event):
                nonlocal token_buffer, first_token_received
                if isinstance(event, StreamTokenEvent):
                    if not first_token_received:
                        first_token_received = True
                        status.stop()
                    token_buffer += event.token
                    # Process buffer for complete lines
                    lines = token_buffer.split('\n')
                    for line in lines[:-1]:
                        console.print(line)
                    token_buffer = lines[-1]
            
            shell.current_agent.add_observer(stream_observer, ["StreamToken"])
            response = await shell.current_agent.chat(
                message,
                history=shell.conversation_manager.get_history(),
                streaming=True
            )
            status.stop()
            shell.current_agent._observers = [obs for obs in shell.current_agent._observers if obs[0] != stream_observer]
            # Flush any remaining buffer
            if token_buffer:
                console.print(token_buffer)
            # Append to history
            shell.conversation_manager.add_message("user", message)
            shell.conversation_manager.add_message("assistant", response)
            return ""  # Prevent CLI from rendering None panel in streaming mode
        else:
            status = console.status("Processing...", spinner="dots")
            status.start()
            response = await shell.current_agent.chat(
                message,
                history=shell.conversation_manager.get_history(),
                streaming=False
            )
            status.stop()
            display_response(response, title="Chat Response", border_style="cyan")
            shell.conversation_manager.add_message("user", message)
            shell.conversation_manager.add_message("assistant", response)
            return response
    except Exception as e:
        display_response(f"Error in chat: {e}", title="Error", border_style="red", is_error=True)
        return f"Error in chat: {e}"