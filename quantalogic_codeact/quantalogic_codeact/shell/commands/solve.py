import json
from typing import List, Optional

from nanoid import generate
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

from ...codeact.events import ActionExecutedEvent, ErrorOccurredEvent, StreamTokenEvent, TaskCompletedEvent
from ...codeact.xml_utils import XMLResultHandler
from ..utils import display_response  # New import

console = Console()

async def solve_command(shell, args: List[str], task_id: Optional[str] = None) -> str:
    """Handle the /solve command with streaming and intermediate steps display."""
    if not args:
        return "Please provide a task to solve. For example: /solve Calculate the integral of x^2 from 0 to 1."
    
    task = " ".join(args)
    # Generate a default task_id if none is provided
    if task_id is None:
        task_id = generate(size=21)
    try:
        if shell.agent_config.streaming:
            step_buffers = {}
            # no block state; uniform Step prefix for all lines
            final_answer = None
            first_token_received = False
            status = console.status("Waiting for first token...", spinner="dots")
            status.start()
            
            def stream_observer(event):
                nonlocal final_answer, first_token_received
                if isinstance(event, StreamTokenEvent):
                    if not first_token_received:
                        first_token_received = True
                        status.stop()
                    step = event.step_number or 1
                    if step not in step_buffers:
                        step_buffers[step] = ""
                    step_buffers[step] += event.token
                    # Process buffer for complete lines uniformly
                    lines = step_buffers[step].split('\n')
                    for line in lines[:-1]:
                        console.print(f"[cyan]Step {step}:[/cyan] {line}")
                    step_buffers[step] = lines[-1]
                elif isinstance(event, ActionExecutedEvent):
                    # Skip display if action was aborted by user confirmation decline
                    try:
                        if getattr(event.result, 'error', None) and 'User declined to execute tool' in event.result.error:
                            return
                    except Exception:
                        pass
                    # Flush any remaining buffers before showing result panel
                    for s, buf in step_buffers.items():
                        if buf:
                            console.print(f"[cyan]Step {s}:[/cyan] {buf}")
                            step_buffers[s] = ""
                    # Format the execution result to XML then summarize
                    xml_str = XMLResultHandler.format_execution_result(event.result)
                    if isinstance(event.result, dict):
                        summary = json.dumps(event.result, indent=2)
                    else:
                        summary = XMLResultHandler.format_result_summary(xml_str)
                    if "<Status>Error</Status>" in xml_str:
                        console.print(Panel(summary, title=f"Step {event.step_number} Error", border_style="red"))
                    else:
                        console.print(Panel(summary, title=f"Step {event.step_number} Result", border_style="magenta"))
                elif isinstance(event, TaskCompletedEvent):
                    # Flush any remaining buffers before finalizing step display
                    for s, buf in step_buffers.items():
                        if buf:
                            console.print(f"[cyan]Step {s}:[/cyan] {buf}")
                            step_buffers[s] = ""
                    if event.final_answer:
                        raw_answer = event.final_answer
                        # if XML, extract value; else use raw
                        if raw_answer.strip().startswith("<"):
                            final_answer = XMLResultHandler.extract_result_value(raw_answer)
                        else:
                            final_answer = raw_answer
                        display_response(final_answer, title="Final Answer", border_style="green")
                    else:
                        display_response("Task did not complete successfully.", title="Error", border_style="red", is_error=True)
                elif isinstance(event, ErrorOccurredEvent):
                    display_response(f"[red]{event.error_message}[/red]", title="Error", border_style="red", is_error=True)
            
            shell.current_agent.add_observer(stream_observer, ["StreamToken", "ActionExecuted", "TaskCompleted", "ErrorOccurred"])
            history = await shell.current_agent.solve(
                task,
                history=shell.conversation_manager.get_history(),
                streaming=True
            )
            status.stop()
            shell.current_agent._observers = [obs for obs in shell.current_agent._observers if obs[0] != stream_observer]
            # Append to history
            shell.conversation_manager.add_message("user", task)
            shell.conversation_manager.add_message("assistant", final_answer or "No final answer.")
            return ""  # Prevent CLI from rendering None panel in streaming mode
        else:
            status = console.status("Processing...", spinner="dots")
            status.start()
            history = await shell.current_agent.solve(
                task,
                history=shell.conversation_manager.get_history(),
                streaming=False
            )
            status.stop()
            if history:
                for step in history:
                    thought = step.get('thought', '')
                    action = step.get('action', '')
                    result = step.get('result', '')
                    if isinstance(result, dict):
                        result_summary = json.dumps(result, indent=2)
                    else:
                        result_summary = XMLResultHandler.format_result_summary(result)
                    if "<Status>Error</Status>" in result:
                        rprint(Panel(
                            f"[cyan]Step {step['step_number']}:[/cyan]\n"
                            f"[yellow]Thought:[/yellow] {thought}\n"
                            f"[yellow]Action:[/yellow] {action}\n"
                            f"[red]Error:[/red] {result_summary}",
                            border_style="red"
                        ))
                    else:
                        rprint(Panel(
                            f"[cyan]Step {step['step_number']}:[/cyan]\n"
                            f"[yellow]Thought:[/yellow] {thought}\n"
                            f"[yellow]Action:[/yellow] {action}\n"
                            f"[blue]Result:[/blue] {result_summary}",
                            border_style="cyan"
                        ))
                raw = history[-1].get("result", "")
                # Handle different result types for final answer
                if isinstance(raw, dict):
                    error_val = raw.get('error')
                    if error_val:
                        final_display = error_val
                        display_response(final_display, title="Error", border_style="red", is_error=True)
                    else:
                        # Use the 'result' field as final answer
                        final_display = raw.get('result', json.dumps(raw, indent=2))
                        display_response(final_display, title="Final Answer", border_style="green")
                elif isinstance(raw, str) and raw.strip().startswith("<"):
                    # Extract value from XML
                    final_display = XMLResultHandler.extract_result_value(raw)
                    display_response(final_display, title="Final Answer", border_style="green")
                elif isinstance(raw, str):
                    final_display = raw
                    if final_display.startswith("Error:"):
                        display_response(final_display, title="Error", border_style="red", is_error=True)
                    else:
                        display_response(final_display, title="Final Answer", border_style="green")
                else:
                    # Fallback to string representation
                    final_display = str(raw)
                    display_response(final_display, title="Final Answer", border_style="green")
                shell.conversation_manager.add_message("user", task)
                shell.conversation_manager.add_message("assistant", final_display)
                return final_display
            else:
                return "No steps were executed."
    except Exception as e:
        display_response(f"Error solving task: {e}", title="Error", border_style="red", is_error=True)
        return f"Error solving task: {e}"