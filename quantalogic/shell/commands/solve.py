from typing import List

from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from quantalogic.codeact.events import ActionExecutedEvent, StreamTokenEvent, TaskCompletedEvent
from quantalogic.codeact.xml_utils import XMLResultHandler

console = Console()

async def solve_command(shell, args: List[str]) -> str:
    """Handle the /solve command with streaming and intermediate steps display."""
    if not args:
        return "Please provide a task to solve."
    
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
                    console.print(f"[magenta]Step {event.step_number} Result:[/magenta]\n{summary}")
                elif isinstance(event, TaskCompletedEvent):
                    if event.final_answer:
                        final_answer = XMLResultHandler.extract_result_value(event.final_answer)
                        console.print(Panel(Markdown(final_answer), title="Final Answer", border_style="green"))
            
            shell.current_agent.add_observer(stream_observer, ["StreamToken", "ActionExecuted", "TaskCompleted"])
            history = await shell.current_agent.solve(
                task,
                history=shell.current_message_history,
                streaming=True
            )
            shell.current_agent._observers = [obs for obs in shell.current_agent._observers if obs[0] != stream_observer]
            # Append to history
            shell.current_message_history.append({"role": "user", "content": task})
            shell.current_message_history.append({"role": "assistant", "content": final_answer or "No final answer."})
            return None  # Changed to prevent redundant printing in streaming mode
        else:
            history = await shell.current_agent.solve(
                task,
                history=shell.current_message_history,
                streaming=False
            )
            if history:
                for step in history:
                    thought = step.get('thought', '')
                    action = step.get('action', '')
                    result = step.get('result', '')
                    rprint(Panel(
                        f"[cyan]Step {step['step_number']}:[/cyan]\n"
                        f"[yellow]Thought:[/yellow] {thought}\n"
                        f"[yellow]Action:[/yellow] {action}\n"
                        f"[yellow]Result:[/yellow] {result}",
                        border_style="cyan"
                    ))
                final_answer = shell.current_agent._extract_response(history)
            else:
                final_answer = "No steps were executed."
            shell.current_message_history.append({"role": "user", "content": task})
            shell.current_message_history.append({"role": "assistant", "content": final_answer})
            return final_answer
    except Exception as e:
        return f"Error solving task: {e}"