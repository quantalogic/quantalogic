"""Enhanced QuantaLogic agent implementing the ReAct framework."""

import asyncio
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger
from pydantic import BaseModel, ConfigDict, PrivateAttr

from quantalogic.event_emitter import EventEmitter
from quantalogic.generative_model import GenerativeModel, ResponseStats, TokenUsage
from quantalogic.memory import AgentMemory, Message, VariableMemory
from quantalogic.prompts import system_prompt
from quantalogic.tool_manager import ToolManager
from quantalogic.tools.task_complete_tool import TaskCompleteTool
from quantalogic.tools.tool import Tool
from quantalogic.utils import get_environment
from quantalogic.utils.ask_user_validation import console_ask_for_user_validation
from quantalogic.xml_parser import ToleranceXMLParser
from quantalogic.xml_tool_parser import ToolParser

# Maximum ratio occupancy of the occupied memory
MAX_OCCUPANCY = 90.0

# Maximum response length in characters
MAX_RESPONSE_LENGTH = 1024 * 32

DEFAULT_MAX_INPUT_TOKENS = 128 * 1024
DEFAULT_MAX_OUTPUT_TOKENS = 4096

# Maximum recursion depth for variable interpolation
MAX_INTERPOLATION_DEPTH = 10


class AgentConfig(BaseModel):
    """Configuration settings for the Agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    environment_details: str
    tools_markdown: str
    system_prompt: str


class ObserveResponseResult(BaseModel):
    """Represents the result of observing the assistant's response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    next_prompt: str
    executed_tool: str | None = None
    answer: str | None = None


