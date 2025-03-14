import asyncio
from typing import List

import litellm
import typer
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.utils.python_interpreter import interpret_code

# Configure loguru to log to a file with rotation
logger.add("action_gen.log", rotation="10 MB", level="DEBUG")

# Initialize Typer app
app = typer.Typer()

# Define tool classes with logging in async_execute
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
        logger.info(f"Adding {kwargs['a']} and {kwargs['b']}")
        return str(int(kwargs["a"]) + int(kwargs["b"]))

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
        logger.info(f"Multiplying {kwargs['x']} and {kwargs['y']}")
        return str(int(kwargs["x"]) * int(kwargs["y"]))

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
        logger.info(f"Concatenating '{kwargs['s1']}' and '{kwargs['s2']}'")
        return kwargs["s1"] + kwargs["s2"]

# Asynchronous function to generate the program
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
    # Collect tool docstrings
    tool_docstrings = "\n\n".join([tool.to_docstring() for tool in tools])

    # Construct the prompt for litellm
    prompt = f"""
You are a Python code generator. Your task is to create a Python program that solves the following task:
"{task_description}"

You have access to the following pre-defined async tool functions, as defined with their signatures and descriptions:

{tool_docstrings}

Instructions:
1. Generate a Python program as a single string enclosed in triple backticks.
2. Include only the import for asyncio (import asyncio).
3. Define an async function named main() that solves the task.
4. Use the pre-defined tool functions (e.g., add_tool, multiply_tool, concat_tool) directly by calling them with await and the appropriate arguments as specified in their descriptions.
5. Do not redefine the tool functions within the program; assume they are already available in the namespace.
6. Return the program as a string enclosed in triple backticks.
7. Do not include asyncio.run(main()) or any code outside the main() function definition.
8. Do not include explanatory text outside the program string.

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
        # Call litellm asynchronously to generate the program
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

    # Robustly clean up the output to ensure only raw Python code remains
    generated_code = generated_code.strip()
    if generated_code.startswith('```python') and generated_code.endswith('```'):
        generated_code = generated_code[9:-3].strip()
    
    return generated_code

# Function to clean unnecessary backticks before execution
def clean_backticks(code: str) -> str:
    return code.replace('```python', '').replace('```', '').strip()

# Async core logic for generate
async def generate_core(task: str, model: str, max_tokens: int):
    logger.info(f"Starting generate command for task: {task}")
    # Input validation
    if not task.strip():
        logger.error("Task description is empty")
        raise typer.BadParameter("Task description cannot be empty")
    if max_tokens <= 0:
        logger.error("max-tokens must be positive")
        raise typer.BadParameter("max-tokens must be a positive integer")

    # Initialize tools
    tools = [AddTool(), MultiplyTool(), ConcatTool()]

    # Generate the program
    try:
        program = await generate_program(task, tools, model, max_tokens)
    except Exception as e:
        logger.error(f"Failed to generate program: {str(e)}")
        typer.echo(typer.style(f"Error: {str(e)}", fg=typer.colors.RED))
        raise typer.Exit(code=1)

    logger.debug(f"Generated program:\n{program}")
    # Output the generated program
    typer.echo(typer.style("Generated Python Program:", fg=typer.colors.GREEN, bold=True))
    typer.echo(program)
    
    # Attempt to execute the program using the safe interpreter
    typer.echo("\n" + typer.style("Executing the program:", fg=typer.colors.GREEN, bold=True))
    try:
        # Create instances of tools
        add_tool_instance = AddTool()
        multiply_tool_instance = MultiplyTool()
        concat_tool_instance = ConcatTool()

        # Ensure the program is a clean string without extra quotes or whitespace
        program = clean_backticks(program)
        
        # Prepare the program by adding necessary wrappers to make it compatible
        # with the safe interpreter and our tool functions
        wrapper_program = f"""
import asyncio

# Create tool function adapters
async def add_tool(a, b):
    return await _add_tool_instance.async_execute(a=a, b=b)

async def multiply_tool(x, y):
    return await _multiply_tool_instance.async_execute(x=x, y=y)

async def concat_tool(s1, s2):
    return await _concat_tool_instance.async_execute(s1=s1, s2=s2)

# The generated program begins here
{program}

# Create a helper to run main
async def _run_main():
    result = await main()
    if result is not None:
        print(result)
        
# Store the result for the interpreter
result = asyncio.run(_run_main())
"""
        
        logger.debug("Executing generated code with safe interpreter")
        
        # Use the safe interpreter with a controlled set of allowed modules
        allowed_modules = ["asyncio"]
        
        # We'll create a simple context manager to set and restore global variables
        class ToolContext:
            def __init__(self, tools):
                self.tools = tools
                self.old_globals = {}
                
            def __enter__(self):
                # No need to modify globals with the safe interpreter approach
                return self
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                # No need to restore globals with the safe interpreter approach
                pass
        
        # Execute in the context of our tools
        with ToolContext(tools):
            # Pass tool instances to the interpreter via globals
            # The interpreter will find these via builtins
            globals_dict = {
                "_add_tool_instance": add_tool_instance,
                "_multiply_tool_instance": multiply_tool_instance,
                "_concat_tool_instance": concat_tool_instance,
            }
            
            # Run the program with the safe interpreter
            interpret_code(wrapper_program, allowed_modules=allowed_modules)
            
    except SyntaxError as e:
        logger.error(f"Syntax error in generated code: {e}")
        typer.echo(typer.style(f"Syntax error: {e}", fg=typer.colors.RED))
    except Exception as e:
        logger.error(f"Execution error: {e}")
        typer.echo(typer.style(f"Execution failed: {e}", fg=typer.colors.RED))
    else:
        logger.info("Program executed successfully")
        typer.echo(typer.style("Execution completed successfully", fg=typer.colors.GREEN))

# Synchronous callback to invoke async generate_core
@app.callback(invoke_without_command=True)
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
):
    """
    Asynchronously generate a Python program based on a task description using specified tools and model.

    Examples:
        $ python action_gen.py "Add 5 and 7 and print the result"
        $ python action_gen.py "Concatenate 'Hello' and 'World' and print it" --model gpt-4 --max-tokens 5000
    """
    asyncio.run(generate_core(task, model, max_tokens))

# Entry point to start the app
def main():
    logger.debug("Starting script execution")
    app()

if __name__ == "__main__":
    main()
