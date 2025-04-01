import ast
import asyncio
from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from quantalogic.tools import Tool

from .constants import MAX_GENERATE_PROGRAM_TOKENS
from .events import PromptGeneratedEvent
from .llm_util import litellm_completion
from .templates import jinja_env
from .xml_utils import XMLResultHandler, validate_xml


async def generate_program(
    task_description: str,
    tools: List[Tool],
    model: str,
    max_tokens: int,
    step: int,
    notify_event: Callable,
    streaming: bool = False
) -> str:
    """Generate a Python program using the specified model with streaming support and retries."""
    tools_by_toolbox = {}
    for tool in tools:
        toolbox_name = tool.toolbox_name if tool.toolbox_name else "Default Toolbox"
        if toolbox_name not in tools_by_toolbox:
            tools_by_toolbox[toolbox_name] = []
        tools_by_toolbox[toolbox_name].append(tool.to_docstring())

    prompt = jinja_env.get_template("generate_program.j2").render(
        task_description=task_description,
        tools_by_toolbox=tools_by_toolbox
    )
    await notify_event(PromptGeneratedEvent(
        event_type="PromptGenerated", step_number=step, prompt=prompt
    ))

    for attempt in range(3):
        try:
            response = await litellm_completion(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a Python code generator."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3,
                stream=streaming,
                step=step,
                notify_event=notify_event
            )
            code = response.strip()
            return code[9:-3].strip() if code.startswith("```python") and code.endswith("```") else code
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                raise Exception(f"Code generation failed with {model} after 3 attempts: {e}")

class PromptStrategy(ABC):
    """Abstract base class for prompt generation strategies."""
    @abstractmethod
    async def generate_prompt(self, task: str, history_str: str, step: int, max_iterations: int) -> str:
        pass

class DefaultPromptStrategy(PromptStrategy):
    """Default strategy using Jinja2 templates."""
    async def generate_prompt(self, task: str, history_str: str, step: int, max_iterations: int) -> str:
        return jinja_env.get_template("generate_action.j2").render(
            task=task,
            history_str=history_str,
            current_step=step,
            max_iterations=max_iterations
        )

class BaseReasoner(ABC):
    """Abstract base class for reasoning components."""
    @abstractmethod
    async def generate_action(
        self,
        task: str,
        history_str: str,
        step: int,
        max_iterations: int,
        system_prompt: Optional[str],
        notify_event: Callable,
        streaming: bool
    ) -> str:
        pass

class Reasoner(BaseReasoner):
    """Handles action generation using the language model."""
    def __init__(self, model: str, tools: List[Tool], prompt_strategy: Optional[PromptStrategy] = None):
        self.model = model
        self.tools = tools
        self.prompt_strategy = prompt_strategy or DefaultPromptStrategy()

    async def generate_action(
        self,
        task: str,
        history_str: str,
        step: int,
        max_iterations: int,
        system_prompt: Optional[str] = None,
        notify_event: Callable = None,
        streaming: bool = False
    ) -> str:
        """Generate an action based on task and history with streaming support."""
        try:
            task_prompt = await self.prompt_strategy.generate_prompt(
                task if not system_prompt else f"{system_prompt}\nTask: {task}",
                history_str,
                step,
                max_iterations
            )
            await notify_event(PromptGeneratedEvent(
                event_type="PromptGenerated", step_number=step, prompt=task_prompt
            ))
            program = await generate_program(task_prompt, self.tools, self.model, MAX_GENERATE_PROGRAM_TOKENS, step, notify_event, streaming=streaming)
            program = self._clean_code(program)
            response = jinja_env.get_template("response_format.j2").render(
                task=task,
                included_stepsincluded_stepshistory_str=history_str,
                program=program,
                current_step=step,
                max_iterations=max_iterations
            )
            if not validate_xml(response):
                raise ValueError("Invalid XML generated")
            return response
        except Exception as e:
            return XMLResultHandler.format_error_result(str(e))

    def _clean_code(self, code: str) -> str:
        lines = code.splitlines()
        in_code_block = False
        code_lines = []
        
        for line in lines:
            if line.startswith('```python'):
                in_code_block = True
                code_part = line[len('```python'):].strip()
                if code_part:
                    code_lines.append(code_part)
                continue
            if in_code_block:
                if line.startswith('```'):
                    break
                code_lines.append(line)
        
        final_code = '\n'.join(code_lines) if in_code_block else code
        
        try:
            ast.parse(final_code)
            return final_code
        except SyntaxError as e:
            raise ValueError(f'Invalid Python code: {e}') from e