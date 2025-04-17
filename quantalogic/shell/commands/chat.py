from typing import List

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from quantalogic.codeact.events import StreamTokenEvent

console = Console()

async def chat_command(shell, args: List[str]) -> str:
    """Handle the /chat command with conversation history and streaming."""
    if not args:
        return "Please provide a message to chat with the agent."
    
    message = " ".join(args)
    try:
        if shell.state.streaming:
            buffer = ""
            markdown = Markdown(buffer)
            with Live(markdown, console=console, refresh_per_second=4) as live:
                def stream_observer(event):
                    nonlocal buffer
                    if isinstance(event, StreamTokenEvent):
                        buffer += event.token
                        markdown.text = buffer
                        live.update(markdown)
                
                shell.current_agent.add_observer(stream_observer, ["StreamToken"])
                response = await shell.current_agent.chat(
                    message,
                    history=shell.current_message_history,
                    streaming=True
                )
                shell.current_agent._observers = [obs for obs in shell.current_agent._observers if obs[0] != stream_observer]
            # Append to history after streaming completes
            shell.current_message_history.append({"role": "user", "content": message})
            shell.current_message_history.append({"role": "assistant", "content": response})
            return response
        else:
            response = await shell.current_agent.chat(
                message,
                history=shell.current_message_history,
                streaming=False
            )
            shell.current_message_history.append({"role": "user", "content": message})
            shell.current_message_history.append({"role": "assistant", "content": response})
            console.print(Panel(Markdown(response), title="Chat Response", border_style="blue"))
            return response
    except Exception as e:
        return f"Error in chat: {e}"