import ast
import asyncio
import os
from functools import partial
from typing import Dict, List

import jinja2
import typer
from loguru import logger

from quantalogic.python_interpreter import execute_async
from quantalogic.tools.action_gen import AddTool, AgentTool, ConcatTool, MultiplyTool, generate_program
from quantalogic.tools.tool import Tool

logger.add("react_agent.log", rotation="10 MB", level="DEBUG")
app = typer.Typer()

# Set up Jinja2 environment
template_dir = os.path.join(os.path.dirname(__file__), "prompts")
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir),
    trim_blocks=True,
    lstrip_blocks=True
)

class ReActAgent:
    def __init__(self, model: str, tools: List[Tool], max_iterations: int = 5):
        self.model = model
        self.tools = tools
        self.max_iterations = max_iterations
        
        # Prepare namespace with tool instances as in action_gen.py
        self.tool_namespace: Dict[str, callable] = {"asyncio": asyncio}
        for tool in self.tools:
            self.tool_namespace[tool.name] = partial(tool.async_execute)

    async def generate_action(self, task: str, history: List[Dict[str, str]]) -> str:
        """Generate a Python program as an action using the generate_program function from action_gen.py."""
        logger.info(f"Generating action for task: {task}")
        
        # Construct history string for context
        history_str = "\n".join([f"[Step {i+1}] {h['thought']}\nAction:\n{h['action']}\nResult: {h['result']}" 
                               for i, h in enumerate(history)]) if history else "No previous steps"
        
        # Modify task description to include history and fit action_gen.py's expectations
        enhanced_task = f"""
Solve the following task: '{task}'
Previous steps:
{history_str}
Generate a Python program with an async main() function that uses the available tools to take the next step toward solving the task.
If previous steps indicate the task is solved, return the final result.
Always print the result at the end of the program.
"""
        
        # Use generate_program from action_gen.py
        try:
            program = await generate_program(
                task_description=enhanced_task,
                tools=self.tools,
                model=self.model,
                max_tokens=4000  # Match action_gen.py default
            )
            logger.debug(f"Generated program:\n{program}")
            
            # Format response to match ReActAgent's expected output
            response = f"""
[Thought]
Generated a Python program to take the next step toward solving: {task}
Based on history: {history_str}

[Action]
```python
{program}
```
"""
            return response
        except Exception as e:
            logger.error(f"Failed to generate action: {str(e)}")
            return f"""
[Thought]
Failed to generate a valid action due to: {str(e)}

[Action]
```python
import asyncio
async def main():
    print("Error: Action generation failed")
```
"""

    async def execute_action(self, code: str) -> str:
        """Execute the generated code using the logic from action_gen.py's generate_core."""
        logger.debug(f"Executing action:\n{code}")
        
        # Validate program structure as in action_gen.py
        try:
            ast_tree = ast.parse(code)
            has_async_main = any(
                isinstance(node, ast.AsyncFunctionDef) and node.name == "main"
                for node in ast.walk(ast_tree)
            )
            if not has_async_main:
                logger.warning("Generated code lacks an async main() function")
                return "Error: Generated code lacks an async main() function"
        except SyntaxError as e:
            logger.error(f"Syntax error in generated code: {str(e)}")
            return f"Syntax error: {str(e)}"

        # Execute the program as in action_gen.py
        try:
            execution_result = await execute_async(
                code=code,
                timeout=30,
                entry_point="main",
                allowed_modules=["asyncio"],
                namespace=self.tool_namespace,
            )
            
            # Detailed error handling as in action_gen.py
            if execution_result.error:
                if "SyntaxError" in execution_result.error:
                    logger.error(f"Syntax error: {execution_result.error}")
                    return f"Syntax error: {execution_result.error}"
                elif "TimeoutError" in execution_result.error:
                    logger.error(f"Timeout: {execution_result.error}")
                    return f"Timeout: {execution_result.error}"
                else:
                    logger.error(f"Runtime error: {execution_result.error}")
                    return f"Runtime error: {execution_result.error}"
            else:
                logger.info(f"Execution completed in {execution_result.execution_time:.2f} seconds")
                # Return stdout or result as in action_gen.py
                if execution_result.stdout and execution_result.stdout.strip():
                    return execution_result.stdout.strip()
                elif execution_result.result is not None:
                    return str(execution_result.result)
                else:
                    return "No output"
        except ValueError as e:
            logger.error(f"Invalid code generated: {str(e)}")
            return f"Invalid code: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected execution error: {str(e)}")
            return f"Unexpected error during execution: {str(e)}"

    async def solve(self, task: str) -> List[Dict[str, str]]:
        history = []
        for iteration in range(self.max_iterations):
            logger.info(f"Starting iteration {iteration + 1} for task: {task}")
            
            # Generate reasoning and action
            response = await self.generate_action(task, history)
            logger.debug(f"Generated response:\n{response}")
            
            # Parse response
            try:
                thought_start = response.index("[Thought]") + 9
                action_start = response.index("[Action]") + 8
                thought = response[thought_start:action_start-8].strip()
                
                code_start = response.index("```python") + 9
                code_end = response.index("```", code_start)
                code = response[code_start:code_end].strip()
            except ValueError:
                logger.error("Invalid response format")
                break

            # Execute the action
            result = await self.execute_action(code)
            
            # Store step
            step = {
                "thought": thought,
                "action": code,
                "result": result
            }
            history.append(step)
            
            # Check if task appears solved (simplified condition)
            if "Error" not in result and result.strip() and result != "No output":
                logger.info(f"Task appears solved after {iteration + 1} iterations")
                break
                
        return history

async def run_react_agent(task: str, model: str, max_iterations: int) -> None:
    # Initialize tools as in action_gen.py
    tools = [
        AddTool(),
        MultiplyTool(),
        ConcatTool(),
        AgentTool(model=model)
    ]
    agent = ReActAgent(model=model, tools=tools, max_iterations=max_iterations)
    
    typer.echo(typer.style(f"Solving task: {task}", fg=typer.colors.GREEN, bold=True))
    history = await agent.solve(task)
    
    # Display results as in original agent_new.py
    for i, step in enumerate(history, 1):
        typer.echo(f"\n{typer.style(f'Step {i}', fg=typer.colors.BLUE, bold=True)}")
        typer.echo(typer.style("[Thought]", fg=typer.colors.YELLOW))
        typer.echo(step["thought"])
        typer.echo(typer.style("[Action]", fg=typer.colors.YELLOW))
        typer.echo(step["action"])
        typer.echo(typer.style("[Result]", fg=typer.colors.YELLOW))
        typer.echo(step["result"])

@app.command()
def react(
    task: str = typer.Argument(..., help="The task to solve"),
    model: str = typer.Option("gemini/gemini-2.0-flash", "--model", "-m", help="The litellm model to use"),
    max_iterations: int = typer.Option(5, "--max-iterations", "-i", help="Maximum reasoning steps")
) -> None:
    """Solve a task using a ReAct Agent with code generation and execution"""
    try:
        asyncio.run(run_react_agent(task, model, max_iterations))
    except Exception as e:
        logger.error(f"Agent failed: {str(e)}")
        typer.echo(typer.style(f"Error: {str(e)}", fg=typer.colors.RED))
        raise typer.Exit(code=1)

def main() -> None:
    logger.debug("Starting ReAct Agent")
    app()

if __name__ == "__main__":
    main()
