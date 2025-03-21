import ast
import asyncio
import inspect
from asyncio import TimeoutError
from contextlib import AsyncExitStack
from functools import partial, wraps
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

# region Enhanced Tool Definitions
def logged_tool(verb: str):
    """Decorator factory to add consistent logging to tool functions."""
    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            logger.info(f"Starting tool execution: {func.__name__}")
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            args_str = ", ".join(f"{k}={v}" for k, v in bound_args.arguments.items())
            logger.info(f"{verb} {args_str}")
            result = await func(*args, **kwargs)
            logger.info(f"Finished tool execution: {func.__name__}")
            return result
        return wrapped
    return decorator

def log_tool_method(func):
    """Decorator to add logging to Tool class methods."""
    @wraps(func)
    async def wrapper(self, **kwargs):
        logger.info(f"Starting tool execution: {self.name}")
        try:
            result = await func(self, **kwargs)
            logger.info(f"Finished tool execution: {self.name}")
            return result
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {str(e)}")
            raise
    return wrapper

@create_tool
@logged_tool("Adding")
async def add_tool(a: int, b: int) -> str:
    """Adds two numbers and returns the sum as a string."""
    return str(a + b)

@create_tool
@logged_tool("Multiplying")
async def multiply_tool(x: int, y: int) -> str:
    """Multiplies two numbers and returns the product as a string."""
    return str(x * y)

@create_tool
@logged_tool("Concatenating")
async def concat_tool(s1: str, s2: str) -> str:
    """Concatenates two strings and returns the result."""
    return s1 + s2

class AgentTool(Tool):
    """Maintained as class due to complex initialization requirements"""
    def __init__(self, model: str = "gemini/gemini-2.0-flash"):
        super().__init__(
            name="agent_tool",
            description="Generates text using a language model based on a system prompt and user prompt.",
            arguments=[
                ToolArgument(name="system_prompt", arg_type="string", 
                           description="System prompt to guide the model's behavior", required=True),
                ToolArgument(name="prompt", arg_type="string", 
                           description="User prompt to generate a response for", required=True),
                ToolArgument(name="temperature", arg_type="float", 
                           description="Temperature for generation (0 to 1)", required=True)
            ],
            return_type="string"
        )
        self.model = model
    
    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        system_prompt = kwargs["system_prompt"]
        prompt = kwargs["prompt"]
        temperature = float(kwargs["temperature"])
        
        if not 0 <= temperature <= 1:
            logger.error(f"Temperature {temperature} is out of range (0-1)")
            raise ValueError("Temperature must be between 0 and 1")
        
        logger.info(f"Generating text with model {self.model}, temperature {temperature}")
        try:
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(asyncio.timeout(30))
                
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
                logger.debug(f"Generated text: {generated_text[:100]}...")
                return generated_text
        except TimeoutError as e:
            error_msg = f"API call to {self.model} timed out after 30 seconds"
            logger.error(error_msg)
            raise TimeoutError(error_msg) from e
        except Exception as e:
            logger.error(f"Text generation failed: {str(e)}")
            raise RuntimeError(f"Text generation failed: {str(e)}") from e
# endregion

# region Core Agent Functionality (Preserved with Original Implementation)
def validate_xml(xml_string: str) -> bool:
    """Validate XML string against a simple implicit schema."""
    try:
        etree.fromstring(xml_string)
        return True
    except etree.XMLSyntaxError as e:
        logger.error(f"XML validation failed: {e}")
        return False

async def generate_program(task_description: str, tools: List[Tool], model: str, max_tokens: int) -> str:
    logger.debug(f"Generating program for task: {task_description}")
    tool_docstrings = "\n\n".join([tool.to_docstring() for tool in tools])

    template = jinja_env.get_template("action_code/generate_program.j2")
    prompt = template.render(
        task_description=task_description,
        tool_docstrings=tool_docstrings
    )
    
    for attempt in range(3):
        try:
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
            
            if generated_code.startswith("```python") and generated_code.endswith("```"):
                generated_code = generated_code[9:-3].strip()
            return generated_code
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                raise typer.BadParameter(f"Failed to generate code with model '{model}': {str(e)}")

