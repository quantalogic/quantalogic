from typing import List

from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ...codeact.events import ActionExecutedEvent, ErrorOccurredEvent, StreamTokenEvent, TaskCompletedEvent
from ...codeact.xml_utils import XMLResultHandler

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
                    summary = XMLResultHandler.format_result_summary(event.result_xml)
                    if "<Status>Error</Status>" in event.result_xml:
                        console.print(Panel(summary, title=f"Step {event.step_number} Error", border_style="red"))
                    else:
                        console.print(Panel(summary, title=f"Step {event.step_number} Result", border_style="magenta"))
                elif isinstance(event, TaskCompletedEvent):
                    if event.final_answer:
                        final_answer = XMLResultHandler.extract_result_value(event.final_answer)
                        console.print(Panel(Markdown(final_answer), title="Final Answer", border_style="green"))
                    else:
                        console.print(Panel("Task did not complete successfully.", title="Error", border_style="red"))
                elif isinstance(event, ErrorOccurredEvent):
                    console.print(Panel(f"[red]{event.error_message}[/red]", title="Error", border_style="red"))
            
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
                final_answer = shell.current_agent._extract_response(history)
                if final_answer.startswith("Error:"):
                    console.print(Panel(final_answer, title="Task Error", border_style="red"))
                else:
                    console.print(Panel(Markdown(final_answer), title="Final Answer", border_style="green"))
                shell.history_manager.add_message("user", task)
                shell.history_manager.add_message("assistant", final_answer)
                return final_answer
            else:
                return "No steps were executed."
    except Exception as e:
        console.print(Panel(f"[red]Error solving task: {e}[/red]", title="Error", border_style="red"))
        return f"Error solving task: {e}"