class Agent(BaseModel):
    """Enhanced QuantaLogic agent implementing ReAct framework.

    Supports both synchronous and asynchronous operations for task solving.
    Use `solve_task` for synchronous contexts (e.g., CLI tools) and `async_solve_task`
    for asynchronous contexts (e.g., web servers).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True, extra="forbid")

    specific_expertise: str
    model: GenerativeModel
    memory: AgentMemory = AgentMemory()  # A list User / Assistant Messages
    variable_store: VariableMemory = VariableMemory()  # A dictionary of variables
    tools: ToolManager = ToolManager()
    event_emitter: EventEmitter = EventEmitter()
    config: AgentConfig
    task_to_solve: str
    task_to_solve_summary: str = ""
    ask_for_user_validation: Callable[[str], bool] = console_ask_for_user_validation
    last_tool_call: dict[str, Any] = {}  # Stores the last tool call information
    total_tokens: int = 0  # Total tokens in the conversation
    current_iteration: int = 0
    max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    max_iterations: int = 30
    system_prompt: str = ""
    compact_every_n_iterations: int | None = None
    max_tokens_working_memory: int | None = None
    _model_name: str = PrivateAttr(default="")

    def __init__(
        self,
        model_name: str = "",
        memory: AgentMemory = AgentMemory(),
        variable_store: VariableMemory = VariableMemory(),
        tools: list[Tool] = [TaskCompleteTool()],
        ask_for_user_validation: Callable[[str], bool] = console_ask_for_user_validation,
        task_to_solve: str = "",
        specific_expertise: str = "General AI assistant with coding and problem-solving capabilities",
        get_environment: Callable[[], str] = get_environment,
        compact_every_n_iterations: int | None = None,
        max_tokens_working_memory: int | None = None,
        event_emitter: EventEmitter | None = None,
    ):
        """Initialize the agent with model, memory, tools, and configurations.
        
        Args:
            model_name: Name of the model to use
            memory: AgentMemory instance for storing conversation history
            variable_store: VariableMemory instance for storing variables
            tools: List of Tool instances 
            ask_for_user_validation: Function to ask for user validation
            task_to_solve: Initial task to solve
            specific_expertise: Description of the agent's expertise
            get_environment: Function to get environment details
            compact_every_n_iterations: How often to compact memory
            max_tokens_working_memory: Maximum token count for working memory
            event_emitter: EventEmitter instance for event handling
        """
        try:
            logger.debug("Initializing agent...")

            # Create or use provided event emitter
            if event_emitter is None:
                event_emitter = EventEmitter()

            # Add TaskCompleteTool to the tools list if not already present
            if not any(isinstance(t, TaskCompleteTool) for t in tools):
                tools.append(TaskCompleteTool())

            tool_manager = ToolManager(tools={tool.name: tool for tool in tools})
            environment = get_environment()
            logger.debug(f"Environment details: {environment}")
            tools_markdown = tool_manager.to_markdown()
            logger.debug(f"Tools Markdown: {tools_markdown}")

            system_prompt_text = system_prompt(
                tools=tools_markdown, environment=environment, expertise=specific_expertise
            )
            logger.debug(f"System prompt: {system_prompt_text}")

            config = AgentConfig(
                environment_details=environment,
                tools_markdown=tools_markdown,
                system_prompt=system_prompt_text,
            )

            # Initialize using Pydantic's model_validate
            super().__init__(
                specific_expertise=specific_expertise,
                model=GenerativeModel(model=model_name, event_emitter=event_emitter),
                memory=memory,
                variable_store=variable_store,
                tools=tool_manager,
                event_emitter=event_emitter,
                config=config,
                task_to_solve=task_to_solve,
                task_to_solve_summary="",
                ask_for_user_validation=ask_for_user_validation,
                last_tool_call={},
                total_tokens=0,
                current_iteration=0,
                max_input_tokens=DEFAULT_MAX_INPUT_TOKENS,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                max_iterations=30,
                system_prompt="",
                compact_every_n_iterations=compact_every_n_iterations or 30,
                max_tokens_working_memory=max_tokens_working_memory,
            )

            self._model_name = model_name

            logger.debug(f"Memory will be compacted every {self.compact_every_n_iterations} iterations")
            logger.debug(f"Max tokens for working memory set to: {self.max_tokens_working_memory}")
            logger.debug("Agent initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}")
            raise

    @property
    def model_name(self) -> str:
        """Get the current model name."""
        return self._model_name

    @model_name.setter
    def model_name(self, value: str) -> None:
        """Set the model name and update the model instance."""
        self._model_name = value
        # Update the model instance with the new name
        self.model = GenerativeModel(model=value, event_emitter=self.event_emitter)

    def clear_memory(self) -> None:
        """Clear the memory and reset the session."""
        self._reset_session(clear_memory=True)

    def solve_task(
        self, task: str, max_iterations: int = 30, streaming: bool = False, clear_memory: bool = True
    ) -> str:
        """Solve the given task using the ReAct framework (synchronous version).

        Ideal for synchronous applications. For asynchronous contexts, use `async_solve_task`.

        Args:
            task: The task description
            max_iterations: Maximum number of iterations
            streaming: Whether to use streaming mode
            clear_memory: Whether to clear memory before solving

        Returns:
            The final response after task completion
        """
        logger.debug(f"Solving task... {task}")
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create a new event loop if one doesn't exist
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.async_solve_task(task, max_iterations, streaming, clear_memory))

    async def async_solve_task(
        self, task: str, max_iterations: int = 30, streaming: bool = False, clear_memory: bool = True
    ) -> str:
        """Solve the given task using the ReAct framework (asynchronous version).

        Ideal for asynchronous applications. For synchronous contexts, use `solve_task`.

        Args:
            task: The task description
            max_iterations: Maximum number of iterations
            streaming: Whether to use streaming mode
            clear_memory: Whether to clear memory before solving

        Returns:
            The final response after task completion
        """
        logger.debug(f"Solving task asynchronously... {task}")
        self._reset_session(task_to_solve=task, max_iterations=max_iterations, clear_memory=clear_memory)
        self.task_to_solve_summary = await self._async_generate_task_summary(task)

        if not self.memory.memory or self.memory.memory[0].role != "system":
            self.memory.add(Message(role="system", content=self.config.system_prompt))

        self._emit_event("session_start", {"system_prompt": self.config.system_prompt, "content": task})

        self.max_output_tokens = self.model.get_model_max_output_tokens() or DEFAULT_MAX_OUTPUT_TOKENS
        self.max_input_tokens = self.model.get_model_max_input_tokens() or DEFAULT_MAX_INPUT_TOKENS

        done = False
        current_prompt = self._prepare_prompt_task(task)
        self.current_iteration = 1
        answer = ""

        while not done:
            try:
                self._update_total_tokens(self.memory.memory, current_prompt)
                self._emit_event("task_think_start", {"prompt": current_prompt})
                await self._async_compact_memory_if_needed(current_prompt)

                if streaming:
                    content = ""
                    async_stream = await self.model.async_generate_with_history(
                        messages_history=self.memory.memory,
                        prompt=current_prompt,
                        streaming=True,
                    )
                    async for chunk in async_stream:
                        content += chunk
                    result = ResponseStats(
                        response=content,
                        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                        model=self.model.model,
                        finish_reason="stop",
                    )
                else:
                    result = await self.model.async_generate_with_history(
                        messages_history=self.memory.memory,
                        prompt=current_prompt,
                        streaming=False,
                        # Removed stop_words parameter to allow complete responses
                    )

                content = result.response
                if not streaming:
                    token_usage = result.usage
                    self.total_tokens = token_usage.total_tokens

                self._emit_event("task_think_end", {"response": content})
                result = await self._async_observe_response(content, iteration=self.current_iteration)
                current_prompt = result.next_prompt

                if result.executed_tool == "task_complete":
                    self._emit_event("task_complete", {"response": result.answer})
                    answer = result.answer or ""  # Ensure answer is never None
                    done = True

                self._update_session_memory(current_prompt, content)
                self.current_iteration += 1
                if self.current_iteration >= self.max_iterations:
                    done = True
                    self._emit_event("error_max_iterations_reached")

            except Exception as e:
                logger.error(f"Error during async task solving: {str(e)}")
                answer = f"Error: {str(e)}"
                done = True

        self._emit_event("task_solve_end")
        return answer

    def _observe_response(self, content: str, iteration: int = 1) -> ObserveResponseResult:
        """Analyze the assistant's response and determine next steps (synchronous wrapper).
        
        Args:
            content: The response content to analyze
            iteration: Current iteration number
            
        Returns:
            ObserveResponseResult with next steps information
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._async_observe_response(content, iteration))

    async def _async_observe_response(self, content: str, iteration: int = 1) -> ObserveResponseResult:
        """Analyze the assistant's response and determine next steps (asynchronous).
        
        Args:
            content: The response content to analyze
            iteration: Current iteration number
            
        Returns:
            ObserveResponseResult with next steps information
        """
        try:
            parsed_content = self._parse_tool_usage(content)
            if not parsed_content:
                return self._handle_no_tool_usage()

            for tool_name, tool_input in parsed_content.items():
                tool = self.tools.get(tool_name)
                if not tool:
                    return self._handle_tool_not_found(tool_name)

                arguments_with_values = self._parse_tool_arguments(tool, tool_input)
                is_repeated_call = self._is_repeated_tool_call(tool_name, arguments_with_values)

                if is_repeated_call:
                    executed_tool, response = self._handle_repeated_tool_call(tool_name, arguments_with_values)
                else:
                    executed_tool, response = await self._async_execute_tool(tool_name, tool, arguments_with_values)

                if not executed_tool:
                    return self._handle_tool_execution_failure(response)

                variable_name = self.variable_store.add(response)
                new_prompt = self._format_observation_response(response, executed_tool, variable_name, iteration)

                return ObserveResponseResult(
                    next_prompt=new_prompt,
                    executed_tool=executed_tool,
                    answer=response if executed_tool == "task_complete" else None,
                )
        except Exception as e:
            return self._handle_error(e)

    def _execute_tool(self, tool_name: str, tool: Tool, arguments_with_values: dict) -> tuple[str, Any]:
        """Execute a tool with validation if required (synchronous wrapper).
        
        Args:
            tool_name: Name of the tool to execute
            tool: Tool instance
            arguments_with_values: Tool arguments
            
        Returns:
            Tuple of (executed_tool_name, response)
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._async_execute_tool(tool_name, tool, arguments_with_values))

    async def _async_execute_tool(self, tool_name: str, tool: Tool, arguments_with_values: dict) -> tuple[str, Any]:
        """Execute a tool with validation if required (asynchronous).
        
        Args:
            tool_name: Name of the tool to execute
            tool: Tool instance
            arguments_with_values: Tool arguments
            
        Returns:
            Tuple of (executed_tool_name, response)
        """
        if tool.need_validation:
            question_validation = (
                "Do you permit the execution of this tool?\n"
                f"Tool: {tool_name}\nArguments:\n"
                "<arguments>\n"
                + "\n".join([f"    <{key}>{value}</{key}>" for key, value in arguments_with_values.items()])
                + "\n</arguments>\nYes or No"
            )
            permission_granted = self.ask_for_user_validation(question_validation)
            if not permission_granted:
                return "", f"Error: execution of tool '{tool_name}' was denied by the user."

        self._emit_event("tool_execution_start", {"tool_name": tool_name, "arguments": arguments_with_values})

        try:
            arguments_with_values_interpolated = {
                key: await self._async_interpolate_variables(value) for key, value in arguments_with_values.items()
            }
            if tool.need_variables:
                arguments_with_values_interpolated["variables"] = self.variable_store
            if tool.need_caller_context_memory:
                arguments_with_values_interpolated["caller_context_memory"] = self.memory.memory

            converted_args = self.tools.validate_and_convert_arguments(tool_name, arguments_with_values_interpolated)
            injectable_properties = tool.get_injectable_properties_in_execution()
            for key, value in injectable_properties.items():
                converted_args[key] = value

            if hasattr(tool, "async_execute") and callable(tool.async_execute):
                response = await tool.async_execute(**converted_args)
            else:
                # Fall back to synchronous execution if async is not available
                response = tool.execute(**converted_args)
            executed_tool = tool.name
        except Exception as e:
            response = f"Error executing tool: {tool_name}: {str(e)}\n"
            executed_tool = ""

        self._emit_event(
            "tool_execution_end", {"tool_name": tool_name, "arguments": arguments_with_values, "response": response}
        )
        return executed_tool, response

    async def _async_interpolate_variables(self, text: str, depth: int = 0) -> str:
        """Interpolate variables using $var$ syntax in the given text with recursion protection.
        
        Args:
            text: Text containing variable references
            depth: Current recursion depth
            
        Returns:
            Text with variables interpolated
        """
        if not isinstance(text, str):
            return str(text)
            
        if depth > MAX_INTERPOLATION_DEPTH:
            logger.warning(f"Max interpolation depth ({MAX_INTERPOLATION_DEPTH}) reached, stopping recursion")
            return text
            
        try:
            import re
            
            # Process each variable in the store
            for var in self.variable_store.keys():
                # Properly escape the variable name for regex using re.escape
                # but handle $ characters separately since they're part of our syntax
                escaped_var = re.escape(var).replace('\\$', '$')
                pattern = f"\\${escaped_var}\\$"
                
                # Get variable value as string
                replacement = str(self.variable_store[var])
                
                # Replace all occurrences
                text = re.sub(pattern, lambda m: replacement, text)
                
            # Check if there are still variables to interpolate (for nested variables)
            if '$' in text and depth < MAX_INTERPOLATION_DEPTH:
                return await self._async_interpolate_variables(text, depth + 1)
                
            return text
        except Exception as e:
            logger.error(f"Error in _async_interpolate_variables: {str(e)}")
            return text

    def _interpolate_variables(self, text: str) -> str:
        """Interpolate variables using $var$ syntax in the given text (synchronous wrapper).
        
        Args:
            text: Text containing variable references
            
        Returns:
            Text with variables interpolated
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._async_interpolate_variables(text))

    def _compact_memory_if_needed(self, current_prompt: str = "") -> None:
        """Compacts the memory if it exceeds the maximum occupancy (synchronous wrapper).
        
        Args:
            current_prompt: Current prompt to calculate token usage
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._async_compact_memory_if_needed(current_prompt))

    async def _async_compact_memory_if_needed(self, current_prompt: str = "") -> None:
        """Compacts the memory if it exceeds the maximum occupancy or token limit.
        
        Args:
            current_prompt: Current prompt to calculate token usage
        """
        ratio_occupied = self._calculate_context_occupancy()

        should_compact_by_occupancy = ratio_occupied >= MAX_OCCUPANCY
        should_compact_by_iteration = (
            self.compact_every_n_iterations is not None
            and self.current_iteration > 0
            and self.current_iteration % self.compact_every_n_iterations == 0
        )
        should_compact_by_token_limit = (
            self.max_tokens_working_memory is not None 
            and self.total_tokens > self.max_tokens_working_memory
        )

        if should_compact_by_occupancy or should_compact_by_iteration or should_compact_by_token_limit:
            if should_compact_by_occupancy:
                logger.debug(f"Memory compaction triggered: Occupancy {ratio_occupied}% exceeds {MAX_OCCUPANCY}%")

            if should_compact_by_iteration:
                logger.debug(
                    f"Memory compaction triggered: Iteration {self.current_iteration} is a multiple of {self.compact_every_n_iterations}"
                )

            if should_compact_by_token_limit:
                logger.debug(
                    f"Memory compaction triggered: Token count {self.total_tokens} exceeds limit {self.max_tokens_working_memory}"
                )

            self._emit_event("memory_full")
            await self._async_compact_memory()
            self.total_tokens = self.model.token_counter_with_history(self.memory.memory, current_prompt)
            self._emit_event("memory_compacted")

    async def _async_compact_memory(self) -> None:
        """Compact memory asynchronously."""
        self.memory.compact()

    async def _async_compact_memory_with_summary(self) -> str:
        """Generate a summary and compact memory asynchronously.
        
        Returns:
            Generated summary text
        """
        # Format conversation history for the template
        memory_copy = self.memory.memory.copy()

        if len(memory_copy) < 3:
            logger.warning("Not enough messages to compact memory with summary")
            return "Memory compaction skipped: not enough messages"

        user_message = memory_copy.pop()
        assistant_message = memory_copy.pop()
        
        # Create summarization prompt using template
        prompt_summary = self._render_template('memory_compaction_prompt.j2', 
                                             conversation_history="\n\n".join(
                                                 f"[{msg.role.upper()}]: {msg.content}" 
                                                 for msg in memory_copy
                                             ))
        
        summary = await self.model.async_generate_with_history(messages_history=memory_copy, prompt=prompt_summary)
        
        # Remove last system message if present
        if memory_copy and memory_copy[-1].role == "system":
            memory_copy.pop()
            
        memory_copy.append(Message(role="user", content=summary.response))
        memory_copy.append(assistant_message)
        memory_copy.append(user_message)
        self.memory.memory = memory_copy
        return summary.response

    def _generate_task_summary(self, content: str) -> str:
        """Generate a concise task-focused summary (synchronous wrapper).
        
        Args:
            content: The content to summarize
            
        Returns:
            Generated task summary
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._async_generate_task_summary(content))

    async def _async_generate_task_summary(self, content: str) -> str:
        """Generate a concise task-focused summary using the generative model.

        Args:
            content: The content to summarize

        Returns:
            Generated task summary
        """
        try:
            if len(content) < 1024 * 4:
                return content
                
            prompt = self._render_template('task_summary_prompt.j2', content=content)
            result = await self.model.async_generate(prompt=prompt)
            logger.debug(f"Generated summary: {result.response}")
            return result.response.strip() + "\n🚨 The FULL task is in <task> tag in the previous messages.\n"
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return f"Summary generation failed: {str(e)}"

    def _reset_session(self, task_to_solve: str = "", max_iterations: int = 30, clear_memory: bool = True) -> None:
        """Reset the agent's session.
        
        Args:
            task_to_solve: New task to solve
            max_iterations: Maximum number of iterations
            clear_memory: Whether to clear memory
        """
        logger.debug("Resetting session...")
        self.task_to_solve = task_to_solve
        if clear_memory:
            logger.debug("Clearing memory...")
            self.memory.reset()
            self.variable_store.reset()
            self.total_tokens = 0
        self.current_iteration = 0
        self.max_output_tokens = self.model.get_model_max_output_tokens() or DEFAULT_MAX_OUTPUT_TOKENS
        self.max_input_tokens = self.model.get_model_max_input_tokens() or DEFAULT_MAX_INPUT_TOKENS
        self.max_iterations = max_iterations

    def _update_total_tokens(self, message_history: list[Message], prompt: str) -> None:
        """Update the total tokens count based on message history and prompt.
        
        Args:
            message_history: List of messages
            prompt: Current prompt
        """
        self.total_tokens = self.model.token_counter_with_history(message_history, prompt)

    def _emit_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event with system context and optional additional data.
        
        Args:
            event_type: Type of event
            data: Additional event data
        """
        event_data = {
            "iteration": self.current_iteration,
            "total_tokens": self.total_tokens,
            "context_occupancy": self._calculate_context_occupancy(),
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
        }
        if data:
            event_data.update(data)
        self.event_emitter.emit(event_type, event_data)

    def _parse_tool_usage(self, content: str) -> dict:
        """Extract tool usage from the response content.
        
        Args:
            content: Response content
            
        Returns:
            Dictionary mapping tool names to inputs
        """
        if not content or not isinstance(content, str):
            return {}

        xml_parser = ToleranceXMLParser()
        action = xml_parser.extract_elements(text=content, element_names=["action"])

        tool_names = self.tools.tool_names()

        if action:
            return xml_parser.extract_elements(text=action["action"], element_names=tool_names)
        else:
            return xml_parser.extract_elements(text=content, element_names=tool_names)

    def _parse_tool_arguments(self, tool: Tool, tool_input: str) -> dict:
        """Parse the tool arguments from the tool input.
        
        Args:
            tool: Tool instance
            tool_input: Raw tool input text
            
        Returns:
            Dictionary of parsed arguments
        """
        tool_parser = ToolParser(tool=tool)
        return tool_parser.parse(tool_input)

    def _is_repeated_tool_call(self, tool_name: str, arguments_with_values: dict) -> bool:
        """Check if the tool call is repeated.
        
        Args:
            tool_name: Name of the tool
            arguments_with_values: Tool arguments
            
        Returns:
            True if call is repeated, False otherwise
        """
        current_call = {
            "tool_name": tool_name,
            "arguments": arguments_with_values,
            "timestamp": datetime.now().isoformat(),
        }

        is_repeated_call = (
            self.last_tool_call.get("tool_name") == current_call["tool_name"]
            and self.last_tool_call.get("arguments") == current_call["arguments"]
        )

        if is_repeated_call:
            repeat_count = self.last_tool_call.get("count", 0) + 1
            current_call["count"] = repeat_count
        else:
            current_call["count"] = 1

        self.last_tool_call = current_call
        return is_repeated_call and current_call.get("count", 0) >= 2

    def _handle_no_tool_usage(self) -> ObserveResponseResult:
        """Handle the case where no tool usage is found in the response.
        
        Returns:
            ObserveResponseResult with error message
        """
        return ObserveResponseResult(
            next_prompt="Error: No tool usage found in response.", executed_tool=None, answer=None
        )

    def _handle_tool_not_found(self, tool_name: str) -> ObserveResponseResult:
        """Handle the case where the tool is not found.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            ObserveResponseResult with error message
        """
        logger.warning(f"Tool '{tool_name}' not found in tool manager.")
        return ObserveResponseResult(
            next_prompt=f"Error: Tool '{tool_name}' not found in tool manager.",
            executed_tool="",
            answer=None,
        )

    def _handle_repeated_tool_call(self, tool_name: str, arguments_with_values: dict) -> tuple[str, str]:
        """Handle the case where a tool call is repeated.
        
        Args:
            tool_name: Name of the tool
            arguments_with_values: Tool arguments
            
        Returns:
            Tuple of (executed_tool_name, error_message)
        """
        repeat_count = self.last_tool_call.get("count", 0)
        error_message = self._render_template(
            'repeated_tool_call_error.j2',
            tool_name=tool_name,
            arguments_with_values=arguments_with_values,
            repeat_count=repeat_count
        )
        return tool_name, error_message

    def _handle_tool_execution_failure(self, response: str) -> ObserveResponseResult:
        """Handle the case where tool execution fails.
        
        Args:
            response: Error response
            
        Returns:
            ObserveResponseResult with error message
        """
        return ObserveResponseResult(
            next_prompt=response,
            executed_tool="",
            answer=None,
        )

    def _handle_error(self, error: Exception) -> ObserveResponseResult:
        """Handle any exceptions that occur during response observation.
        
        Args:
            error: Exception that occurred
            
        Returns:
            ObserveResponseResult with error message
        """
        logger.error(f"Error in _observe_response: {str(error)}")
        return ObserveResponseResult(
            next_prompt=f"An error occurred while processing the response: {str(error)}",
            executed_tool=None,
            answer=None,
        )

    def _format_observation_response(
        self, response: str, last_executed_tool: str, variable_name: str, iteration: int
    ) -> str:
        """Format the observation response with the given response, variable name, and iteration.
        
        Args:
            response: Tool execution response
            last_executed_tool: Name of last executed tool
            variable_name: Name of variable storing response
            iteration: Current iteration number
            
        Returns:
            Formatted observation response
        """
        response_display = response
        if len(response) > MAX_RESPONSE_LENGTH:
            response_display = response[:MAX_RESPONSE_LENGTH]
            response_display += (
                f"... content was truncated full content available by interpolation in variable {variable_name}"
            )

        tools_prompt = self._get_tools_names_prompt()
        variables_prompt = self._get_variable_prompt()
        
        formatted_response = self._render_template(
            'observation_response_format.j2',
            iteration=iteration,
            max_iterations=self.max_iterations,
            task_to_solve_summary=self.task_to_solve_summary,
            tools_prompt=tools_prompt,
            variables_prompt=variables_prompt,
            last_executed_tool=last_executed_tool,
            variable_name=variable_name,
            response_display=response_display
        )

        return formatted_response

    def _prepare_prompt_task(self, task: str) -> str:
        """Prepare the initial prompt for the task.

        Args:
            task: The task description

        Returns:
            The formatted task prompt
        """
        tools_prompt = self._get_tools_names_prompt()
        variables_prompt = self._get_variable_prompt()
        
        prompt_task = self._render_template(
            'task_prompt.j2',
            task=task,
            tools_prompt=tools_prompt,
            variables_prompt=variables_prompt
        )
        return prompt_task

    def _get_tools_names_prompt(self) -> str:
        """Construct a detailed prompt that lists the available tools for task execution.
        
        Returns:
            Formatted tools prompt
        """
        tool_names = ', '.join(self.tools.tool_names())
        return self._render_template('tools_prompt.j2', tool_names=tool_names)

    def _get_variable_prompt(self) -> str:
        """Construct a prompt that explains how to use variables.
        
        Returns:
            Formatted variables prompt
        """
        variable_names = ', '.join(self.variable_store.keys()) if len(self.variable_store.keys()) > 0 else "None"
        return self._render_template('variables_prompt.j2', variable_names=variable_names)

    def _calculate_context_occupancy(self) -> float:
        """Calculate the number of tokens in percentages for prompt and completion.
        
        Returns:
            Percentage of context window occupied
        """
        total_tokens = self.total_tokens
        max_tokens = self.model.get_model_max_input_tokens()

        if max_tokens is None or max_tokens <= 0:
            logger.warning(f"Invalid max tokens value: {max_tokens}. Using default of {DEFAULT_MAX_INPUT_TOKENS}.")
            max_tokens = DEFAULT_MAX_INPUT_TOKENS

        return round((total_tokens / max_tokens) * 100, 2)

    def _update_session_memory(self, user_content: str, assistant_content: str) -> None:
        """Log session messages to memory and emit events.

        Args:
            user_content: The user's content
            assistant_content: The assistant's content
        """
        self.memory.add(Message(role="user", content=user_content))
        self._emit_event("session_add_message", {"role": "user", "content": user_content})

        self.memory.add(Message(role="assistant", content=assistant_content))
        self._emit_event("session_add_message", {"role": "assistant", "content": assistant_content})

    def update_model(self, new_model_name: str) -> None:
        """Update the model name and recreate the model instance.
        
        Args:
            new_model_name: New model name to use
        """
        self.model_name = new_model_name
        self.model = GenerativeModel(model=new_model_name, event_emitter=self.event_emitter)

    def add_tool(self, tool: Tool) -> None:
        """Add a new tool to the agent's tool manager.
        
        Args:
            tool: The tool instance to add
            
        Raises:
            ValueError: If a tool with the same name already exists
        """
        if tool.name in self.tools.tool_names():
            raise ValueError(f"Tool with name '{tool.name}' already exists")
            
        self.tools.add(tool)
        # Update tools markdown in config
        self.config = AgentConfig(
            environment_details=self.config.environment_details,
            tools_markdown=self.tools.to_markdown(),
            system_prompt=self.config.system_prompt,
        )
        logger.debug(f"Added tool: {tool.name}")
        
    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool from the agent's tool manager.
        
        Args:
            tool_name: Name of the tool to remove
            
        Raises:
            ValueError: If tool doesn't exist or is TaskCompleteTool
        """
        if tool_name not in self.tools.tool_names():
            raise ValueError(f"Tool '{tool_name}' does not exist")
            
        tool = self.tools.get(tool_name)
        if isinstance(tool, TaskCompleteTool):
            raise ValueError("Cannot remove TaskCompleteTool as it is required")
            
        self.tools.remove(tool_name)
        # Update tools markdown in config
        self.config = AgentConfig(
            environment_details=self.config.environment_details,
            tools_markdown=self.tools.to_markdown(),
            system_prompt=self.config.system_prompt,
        )
        logger.debug(f"Removed tool: {tool_name}")
        
    def set_tools(self, tools: list[Tool]) -> None:
        """Set/replace all tools for the agent.
        
        Args:
            tools: List of tool instances to set
            
        Note:
            TaskCompleteTool will be automatically added if not present
        """
        # Ensure TaskCompleteTool is present
        if not any(isinstance(t, TaskCompleteTool) for t in tools):
            tools.append(TaskCompleteTool())
            
        # Create new tool manager and add tools
        tool_manager = ToolManager()
        tool_manager.add_list(tools)
        self.tools = tool_manager
        
        # Update config with new tools markdown
        self.config = AgentConfig(
            environment_details=self.config.environment_details,
            tools_markdown=self.tools.to_markdown(),
            system_prompt=self.config.system_prompt,
        )
        logger.debug(f"Set {len(tools)} tools")
        
    def _render_template(self, template_name: str, **kwargs) -> str:
        """Render a Jinja2 template with the provided variables.
        
        Args:
            template_name: Name of the template file (without directory path)
            **kwargs: Variables to pass to the template
            
        Returns:
            str: The rendered template
        """
        try:
            # Get the directory where this file is located
            current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            
            # Set up Jinja2 environment
            template_dir = current_dir / 'prompts'
            env = Environment(loader=FileSystemLoader(template_dir))
            
            # Load the template
            template = env.get_template(template_name)
            
            # Render the template with the provided variables
            return template.render(**kwargs)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {str(e)}")
            raise