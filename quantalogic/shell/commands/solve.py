from typing import List

from rich import print as rprint
from rich.panel import Panel


async def solve_command(shell, args: List[str]) -> str:
    """Handle the /solve command with intermediate steps display and conversation history."""
    if not args:
        return "Please provide a task to solve."
    
    task = " ".join(args)
    try:
        # Pass the current agent's message_history to the agent for context
        history = await shell.current_agent.solve(
            task,
            history=shell.current_message_history,
            streaming=shell.state.streaming
        )
        if history:
            # Display intermediate steps with color and formatting
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
        # Append task and response to message_history
        shell.current_message_history.append({"role": "user", "content": task})
        shell.current_message_history.append({"role": "assistant", "content": final_answer})
        return final_answer
    except Exception as e:
        return f"Error solving task: {e}"