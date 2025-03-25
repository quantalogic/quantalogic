import ast
import asyncio
from asyncio import TimeoutError
from contextlib import AsyncExitStack
from functools import partial
from typing import Callable, Dict, List

import litellm
import typer
from loguru import logger

from quantalogic.python_interpreter import execute_async
from quantalogic.tools.tool import Tool, ToolArgument

# Configure loguru to log to a file with rotation, matching original
logger.add("action_gen.log", rotation="10 MB", level="DEBUG")

# Initialize Typer app, unchanged
app = typer.Typer()

# Define tool classes with logging in async_execute, preserving original structure
class AddTool(Tool):
    def __init__(self):
        super().__init__(
            name="add_tool",
            description="Adds two numbers and returns the sum.",
            arguments=[
                ToolArgument(name="a", arg_type="int", description="First number", required=True),
                ToolArgument(name="b", arg_type="int", description="Second number", required=True)
            ],
            return_type="int"
        )
    
    async def async_execute(self, **kwargs) -> str:
        logger.info(f"Starting tool execution: {self.name}")
        logger.info(f"Adding {kwargs['a']} and {kwargs['b']}")
        result = str(int(kwargs["a"]) + int(kwargs["b"]))
        logger.info(f"Finished tool execution: {self.name}")
        return result

class MultiplyTool(Tool):
    def __init__(self):
        super().__init__(
            name="multiply_tool",
            description="Multiplies two numbers and returns the product.",
            arguments=[
                ToolArgument(name="x", arg_type="int", description="First number", required=True),
                ToolArgument(name="y", arg_type="int", description="Second number", required=True)
            ],
            return_type="int"
        )
    
    async def async_execute(self, **kwargs) -> str:
        logger.info(f"Starting tool execution: {self.name}")
        logger.info(f"Multiplying {kwargs['x']} and {kwargs['y']}")
        result = str(int(kwargs["x"]) * int(kwargs["y"]))
        logger.info(f"Finished tool execution: {self.name}")
        return result

class ConcatTool(Tool):
    def __init__(self):
        super().__init__(
            name="concat_tool",
            description="Concatenates two strings.",
            arguments=[
                ToolArgument(name="s1", arg_type="string", description="First string", required=True),
                ToolArgument(name="s2", arg_type="string", description="Second string", required=True)
            ],
            return_type="string"
        )
    
    async def async_execute(self, **kwargs) -> str:
        logger.info(f"Starting tool execution: {self.name}")
        logger.info(f"Concatenating '{kwargs['s1']}' and '{kwargs['s2']}'")
        result = kwargs["s1"] + kwargs["s2"]
        logger.info(f"Finished tool execution: {self.name}")
        return result

class AgentTool(Tool):
    def __init__(self, model: str = "gemini/gemini-2.0-flash"):
        super().__init__(
            name="agent_tool",
            description="Generates text using a language model based on a system prompt and user prompt.",
            arguments=[
                ToolArgument(name="system_prompt", arg_type="string", description="System prompt to guide the model's behavior", required=True),
                ToolArgument(name="prompt", arg_type="string", description="User prompt to generate a response for", required=True),
                ToolArgument(name="temperature", arg_type="float", description="Temperature for generation (0 to 1)", required=True)
            ],
            return_type="string"
        )
        self.model = model
    
    async def async_execute(self, **kwargs) -> str:
        logger.info(f"Starting tool execution: {self.name}")
        system_prompt = kwargs["system_prompt"]
        prompt = kwargs["prompt"]
        temperature = float(kwargs["temperature"])
        
        # Validate temperature, unchanged
        if not 0 <= temperature <= 1:
            logger.error(f"Temperature {temperature} is out of range (0-1)")
            raise ValueError("Temperature must be between 0 and 1")
        
        logger.info(f"Generating text with model {self.model}, temperature {temperature}")
        try:
            async with AsyncExitStack() as stack:
                timeout_cm = asyncio.timeout(30)
                await stack.enter_async_context(timeout_cm)
                
                logger.debug(f"Making API call to {self.model}")
                response = await litellm.acompletion(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    max_tokens=1000  # Original default
                )
                generated_text = response.choices[0].message.content.strip()
                logger.debug(f"Generated text: {generated_text}")
                result = generated_text
                logger.info(f"Finished tool execution: {self.name}")
                return result
        except TimeoutError as e:
            error_msg = f"API call to {self.model} timed out after 30 seconds"
            logger.error(error_msg)
            raise TimeoutError(error_msg) from e
        except Exception as e:
            logger.error(f"Failed to generate text with {self.model}: {str(e)}")
            raise RuntimeError(f"Text generation failed: {str(e)}")

