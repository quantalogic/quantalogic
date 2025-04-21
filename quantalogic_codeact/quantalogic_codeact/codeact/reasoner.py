import ast
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from quantalogic.tools import Tool

from .constants import MAX_GENERATE_PROGRAM_TOKENS
from .events import PromptGeneratedEvent
from .llm_util import LLMCompletionError, litellm_completion
from .templates import jinja_env
from .xml_utils import XMLResultHandler, validate_xml


class PromptStrategy(ABC):
    """Abstract base class for prompt generation strategies."""
    @abstractmethod
    async def generate_prompt(self, task: str, history_str: str, step: int, max_iterations: int, available_vars: List[str]) -> str:
        pass


class DefaultPromptStrategy(PromptStrategy):
    """Default strategy using Jinja2 templates."""
    async def generate_prompt(self, task: str, history_str: str, step: int, max_iterations: int, available_vars: List[str]) -> str:
        tools_by_toolbox = {}
        for tool in self.tools:
            toolbox_name = tool.toolbox_name if tool.toolbox_name else "default"
            if toolbox_name not in tools_by_toolbox:
                tools_by_toolbox[toolbox_name] = []
            tools_by_toolbox[toolbox_name].append(tool.to_docstring())
        
        return jinja_env.get_template("action_program.j2").render(
            task_description=task,
            history_str=history_str,
            current_step=step,
            max_iterations=max_iterations,
            tools_by_toolbox=tools_by_toolbox,
            available_vars=available_vars
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
        streaming: bool,
        available_vars: List[str]
    ) -> str:
        pass


class Reasoner(BaseReasoner):
    """Handles action generation using the language model."""
    def __init__(self, model: str, tools: List[Tool], config: Optional[Dict[str, Any]] = None, prompt_strategy: Optional[PromptStrategy] = None):
        self.model = model
        self.tools = tools
        self.config = config or {}
        self.prompt_strategy = prompt_strategy or DefaultPromptStrategy()
        self.prompt_strategy.tools = tools  # Inject tools into strategy

    async def generate_action(
        self,
        task: str,
        history_str: str,
        step: int,
        max_iterations: int,
        system_prompt: Optional[str] = None,
        notify_event: Callable = None,
        streaming: bool = False,
        available_vars: List[str] = None
    ) -> str:
        """Generate an action based on task and history with streaming support."""
        try:
            # Prepare type hints for available variables based on tool return types
            available_var_types = {}
            for var_name in available_vars or []:
                # Infer type from tool documentation if possible (simplified heuristic)
                if "plan" in var_name.lower():
                    available_var_types[var_name] = "PlanResult (has attributes: task_id, task_description, subtasks)"
                else:
                    available_var_types[var_name] = "Unknown (check history or assume str)"

            task_prompt = await self.prompt_strategy.generate_prompt(
                task if not system_prompt else f"{system_prompt}\nTask: {task}",
                history_str,
                step,
                max_iterations,
                available_vars or []  # Default to empty list if None
            )
            await notify_event(PromptGeneratedEvent(
                event_type="PromptGenerated", step_number=step, prompt=task_prompt
            ))
            logger.debug(f"Generated prompt for step {step}:\n{task_prompt}")

            for attempt in range(3):
                try:
                    response = await litellm_completion(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a Python code generator."},
                            {"role": "user", "content": task_prompt}
                        ],
                        max_tokens=self.config.get("max_tokens", MAX_GENERATE_PROGRAM_TOKENS),
                        temperature=0.3,
                        stream=streaming,
                        step=step,
                        notify_event=notify_event
                    )
                    program = response.strip()
                    program = self._clean_code(program)
                    response = jinja_env.get_template("response_format.j2").render(
                        task=task,
                        history_str=history_str,
                        program=program,
                        current_step=step,
                        max_iterations=max_iterations
                    )
                    if not validate_xml(response):
                        raise ValueError("Invalid XML generated")
                    return response
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                        continue
                    raise Exception(f"Code generation failed with {self.model} after 3 attempts: {e}")
        except LLMCompletionError as e:
            raise e
        except Exception as e:
            logger.error(f"Error generating action: {e}")
            return XMLResultHandler.format_error_result(str(e))

    def _clean_code(self, code: str) -> str:
        """Clean the generated code, removing markdown and ensuring valid syntax."""
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