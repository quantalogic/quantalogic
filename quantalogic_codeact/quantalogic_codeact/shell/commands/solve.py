from typing import List

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

from ...codeact.events import ActionExecutedEvent, ErrorOccurredEvent, StreamTokenEvent, TaskCompletedEvent
from ...codeact.xml_utils import XMLResultHandler
from ..utils import display_response  # New import

console = Console()

async def solve_command(shell, args: List[str]) -> str:
    """Handle the /solve command with streaming and intermediate steps display."""
    if not args:
        return "Please provide a task to solve. For example: /solve Calculate the integral of x^2 from 0 to 1."
    
    task = " ".join(args)
    try:
        if shell.state.streaming:
            step_buffers = {}
            final_answer = None
            
            def stream_observer(event):
                nonlocal final_answer
                if isinstance(event, StreamTokenEvent):
                    step = event.step_number or 1
                    if step not in step_buffers:
                        step_buffers[step] = ""
                    step_buffers[step] += event.token
                    # Process buffer for complete lines
                    lines = step_buffers[step].split('\n')
                    for line in lines[:-1]:
                        console.print(f"[cyan]Step {step}:[/cyan] {line}")
                    step_buffers[step] = lines[-1]
                elif isinstance(event, ActionExecutedEvent):
                    # Format the execution result to XML then summarize
                    xml_str = XMLResultHandler.format_execution_result(event.result)
                    summary = XMLResultHandler.format_result_summary(xml_str)
                    if "<Status>Error</Status>" in xml_str:
                        console.print(Panel(summary, title=f"Step {event.step_number} Error", border_style="red"))
                    else:
                        console.print(Panel(summary, title=f"Step {event.step_number} Result", border_style="magenta"))
                elif isinstance(event, TaskCompletedEvent):
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
                history=shell.history_manager.get_history(),
                streaming=True
            )
            shell.current_agent._observers = [obs for obs in shell.current_agent._observers if obs[0] != stream_observer]
            # Append to history
            shell.history_manager.add_message("user", task)
            shell.history_manager.add_message("assistant", final_answer or "No final answer.")
            return None  # Changed to prevent redundant printing in streaming mode
        else:
            history = await shell.current_agent.solve(
                task,
                history=shell.history_manager.get_history(),
                streaming=False
            )
            if history:
                for step in history:
                    thought = step.get('thought', '')
                    action = step.get('action', '')
                    result = step.get('result', '')
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
                # extract XML value or use raw
                if isinstance(raw, str) and raw.strip().startswith("<"):
                    final_answer = XMLResultHandler.extract_result_value(raw)
                else:
                    final_answer = raw
                if final_answer.startswith("Error:"):
                    display_response(final_answer, title="Error", border_style="red", is_error=True)
                else:
                    display_response(final_answer, title="Final Answer", border_style="green")
                shell.history_manager.add_message("user", task)
                shell.history_manager.add_message("assistant", final_answer)
                return final_answer
            else:
                return "No steps were executed."
    except Exception as e:
        display_response(f"Error solving task: {e}", title="Error", border_style="red", is_error=True)
        return f"Error solving task: {e}"