# Asynchronous function to generate the program, matching original behavior with updated prompt
async def generate_program(task_description: str, tools: List[Tool], model: str, max_tokens: int) -> str:
    """
    Asynchronously generate a Python program that solves a given task using a list of tools.

    Args:
        task_description (str): A description of the task to be solved.
        tools (List[Tool]): A list of Tool objects available for use.
        model (str): The litellm model to use for code generation.
        max_tokens (int): Maximum number of tokens for the generated response.

    Returns:
        str: A string containing a complete Python program.
    """
    logger.debug(f"Generating program for task: {task_description}")
    tool_docstrings = "\n\n".join([tool.to_docstring() for tool in tools])

    # Updated prompt with reinforced instruction to exclude __main__ block
    prompt = f"""
You are a Python code generator. Your task is to create a Python program that solves the following task:
"{task_description}"

You have access to the following pre-defined async tool functions, as defined with their signatures and descriptions:

{tool_docstrings}

Instructions:
1. Generate a Python program as a single string.
2. Include only the import for asyncio (import asyncio).
3. Define an async function named main() that solves the task.
4. Use the pre-defined tool functions (e.g., add_tool, multiply_tool, concat_tool) directly by calling them with await and the appropriate arguments as specified in their descriptions.
5. Do not redefine the tool functions within the program; assume they are already available in the namespace.
6. Return the program as markdown code block.
7. Strictly exclude asyncio.run(main()) or any code outside the main() function definition, including any 'if __name__ == "__main__":' block, as the runtime will handle execution of main().
8. Do not include explanatory text outside the program string.
9. Express all string variables as multiline strings
string, always start a string at the beginning of a line.
10. Always print the result at the end of the program.

Example task: "Add 5 and 7 and print the result"
Example output:
```python
import asyncio

async def main():
    result = await add_tool(a=5, b=7)
    print(result)
```
"""
    
    logger.debug(f"Prompt sent to litellm:\n{prompt}")
    
    try:
        logger.debug(f"Calling litellm with model {model}")
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": "You are a Python code generator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3
        )
        generated_code = response.choices[0].message.content.strip()
        logger.debug("Code generation successful")
    except Exception as e:
        logger.error(f"Failed to generate code: {str(e)}")
        raise typer.BadParameter(f"Failed to generate code with model '{model}': {str(e)}")

    # Clean up output, preserving original logic
    if generated_code.startswith('"""') and generated_code.endswith('"""'):
        generated_code = generated_code[3:-3]
    elif generated_code.startswith("```python") and generated_code.endswith("```"):
        generated_code = generated_code[9:-3].strip()
    
    # Post-processing to remove any __main__ block if generated despite instructions
    if "if __name__ == \"__main__\":" in generated_code:
        lines = generated_code.splitlines()
        main_end_idx = next(
            (i for i in range(len(lines)) if "if __name__" in lines[i]),
            len(lines)
        )
        generated_code = "\n".join(lines[:main_end_idx]).strip()
        logger.warning("Removed unexpected __main__ block from generated code")

    return generated_code