class ReActAgent:
    def __init__(self, model: str, tools: List[Tool], max_iterations: int = 5):
        self.model = model
        self.tools = tools
        self.max_iterations = max_iterations
        self.tool_namespace: Dict[str, Callable] = self._build_tool_namespace()

    def _build_tool_namespace(self) -> Dict[str, Callable]:
        namespace = {"asyncio": asyncio}
        for tool in self.tools:
            namespace[tool.name] = partial(tool.async_execute)
        return namespace

    async def generate_action(self, task: str, history: List[Dict[str, str]], current_step: int, max_iterations: int) -> str:
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
            return jinja_env.get_template("action_code/error_format.j2").render(error=str(e))

    async def execute_action(self, code: str,timeout: int = 300) -> str:
        if not self._validate_code(code):
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", 
                            message="Generated code lacks an async main() function"),
                encoding="unicode"
            )

        try:
            result = await execute_async(
                code=code,
                timeout=timeout,
                entry_point="main",
                allowed_modules=["asyncio"],
                namespace=self.tool_namespace,
            )
            return self._format_execution_result(result)
        except Exception as e:
            return etree.tostring(
                etree.Element("ExecutionResult", status="Error", message=f"Execution error: {e}"),
                encoding="unicode"
            )

    def _validate_code(self, code: str) -> bool:
        try:
            tree = ast.parse(code)
            return any(isinstance(node, ast.AsyncFunctionDef) and node.name == "main" for node in ast.walk(tree))
        except SyntaxError:
            return False

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        return "\n".join(
            f"[Step {i+1}] {h['thought']}\nAction:\n{h['action']}\nResult: {h['result']}"
            for i, h in enumerate(history)
        ) if history else "No previous steps"

    def _format_execution_result(self, result) -> str:
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
        
        return etree.tostring(root, pretty_print=True, encoding="unicode")

    async def is_task_complete(self, task: str, history: List[Dict[str, str]], result: str, 
                             success_criteria: Optional[str] = None) -> Tuple[bool, str]:
        try:
            result_xml = etree.fromstring(result)
            if result_xml.findtext("Completed") == "true":
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
                    return True, final_answer
                return True, final_answer
        
        except etree.XMLSyntaxError:
            pass
        
        if success_criteria:
            result_value = self._extract_result(result)
            if result_value and success_criteria in result_value:
                return True, result_value
        
        return False, ""

    def _extract_final_answer(self, result: str) -> str:
        try:
            return etree.fromstring(result).findtext("FinalAnswer") or ""
        except etree.XMLSyntaxError:
            return ""

    def _extract_result(self, result: str) -> str:
        try:
            return etree.fromstring(result).findtext("Value") or ""
        except etree.XMLSyntaxError:
            return ""

    async def solve(self, task: str, success_criteria: Optional[str] = None) -> List[Dict[str, str]]:
        history = []
        for iteration in range(self.max_iterations):
            current_step = iteration + 1
            response = await self.generate_action(task, history, current_step, self.max_iterations)
            
            try:
                thought, code = self._parse_response(response)
                result = await self.execute_action(code)
                history.append({"thought": thought, "action": code, "result": result})
                
                is_complete, final_answer = await self.is_task_complete(task, history, result, success_criteria)
                if is_complete:
                    history[-1]["result"] += f"\n<FinalAnswer><![CDATA[\n{final_answer}\n]]></FinalAnswer>"
                    break
            except (ValueError, etree.XMLSyntaxError):
                break
        return history

    def _parse_response(self, response: str) -> Tuple[str, str]:
        try:
            root = etree.fromstring(response)
            return root.findtext("Thought") or "", root.findtext("Code") or ""
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Failed to parse XML response: {e}")
# endregion

# region Preserved CLI Interface
async def run_react_agent(
    task: str,
    model: str,
    max_iterations: int,
    success_criteria: Optional[str] = None,
    tools: Optional[List[Union[Tool, Callable]]] = None
) -> None:
    default_tools = [add_tool, multiply_tool, concat_tool, AgentTool(model=model)]
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
# endregion