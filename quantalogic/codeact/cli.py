import asyncio
from typing import Callable, List, Optional, Union

import typer
from loguru import logger

from quantalogic.tools import create_tool

from .agent import ReActAgent
from .constants import DEFAULT_MODEL
from .tools_manager import Tool, get_default_tools

app = typer.Typer(no_args_is_help=True)


async def run_react_agent(
    task: str,
    model: str,
    max_iterations: int,
    success_criteria: Optional[str] = None,
    tools: Optional[List[Union[Tool, Callable]]] = None
) -> None:
    tools = tools if tools is not None else get_default_tools(model)
    
    processed_tools = []
    for tool in tools:
        if isinstance(tool, Tool):
            processed_tools.append(tool)
        elif callable(tool):
            processed_tools.append(create_tool(tool))
        else:
            logger.warning(f"Invalid tool type: {type(tool)}. Skipping.")
            typer.echo(typer.style(f"Warning: Invalid tool type {type(tool)} skipped.", fg=typer.colors.YELLOW))

    agent = ReActAgent(model=model, tools=processed_tools, max_iterations=max_iterations)
    
    typer.echo(typer.style(f"Solving task: {task}", fg=typer.colors.GREEN, bold=True))
    history = await agent.solve(task, success_criteria)
    for i, step in enumerate(history, 1):
        typer.echo(f"\n{typer.style(f'Step {i}', fg=typer.colors.BLUE, bold=True)}")
        for key, color in [("thought", typer.colors.YELLOW), ("action", typer.colors.YELLOW), ("result", typer.colors.YELLOW)]:
            typer.echo(typer.style(f"[{key.capitalize()}]", fg=color))
            typer.echo(step[key])
    
    if history and "<FinalAnswer><![CDATA[" in history[-1]["result"]:
        start = history[-1]["result"].index("<FinalAnswer><![CDATA[") + len("<FinalAnswer><![CDATA[")
        end = history[-1]["result"].index("]]></FinalAnswer>", start)
        final_answer = history[-1]["result"][start:end].strip()
        typer.echo(f"\n{typer.style('Final Answer', fg=typer.colors.GREEN, bold=True)}")
        typer.echo(final_answer)
    elif history:
        typer.echo(typer.style("\nTask not completed within the maximum iterations.", fg=typer.colors.RED))


@app.command()
def react(
    task: str = typer.Argument(..., help="The task to solve"),
    model: str = typer.Option(DEFAULT_MODEL, help="The litellm model to use"),
    max_iterations: int = typer.Option(5, help="Maximum reasoning steps"),
    success_criteria: Optional[str] = typer.Option(None, help="Optional criteria to determine task completion"),
) -> None:
    try:
        asyncio.run(run_react_agent(task, model, max_iterations, success_criteria))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()