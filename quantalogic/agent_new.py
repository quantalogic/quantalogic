import ast
import asyncio
from asyncio import TimeoutError
from contextlib import AsyncExitStack
from functools import partial
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

import litellm
import typer
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from lxml import etree

from quantalogic.python_interpreter import execute_async
from quantalogic.tools.tool import Tool, ToolArgument, create_tool

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


# Define tool classes from action_gen.py
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
                    max_tokens=1000
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


# XML Validation Helper
def validate_xml(xml_string: str) -> bool:
    """Validate XML string against a simple implicit schema."""
    try:
        etree.fromstring(xml_string)
        return True
    except etree.XMLSyntaxError as e:
        logger.error(f"XML validation failed: {e}")
        return False


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

    template = jinja_env.get_template("action_code/generate_program.j2")
    prompt = template.render(
        task_description=task_description,
        tool_docstrings=tool_docstrings
    )
    
    logger.debug(f"Prompt sent to litellm:\n{prompt}")
    
    for attempt in range(3):  # Retry logic for robustness
        try:
            logger.debug(f"Calling litellm with model {model}, attempt {attempt + 1}")
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
            
            if generated_code.startswith("```python") and generated_code.endswith("```"):
                generated_code = generated_code[9:-3].strip()
            return generated_code
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to generate code after retries: {str(e)}")
                raise typer.BadParameter(f"Failed to generate code with model '{model}': {str(e)}")


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

    async def generate_action(self, task: str, history: List[Dict[str, str]], current_step: int, max_iterations: int) -> str:
        """Generate a Python program as an action, returning XML."""
        logger.info(f"Generating action for task: {task} at step {current_step} of {max_iterations}")
        history_str = self._format_history(history)

        try:
            task_prompt = jinja_env.get_template("action_code/generate_action.j2").render(
                task=task,
                history_str=history_str,
                current_step=current_step,
                max_iterations=max_iterations
            )
            program = await generate_program(
                task_description=task_prompt,
                tools=self.tools,
                model=self.model,
                max_tokens=MAX_TOKENS,
            )
            logger.debug(f"Generated program:\n{program}")
            response = jinja_env.get_template("action_code/response_format.j2").render(
                task=task,
                history_str=history_str,
                program=program,
                current_step=current_step,
                max_iterations=max_iterations
            )
            if not validate_xml(response):
                raise ValueError("Generated XML is invalid")
            return response
        except Exception as e:
            logger.error(f"Action generation failed: {e}")
            return jinja_env.get_template("action_code/error_format.j2").render(error=str(e))

    async def execute_action(self, code: str) -> str:
        """Execute the generated code and return formatted XML result."""
        logger.debug(f"Executing action:\n{code}")
        
        if not self._validate_code(code):
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message="Generated code lacks an async main() function"),
                encoding="unicode"
            )

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
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message=f"Syntax error: {e}"),
                encoding="unicode"
            )
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message=f"Execution error: {e}"),
                encoding="unicode"
            )

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
        """Format execution result as XML with CDATA."""
        root = etree.Element("ExecutionResult")
        etree.SubElement(root, "Status").text = "Success" if not result.error else "Error"
        etree.SubElement(root, "Value").text = etree.CDATA(str(result.result or result.error))
        etree.SubElement(root, "ExecutionTime").text = f"{result.execution_time:.2f} seconds"
        
        if not result.error and result.result and result.result.startswith("Task completed:"):
            etree.SubElement(root, "Completed").text = "true"
            final_answer = result.result[len("Task completed:"):].strip()
            etree.SubElement(root, "FinalAnswer").text = etree.CDATA(final_answer)
        else:
            etree.SubElement(root, "Completed").text = "false"
        
        if result.local_variables:
            vars_elem = etree.SubElement(root, "Variables")
            for k, v in result.local_variables.items():
                if not callable(v) and not k.startswith("__"):
                    var_elem = etree.SubElement(vars_elem, "Variable", name=k)
                    var_elem.text = etree.CDATA(str(v)[:5000] + ("... (truncated)" if len(str(v)) > 5000 else ""))
        
        formatted_result = etree.tostring(root, pretty_print=True, encoding="unicode")
        logger.debug(f"Execution result: {formatted_result[:100]}..." if len(formatted_result) > 100 else formatted_result)
        return formatted_result

    async def is_task_complete(self, task: str, history: List[Dict[str, str]], result: str, success_criteria: Optional[str] = None) -> Tuple[bool, str]:
        """Determine if the task is complete using a hybrid approach."""
        try:
            result_xml = etree.fromstring(result)
            completed = result_xml.findtext("Completed") == "true"
            if completed:
                final_answer = result_xml.findtext("FinalAnswer") or ""
                verification_prompt = f"Does '{final_answer}' solve '{task}' given history:\n{self._format_history(history)}?"
                verification = await litellm.acompletion(
                    model=self.model,
                    messages=[{"role": "user", "content": verification_prompt}],
                    temperature=0.1,
                    max_tokens=100
                )
                response = verification.choices[0].message.content.lower()
                if "yes" in response or "true" in response:
                    logger.info(f"Task completion verified by LLM: {final_answer}")
                    return True, final_answer
                return True, final_answer  # Fallback if verification fails
        
        except etree.XMLSyntaxError as e:
            logger.error(f"Failed to parse result XML: {e}")
        
        if success_criteria:
            result_value = self._extract_result(result)
            if result_value and success_criteria in result_value:
                logger.info(f"Task completed based on success criteria: {result_value}")
                return True, result_value
        
        return False, ""

    def _extract_final_answer(self, result: str) -> str:
        """Extract the final answer from the execution result."""
        try:
            result_xml = etree.fromstring(result)
            return result_xml.findtext("FinalAnswer") or ""
        except etree.XMLSyntaxError:
            return ""

    def _extract_result(self, result: str) -> str:
        """Extract the raw result value from the execution result."""
        try:
            result_xml = etree.fromstring(result)
            return result_xml.findtext("Value") or ""
        except etree.XMLSyntaxError:
            return ""

    async def solve(self, task: str, success_criteria: Optional[str] = None) -> List[Dict[str, str]]:
        """Solve the task iteratively with enhanced completion criteria."""
        history = []
        for iteration in range(self.max_iterations):
            current_step = iteration + 1
            logger.info(f"Iteration {current_step} for task: {task}")
            response = await self.generate_action(task, history, current_step, self.max_iterations)
            
            try:
                thought, code = self._parse_response(response)
                result = await self.execute_action(code)
                history.append({"thought": thought, "action": code, "result": result})
                
                is_complete, final_answer = await self.is_task_complete(task, history, result, success_criteria)
                if is_complete:
                    logger.info(f"Task solved after {current_step} iterations")
                    history[-1]["result"] += f"\n<FinalAnswer><![CDATA[\n{final_answer}\n]]></FinalAnswer>"
                    break
            except (ValueError, etree.XMLSyntaxError) as e:
                logger.error(f"Response parsing failed: {e}")
                break
        return history

    def _parse_response(self, response: str) -> Tuple[str, str]:
        """Parse thought and code from XML response."""
        try:
            root = etree.fromstring(response)
            thought = root.findtext("Thought") or ""
            code = root.findtext("Code") or ""
            if not code:
                raise ValueError("No code found in response")
            return thought, code
        except etree.XMLSyntaxError as e:
            logger.error(f"Invalid XML response: {e}")
            raise ValueError(f"Failed to parse XML response: {e}")


async def run_react_agent(
    task: str,
    model: str,
    max_iterations: int,
    success_criteria: Optional[str] = None,
    tools: Optional[List[Union[Tool, Callable]]] = None
) -> None:
    """Run the ReAct agent and present the final answer clearly."""
    default_tools = [AddTool(), MultiplyTool(), ConcatTool(), AgentTool(model=model)]
    tools = tools if tools is not None else default_tools
    
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
    success_criteria: Optional[str] = typer.Option(None, help="Optional criteria to determine task completion (e.g., expected result)"),
) -> None:
    """Solve a task using a ReAct Agent."""
    try:
        asyncio.run(run_react_agent(task, model, max_iterations, success_criteria))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()