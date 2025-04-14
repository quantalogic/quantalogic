"""Solve command implementation."""
from typing import List


async def solve_command(shell, args: List[str]) -> str:
    """Handle the /solve command."""
    if not args:
        return "Please provide a task to solve."
    
    task = " ".join(args)
    shell.message_history.append({"role": "user", "content": task})
    
    try:
        history = await shell.agent.solve(task, streaming=shell.streaming)
        if history:
            final_answer = shell.agent._extract_response(history)
        else:
            final_answer = "No steps were executed."
        shell.message_history.append({"role": "assistant", "content": final_answer})
        return final_answer
    except Exception as e:
        return f"Error solving task: {e}"