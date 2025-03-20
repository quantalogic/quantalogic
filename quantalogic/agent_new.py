import ast
import asyncio
from functools import partial
from pathlib import Path
from typing import Callable, Dict, List

import typer
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from quantalogic.python_interpreter import execute_async
from quantalogic.tools.action_gen import AddTool, AgentTool, ConcatTool, MultiplyTool, generate_program
from quantalogic.tools.tool import Tool, create_tool

# Constants
TEMPLATE_DIR = Path(__file__).parent / "prompts"
LOG_FILE = "react_agent.log"
DEFAULT_MODEL = "gemini/gemini-2.0-flash"
MAX_TOKENS = 4000

# Logger setup
logger.add(LOG_FILE, rotation="10 MB", level="DEBUG")

# Typer app
app = typer.Typer(no_args_is_help=True)

# Jinja2 environment
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)





class ReActAgent:
    def __init__(self, model: str, tools: List[Tool], max_iterations: int = 5):
        self.model = model
        self.tools = tools
        self.max_iterations = max_iterations
        self.tool_namespace: Dict[str, Callable] = self._build_tool_namespace()

    def _build_tool_namespace(self) -> Dict[str, Callable]:
        """Build namespace with tool instances."""
        namespace = {"asyncio": asyncio}
        for tool in self.tools:
            namespace[tool.name] = partial(tool.async_execute)
        return namespace

    async def generate_action(self, task: str, history: List[Dict[str, str]]) -> str:
        """Generate a Python program as an action."""
        logger.info(f"Generating action for task: {task}")
        history_str = self._format_history(history)

        try:
            task_prompt = jinja_env.get_template("action_code/generate_action.j2").render(
                task=task, history_str=history_str
            )
            program = await generate_program(
                task_description=task_prompt,
                tools=self.tools,
                model=self.model,
                max_tokens=MAX_TOKENS,
            )
            logger.debug(f"Generated program:\n{program}")
            return jinja_env.get_template("action_code/response_format.j2").render(
                task=task, history_str=history_str, program=program
            )
        except Exception as e:
            logger.error(f"Action generation failed: {e}")
            return jinja_env.get_template("action_code/error_format.j2").render(error=str(e))

    async def execute_action(self, code: str) -> str:
        """Execute the generated code and return formatted result."""
        logger.debug(f"Executing action:\n{code}")
        
        if not self._validate_code(code):
            return "Error: Generated code lacks an async main() function"

        try:
            result = await execute_async(
                code=code,
                timeout=30,
                entry_point="main",
                allowed_modules=["asyncio"],
                namespace=self.tool_namespace,
            )
            return self._format_execution_result(result)
        except SyntaxError as e:
            logger.error(f"Syntax error: {e}")
            return f"Syntax error: {e}"
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return f"Execution error: {e}"

    def _validate_code(self, code: str) -> bool:
        """Validate that code has an async main function."""
        try:
            tree = ast.parse(code)
            return any(isinstance(node, ast.AsyncFunctionDef) and node.name == "main" for node in ast.walk(tree))
        except SyntaxError as e:
            logger.error(f"Code validation failed: {e}")
            return False

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Format history into a readable string."""
        return "\n".join(
            f"[Step {i+1}] {h['thought']}\nAction:\n{h['action']}\nResult: {h['result']}"
            for i, h in enumerate(history)
        ) if history else "No previous steps"

    def _format_execution_result(self, result) -> str:
        """Format execution result as XML with CDATA, including completion status."""
        if result.error:
            logger.error(f"Execution failed: {result.error}")
            return f"Error: {result.error}"

        result_value = result.result
        completed = isinstance(result_value, str) and result_value.startswith("Task completed:")
        final_answer = result_value[len("Task completed: "):].strip() if completed else None

        xml = [f"<ExecutionResult>\n  <ExecutionTime>{result.execution_time:.2f} seconds</ExecutionTime>"]
        if completed:
            xml.append(f"  <Completed>true</Completed>")
            xml.append(f"  <FinalAnswer><![CDATA[\n{final_answer}\n  ]]></FinalAnswer>")
        else:
            xml.append(f"  <Completed>false</Completed>")
            if result_value is not None:
                xml.append(f"  <Result><![CDATA[\n{str(result_value)}\n  ]]></Result>")

        non_callable_vars = {
            k: (v[:5000] + "... (truncated)" if isinstance(v, str) and len(v) > 5000 else v)
            for k, v in (result.local_variables or {}).items()
            if not callable(v) and not k.startswith("__")
        }
        if non_callable_vars:
            xml.append("  <LocalVariables>")
            for k, v in non_callable_vars.items():
                xml.append(f"    <Variable name=\"{k}\">\n      <![CDATA[\n{v}\n      ]]>\n    </Variable>")
            xml.append("  </LocalVariables>")
        xml.append("</ExecutionResult>")

        formatted_result = "\n".join(xml)
        logger.debug(f"Execution result: {formatted_result[:100]}..." if len(formatted_result) > 100 else formatted_result)
        return formatted_result

    async def solve(self, task: str) -> List[Dict[str, str]]:
        """Solve the task iteratively with explicit stopping criteria."""
        history = []
        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1} for task: {task}")
            response = await self.generate_action(task, history)
            
            try:
                thought, code = self._parse_response(response)
                result = await self.execute_action(code)
                history.append({"thought": thought, "action": code, "result": result})
                if "<Completed>true</Completed>" in result:
                    logger.info(f"Task solved after {iteration + 1} iterations")
                    break
            except ValueError as e:
                logger.error(f"Response parsing failed: {e}")
                break
        return history

    def _parse_response(self, response: str) -> tuple[str, str]:
        """Parse thought and code from response."""
        thought_start = response.index("[Thought]") + 9
        action_start = response.index("[Action]") + 8
        code_start = response.index("```python") + 9
        code_end = response.index("```", code_start)
        return (
            response[thought_start:action_start-8].strip(),
            response[code_start:code_end].strip(),
        )


async def run_react_agent(task: str, model: str, max_iterations: int) -> None:
    """Run the ReAct agent and present the final answer clearly."""
    tools = [AddTool(), MultiplyTool(), ConcatTool(), AgentTool(model=model)]
    agent = ReActAgent(model=model, tools=tools, max_iterations=max_iterations)
    
    typer.echo(typer.style(f"Solving task: {task}", fg=typer.colors.GREEN, bold=True))
    history = await agent.solve(task)
    for i, step in enumerate(history, 1):
        typer.echo(f"\n{typer.style(f'Step {i}', fg=typer.colors.BLUE, bold=True)}")
        for key, color in [("thought", typer.colors.YELLOW), ("action", typer.colors.YELLOW), ("result", typer.colors.YELLOW)]:
            typer.echo(typer.style(f"[{key.capitalize()}]", fg=color))
            typer.echo(step[key])
    
    # Present the final answer if the task was completed
    if history and "<Completed>true</Completed>" in history[-1]["result"]:
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
) -> None:
    """Solve a task using a ReAct Agent."""
    try:
        asyncio.run(run_react_agent(task, model, max_iterations))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()