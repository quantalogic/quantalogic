"""Solve command implementation."""
from typing import List

async def solve_command(shell, args: List[str]) -> str:
    """Handle the /solve command."""
    if not args:
        return "Please provide a task to solve."
    
    task = " ".join(args)
    shell.message_history.append({"role": "user", "content": task})
    
    try:
        result = await shell.agent.solve(task)
        final_answer = shell._extract_final_answer(result)
        shell.message_history.append({"role": "assistant", "content": final_answer})
        return final_answer
    except Exception as e:
        return f"Error solving task: {e}"
