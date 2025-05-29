import ast
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger
from lxml import etree
from nanoid import generate

from quantalogic.tools import Tool

from .events import PromptGeneratedEvent
from .executor import ALLOWED_MODULES as DEFAULT_ALLOWED_MODULES
from .llm_util import LLMCompletionError, litellm_completion
from .message import Message
from .templates import jinja_env
from .working_memory import WorkingMemory
from .xml_utils import XMLResultHandler, validate_xml


class PromptStrategy(ABC):
    """Abstract base class for prompt generation strategies."""

    @abstractmethod
    async def generate_prompt(
        self,
        task: str,
        step_history_str: str,
        step: int,
        max_iterations: int,
        available_vars: List[str],
        allowed_modules: List[str],
        working_memory: WorkingMemory,
    ) -> str:
        pass


class DefaultPromptStrategy(PromptStrategy):
    """Default strategy using Jinja2 templates."""

    async def generate_prompt(
        self,
        task: str,
        step_history_str: str,
        step: int,
        max_iterations: int,
        available_vars: List[str],
        allowed_modules: List[str],
        working_memory: WorkingMemory,
    ) -> str:
        tools_by_toolbox = {}
        for tool in self.tools:
            toolbox_name = tool.toolbox_name if tool.toolbox_name else "default"
            if toolbox_name not in tools_by_toolbox:
                tools_by_toolbox[toolbox_name] = []
            tools_by_toolbox[toolbox_name].append(tool.to_docstring())

        available_vars = available_vars or []
        if 'context_vars' not in available_vars:
            available_vars.append('context_vars')
        logger.debug(f"Rendering prompt with available_vars: {available_vars}")

        return jinja_env.get_template("action_program.j2").render(
            task_description=task,
            history_str=step_history_str,
            current_step=step,
            max_iterations=max_iterations,
            tools_by_toolbox=tools_by_toolbox,
            available_vars=available_vars,
            allowed_modules=allowed_modules,
            context_vars={'state': {}},
            working_memory=working_memory,
        )


class BaseReasoner(ABC):
    """Abstract base class for reasoning components."""

    @abstractmethod
    async def generate_action(
        self,
        task: str,
        step_history_str: str,
        step: int,
        max_iterations: int,
        system_prompt: Optional[str],
        notify_event: Callable,
        streaming: bool,
        available_vars: List[str],
        allowed_modules: List[str],
        conversation_history: List[Message],
    ) -> str:
        """Generate an action with dynamic allowed modules for import."""
        pass


class Reasoner(BaseReasoner):
    """Handles action generation using the language model."""

    def __init__(
        self,
        model: str,
        tools: List[Tool],
        temperature: float = 0.3,
        config: Optional[Dict[str, Any]] = None,
        prompt_strategy: Optional[PromptStrategy] = None,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ):
        self.model = model
        self.tools = tools
        self.temperature = temperature
        self.config = config or {}
        self.prompt_strategy = prompt_strategy or DefaultPromptStrategy()
        self.prompt_strategy.tools = tools
        self.agent_id = agent_id or generate()
        self.agent_name = agent_name or f"agent_{self.agent_id[:8]}"
        self.working_memory = None  # Will be set by CodeActAgent

    async def generate_action(
        self,
        task: str,
        step_history_str: str,
        step: int,
        max_iterations: int,
        system_prompt: Optional[str] = None,
        notify_event: Callable = None,
        streaming: bool = False,
        available_vars: List[str] = None,
        allowed_modules: List[str] = None,
        conversation_history: List[Message] = None,
    ) -> str:
        """Generate an action based on task and history with streaming support."""
        allowed_modules = allowed_modules or DEFAULT_ALLOWED_MODULES
        conv_items = conversation_history or []
        if not isinstance(conv_items, list):
            raise ValueError("conversation_history must be a list of Message or dict")
        conversation_history = []
        for msg in conv_items:
            if isinstance(msg, Message):
                conversation_history.append(
                    {"role": msg.role, "content": f"nanoid:{msg.nanoid}\n{msg.content}"}
                )
            elif isinstance(msg, dict):
                content = msg.get("content")
                if "nanoid" in msg:
                    content = f"nanoid:{msg['nanoid']}\n{msg['content']}"
                conversation_history.append({"role": msg.get("role"), "content": content})
            else:
                raise ValueError(f"Invalid message type {type(msg)} in conversation_history")

        try:
            available_vars = available_vars or ['context_vars']
            logger.debug(f"Step {step}: Generating action with available_vars: {available_vars}")

            task_prompt = await self.prompt_strategy.generate_prompt(
                task if not system_prompt else f"### Personality Prompt: {system_prompt}\n###Task: {task}",
                step_history_str,
                step,
                max_iterations,
                available_vars,
                allowed_modules,
                working_memory=self.working_memory,
            )
            await notify_event(PromptGeneratedEvent(
                event_type="PromptGenerated",
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                step_number=step,
                prompt=task_prompt
            ))
            logger.debug(f"Generated prompt for step {step}:\n{task_prompt}")

            messages = (
                [{"role": "system", "content": "You are a Python code generator."}]
                + conversation_history
                + [{"role": "user", "content": task_prompt}]
            )

            logger.debug(f"👨‍🍳 Conversation history for step {step}:\n{conversation_history}")

            for attempt in range(3):
                try:
                    response = await litellm_completion(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        stream=streaming,
                        step=step,
                        notify_event=notify_event,
                        agent_id=self.agent_id,
                        agent_name=self.agent_name,
                    )
                    program = self._clean_code(response)
                    response = jinja_env.get_template("response_format.j2").render(
                        task=task,
                        history_str=step_history_str,
                        program=program,
                        current_step=step,
                        max_iterations=max_iterations,
                    )
                    logger.debug(f"Raws Generated response for step {step}:\n{response}")
                    if not validate_xml(response):
                        raise ValueError("Invalid XML generated")
                    thought, code = self._parse_response(response)
                    if not code:
                        raise ValueError("No valid Python code extracted from response")
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
        import re
        import textwrap

        match = re.search(r"```(?:[\w+-]*)\n([\s\S]*?)```", code, re.DOTALL)
        code_content = match.group(1) if match else code

        code_content = code_content.strip("` \n")
        final_code = textwrap.dedent(code_content).strip()

        try:
            ast.parse(final_code)
        except SyntaxError as e:
            logger.warning(f"Syntax error in cleaned code: {e}, returning dedented code.")
        return final_code

    def _parse_response(self, response: str) -> Tuple[str, str]:
        """Parse the XML response to extract thought and code reliably."""
        import re

        xml_match = re.search(r"<Action>.*?</Action>", response, re.DOTALL)
        if not xml_match:
            logger.error("No <Action> tag found in response")
            return "", ""

        xml_str = xml_match.group(0)
        try:
            parser = etree.XMLParser(recover=True, remove_comments=True, resolve_entities=False)
            tree = etree.fromstring(xml_str, parser=parser)
            thought = tree.findtext("Thought", default="")
            code_element = tree.find("Code")
            code = code_element.text.strip() if code_element is not None else ""
            return thought, code
        except etree.XMLSyntaxError as e:
            logger.error(f"Failed to parse XML: {e}")
            return "", ""