# Updated async core logic with improved interpreter usage
async def generate_core(task: str, model: str, max_tokens: int) -> None:
    """
    Core logic to generate and execute a Python program based on a task description.

    Args:
        task (str): The task description to generate a program for.
        model (str): The litellm model to use for generation.
        max_tokens (int): Maximum number of tokens for the generated response.
    """
    logger.info(f"Starting generate command for task: {task}")
    # Input validation, unchanged
    if not task.strip():
        logger.error("Task description is empty")
        raise typer.BadParameter("Task description cannot be empty")
    if max_tokens <= 0:
        logger.error("max-tokens must be positive")
        raise typer.BadParameter("max-tokens must be a positive integer")

    # Initialize tools, unchanged
    tools = [
        AddTool(),
        MultiplyTool(),
        ConcatTool(),
        AgentTool(model=model)
    ]

    # Generate the program
    try:
        program = await generate_program(task, tools, model, max_tokens)
    except Exception as e:
        logger.error(f"Failed to generate program: {str(e)}")
        typer.echo(typer.style(f"Error: {str(e)}", fg=typer.colors.RED))
        raise typer.Exit(code=1)

    logger.debug(f"Generated program:\n{program}")
    # Output the generated program with original style
    typer.echo(typer.style("Generated Python Program:", fg=typer.colors.GREEN, bold=True))
    typer.echo(program)
    
    # Validate program structure
    try:
        ast_tree = ast.parse(program)
        has_async_main = any(
            isinstance(node, ast.AsyncFunctionDef) and node.name == "main"
            for node in ast.walk(ast_tree)
        )
        if not has_async_main:
            logger.warning("Generated code lacks an async main() function")
            typer.echo(typer.style("Warning: Generated code lacks an async main() function", fg=typer.colors.YELLOW))
            return
    except SyntaxError as e:
        logger.error(f"Syntax error in generated code: {str(e)}")
        typer.echo(typer.style(f"Syntax error in generated code: {str(e)}", fg=typer.colors.RED))
        return

    # Prepare namespace with tool instances
    namespace: Dict[str, Callable] = {
        "asyncio": asyncio,
        "add_tool": partial(AddTool().async_execute),
        "multiply_tool": partial(MultiplyTool().async_execute),
        "concat_tool": partial(ConcatTool().async_execute),
        "agent_tool": partial(AgentTool(model=model).async_execute),
    }

    # Check for namespace collisions
    reserved_names = set(vars(__builtins__))
    for name in namespace:
        if name in reserved_names and name != "asyncio":
            logger.warning(f"Namespace collision detected: '{name}' shadows a builtin")
            typer.echo(typer.style(f"Warning: Tool name '{name}' shadows a builtin", fg=typer.colors.YELLOW))

    # Execute the program
    typer.echo("\n" + typer.style("Executing the program:", fg=typer.colors.GREEN, bold=True))
    try:
        logger.debug("Executing generated code with execute_async")
        execution_result = await execute_async(
            code=program,
            timeout=30,
            entry_point="main",
            allowed_modules=["asyncio"],
            namespace=namespace,
        )
        
        # Detailed error handling
        if execution_result.error:
            if "SyntaxError" in execution_result.error:
                logger.error(f"Syntax error: {execution_result.error}")
                typer.echo(typer.style(f"Syntax error: {execution_result.error}", fg=typer.colors.RED))
            elif "TimeoutError" in execution_result.error:
                logger.error(f"Timeout: {execution_result.error}")
                typer.echo(typer.style(f"Timeout: {execution_result.error}", fg=typer.colors.RED))
            else:
                logger.error(f"Runtime error: {execution_result.error}")
                typer.echo(typer.style(f"Runtime error: {execution_result.error}", fg=typer.colors.RED))
        else:
            logger.info(f"Execution completed in {execution_result.execution_time:.2f} seconds")
            typer.echo(typer.style(f"Execution completed in {execution_result.execution_time:.2f} seconds", fg=typer.colors.GREEN))
            
            # Display the result if it's not None
            if execution_result.result is not None:
                typer.echo("\n" + typer.style("Result:", fg=typer.colors.BLUE, bold=True))
                typer.echo(str(execution_result.result))
    except ValueError as e:
        logger.error(f"Invalid code generated: {str(e)}")
        typer.echo(typer.style(f"Invalid code: {str(e)}", fg=typer.colors.RED))
    except Exception as e:
        logger.error(f"Unexpected execution error: {str(e)}")
        typer.echo(typer.style(f"Unexpected error during execution: {str(e)}", fg=typer.colors.RED))
    else:
        logger.info("Program executed successfully")

@app.command()
def generate(
    task: str = typer.Argument(
        ...,
        help="The task description to generate a program for (e.g., 'Add 5 and 7 and print the result')"
    ),
    model: str = typer.Option(
        "gemini/gemini-2.0-flash",
        "--model",
        "-m",
        help="The litellm model to use for generation (e.g., 'gpt-3.5-turbo', 'gpt-4')"
    ),
    max_tokens: int = typer.Option(
        4000,
        "--max-tokens",
        "-t",
        help="Maximum number of tokens for the generated response (default: 4000)"
    )
) -> None:
    """Generate and execute a Python program based on a task description"""
    try:
        # Run async core logic, preserving original execution style
        asyncio.run(generate_core(task, model, max_tokens))
    except Exception as e:
        logger.error(f"Command failed: {str(e)}")
        typer.echo(typer.style(f"Error: {str(e)}", fg=typer.colors.RED))
        raise typer.Exit(code=1)

# Entry point, unchanged
def main() -> None:
    logger.debug("Starting script execution")
    app()

if __name__ == "__main__":
    main()
