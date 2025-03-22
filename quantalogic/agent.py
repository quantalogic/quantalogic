"""Enhanced QuantaLogic agent implementing the ReAct framework with optional chat mode."""

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

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
import uuid

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
    """Enhanced QuantaLogic agent supporting both ReAct goal-solving and conversational chat modes.

    Use `solve_task`/`async_solve_task` for goal-oriented ReAct mode (backward compatible).
    Use `chat`/`async_chat` for conversational mode with a customizable persona.

    Supports both synchronous and asynchronous operations. Use synchronous methods for CLI tools
    and asynchronous methods for web servers or async contexts.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True, extra="forbid")

    specific_expertise: str
    model: GenerativeModel
    memory: AgentMemory = AgentMemory()  # List of User/Assistant Messages
    variable_store: VariableMemory = VariableMemory()  # Dictionary of variables
    tools: ToolManager = ToolManager()
    event_emitter: EventEmitter = EventEmitter()
    config: AgentConfig
    task_to_solve: str
    task_to_solve_summary: str = ""
    ask_for_user_validation: Callable[[str, str], bool] = console_ask_for_user_validation
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
    chat_system_prompt: str  # Base persona prompt for chat mode
    tool_mode: Optional[str] = None  # Tool or toolset to prioritize in chat mode
    tracked_files: list[str] = []  # List to track files created or modified during execution
    agent_mode: str = "react"  # Default mode is ReAct

    def __init__(
        self,
        model_name: str = "",
        memory: AgentMemory = AgentMemory(),
        variable_store: VariableMemory = VariableMemory(),
        tools: list[Tool] = [TaskCompleteTool()],
        ask_for_user_validation: Callable[[str, str], bool] = console_ask_for_user_validation,
        task_to_solve: str = "",
        specific_expertise: str = "General AI assistant with coding and problem-solving capabilities",
        get_environment: Callable[[], str] = get_environment,
        compact_every_n_iterations: int | None = None,
        max_tokens_working_memory: int | None = None,
        event_emitter: EventEmitter | None = None,
        chat_system_prompt: str | None = None,
        tool_mode: Optional[str] = None,
        agent_mode: str = "react",
    ):
        """Initialize the agent with model, memory, tools, and configurations.

        Args:
            model_name: Name of the model to use
            memory: AgentMemory instance for storing conversation history
            variable_store: VariableMemory instance for storing variables
            tools: List of Tool instances
            ask_for_user_validation: Function to ask for user validation
            task_to_solve: Initial task to solve (for ReAct mode)
            specific_expertise: Description of the agent's expertise
            get_environment: Function to get environment details
            compact_every_n_iterations: How often to compact memory
            max_tokens_working_memory: Maximum token count for working memory
            event_emitter: EventEmitter instance for event handling
            chat_system_prompt: Optional base system prompt for chat mode persona
            tool_mode: Optional tool or toolset to prioritize in chat mode
            agent_mode: Mode to use ("react" or "chat")
        """
        try:
            logger.debug("Initializing agent...")

            if event_emitter is None:
                event_emitter = EventEmitter()

            if not any(isinstance(t, TaskCompleteTool) for t in tools):
                tools.append(TaskCompleteTool())

            tool_manager = ToolManager(tools={tool.name: tool for tool in tools})
            environment = get_environment()
            logger.debug(f"Environment details: {environment}")
            tools_markdown = tool_manager.to_markdown()
            logger.debug(f"Tools Markdown: {tools_markdown}")

            logger.info(f"Agent mode: {agent_mode}")
            system_prompt_text = system_prompt(
                tools=tools_markdown, environment=environment, expertise=specific_expertise, agent_mode=agent_mode
            )
            logger.debug(f"System prompt: {system_prompt_text}")

            config = AgentConfig(
                environment_details=environment,
                tools_markdown=tools_markdown,
                system_prompt=system_prompt_text,
            )

            chat_system_prompt = chat_system_prompt or specific_expertise or (
                "You are a friendly, helpful AI assistant. Engage in natural conversation, "
                "answer questions, and use tools when explicitly requested or when they enhance your response."
            )

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
                chat_system_prompt=chat_system_prompt,
                tool_mode=tool_mode,
                agent_mode=agent_mode,
            )

            self._model_name = model_name

            logger.debug(f"Memory will be compacted every {self.compact_every_n_iterations} iterations")
            logger.debug(f"Max tokens for working memory set to: {self.max_tokens_working_memory}")
            logger.debug(f"Tool mode set to: {self.tool_mode}")
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
                    )

                content = result.response
                if not streaming:
                    token_usage = result.usage
                    self.total_tokens = token_usage.total_tokens

                self._emit_event("task_think_end", {"response": content})
                result = await self._async_observe_response(content, iteration=self.current_iteration)
                current_prompt = result.next_prompt

                if result.executed_tool == "task_complete":
                    self._emit_event("task_complete", {
                        "response": result.answer,
                        "message": "Task execution completed",
                        "tracked_files": self.tracked_files if self.tracked_files else []
                    })
                    answer = result.answer or ""
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

        task_solve_end_data = {
            "result": answer,
            "message": "Task execution completed",
            "tracked_files": self.tracked_files if self.tracked_files else []
        }
        self._emit_event("task_solve_end", task_solve_end_data)
        return answer

    def chat(
        self,
        message: str,
        streaming: bool = False,
        clear_memory: bool = False,
        auto_tool_call: bool = True,
    ) -> str:
        """Engage in a conversational chat with the user (synchronous version).

        Ideal for synchronous applications. For asynchronous contexts, use `async_chat`.

        Args:
            message: The user's input message
            streaming: Whether to stream the response
            clear_memory: Whether to clear memory before starting
            auto_tool_call: Whether to automatically execute detected tool calls and interpret results

        Returns:
            The assistant's response
        """
        logger.debug(f"Chatting synchronously with message: {message}, auto_tool_call: {auto_tool_call}")
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.async_chat(message, streaming, clear_memory, auto_tool_call))

    async def async_chat(
        self,
        message: str,
        streaming: bool = False,
        clear_memory: bool = False,
        auto_tool_call: bool = True,
    ) -> str:
        """Engage in a conversational chat with the user (asynchronous version).

        Ideal for asynchronous applications. For synchronous contexts, use `chat`.

        Args:
            message: The user's input message
            streaming: Whether to stream the response
            clear_memory: Whether to clear memory before starting
            auto_tool_call: Whether to automatically execute detected tool calls and interpret results

        Returns:
            The assistant's response
        """
        logger.debug(f"Chatting asynchronously with message: {message}, auto_tool_call: {auto_tool_call}")
        if clear_memory:
            self.clear_memory()

        # Prepare chat system prompt with tool information
        tools_prompt = self._get_tools_names_prompt()
        logger.debug(tools_prompt)
        if self.tool_mode:
            tools_prompt += f"\nPrioritized tool mode: {self.tool_mode}. Prefer tools related to {self.tool_mode} when applicable."

        full_chat_prompt = self._render_template(
            'chat_system_prompt.j2',
            persona=self.chat_system_prompt,
            tools_prompt=tools_prompt
        )

        if not self.memory.memory or self.memory.memory[0].role != "system":
            self.memory.add(Message(role="system", content=full_chat_prompt))

        self._emit_event("chat_start", {"message": message})

        # Add user message to memory
        self.memory.add(Message(role="user", content=message))
        self._update_total_tokens(self.memory.memory, "")

        # Iterative tool usage with auto-execution
        current_prompt = message
        response_content = ""
        max_tool_iterations = 5  # Prevent infinite tool loops
        tool_iteration = 0

        while tool_iteration < max_tool_iterations:
            try:
                if streaming:
                    content = ""
                    # When streaming is enabled, the GenerativeModel._async_stream_response method
                    # already emits the stream_chunk events, so we don't need to emit them again here
                    async_stream = await self.model.async_generate_with_history(
                        messages_history=self.memory.memory,
                        prompt=current_prompt,
                        streaming=True,
                    )
                    # Just collect the chunks without re-emitting events
                    async for chunk in async_stream:
                        content += chunk
                    response = ResponseStats(
                        response=content,
                        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                        model=self.model.model,
                        finish_reason="stop",
                    )
                else:
                    response = await self.model.async_generate_with_history(
                        messages_history=self.memory.memory,
                        prompt=current_prompt,
                        streaming=False,
                    )
                    content = response.response

                self.total_tokens = response.usage.total_tokens if not streaming else self.total_tokens

                # Observe response for tool calls
                observation = await self._async_observe_response(content)
                if observation.executed_tool and auto_tool_call:
                    # Tool was executed; process result and continue
                    current_prompt = observation.next_prompt
                    
                    # In chat mode, format the response with clear tool call visualization
                    if not self.task_to_solve.strip():  # We're in chat mode
                        # Format the response to clearly show the tool call and result
                        # Use a format that task_runner.py can parse and display nicely
                        
                        # For a cleaner look, insert a special delimiter that task_runner.py can recognize
                        # to separate tool call from result
                        response_content = f"{content}\n\n__TOOL_RESULT_SEPARATOR__{observation.executed_tool}__\n{observation.next_prompt}"
                    else:
                        # In task mode, keep the original behavior
                        response_content = observation.next_prompt
                    
                    tool_iteration += 1
                    self.memory.add(Message(role="assistant", content=content))  # Original tool call
                    self.memory.add(Message(role="user", content=observation.next_prompt))  # Tool result
                    logger.debug(f"Tool executed: {observation.executed_tool}, iteration: {tool_iteration}")
                elif not observation.executed_tool and "<action>" in content and auto_tool_call:
                    # Detected malformed tool call attempt; provide feedback and exit loop
                    response_content = (
                        f"{content}\n\n⚠️ Error: Invalid tool call format detected. "
                        "Please use the exact XML structure as specified in the system prompt:\n"
                        "```xml\n<action>\n<tool_name>\n  <parameter_name>value</parameter_name>\n</tool_name>\n</action>\n```"
                    )
                    break
                else:
                    # No tool executed or auto_tool_call is False; final response
                    response_content = content
                    break

            except Exception as e:
                logger.error(f"Error during async chat: {str(e)}")
                response_content = f"Error: {str(e)}"
                break

        self._update_session_memory(message, response_content)
        self._emit_event("chat_response", {"response": response_content})
        return response_content


    def chat_news_specific(
        self,
        message: str,
        streaming: bool = False,
        clear_memory: bool = False,
        auto_tool_call: bool = True,
    ) -> str:
        """Engage in a conversational chat_news_specific with the user (synchronous version).

        Ideal for synchronous applications. For asynchronous contexts, use `async_chat_news_specific`.

        Args:
            message: The user's input message
            streaming: Whether to stream the response
            clear_memory: Whether to clear memory before starting
            auto_tool_call: Whether to automatically execute detected tool calls and interpret results

        Returns:
            The assistant's response
        """
        logger.debug(f"chat_news_specificting synchronously with message: {message}, auto_tool_call: {auto_tool_call}")
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.async_chat_news_specific(message, streaming, clear_memory, auto_tool_call))

    async def async_chat_news_specific(
        self,
        message: str,
        streaming: bool = False,
        clear_memory: bool = False,
        auto_tool_call: bool = True,
    ) -> str:
        """Engage in a conversational chat with the user (asynchronous version).

        Ideal for asynchronous applications. For synchronous contexts, use `chat`.

        Args:
            message: The user's input message
            streaming: Whether to stream the response
            clear_memory: Whether to clear memory before starting
            auto_tool_call: Whether to automatically execute detected tool calls and interpret results

        Returns:
            The assistant's response
        """
        logger.debug(f"Chatting asynchronously with message: {message}, auto_tool_call: {auto_tool_call}")
        if clear_memory:
            self.clear_memory()

        # Prepare chat system prompt with tool information
        tools_prompt = self._get_tools_names_prompt()
        logger.debug(tools_prompt)
        if self.tool_mode:
            tools_prompt += f"\nPrioritized tool mode: {self.tool_mode}. Prefer tools related to {self.tool_mode} when applicable."

        full_chat_prompt = self._render_template(
            'chat_system_prompt.j2',
            persona=self.chat_system_prompt,
            tools_prompt=tools_prompt
        )

        if not self.memory.memory or self.memory.memory[0].role != "system":
            self.memory.add(Message(role="system", content=full_chat_prompt))

        self._emit_event("chat_start", {"message": message})

        # Add user message to memory
        self.memory.add(Message(role="user", content=message))
        self._update_total_tokens(self.memory.memory, "")

        # Iterative tool usage with auto-execution
        current_prompt = message
        response_content = ""
        max_tool_iterations = 5  # Prevent infinite tool loops
        tool_iteration = 0

        while tool_iteration < max_tool_iterations:
            try:
                if streaming:
                    content = ""
                    # When streaming is enabled, the GenerativeModel._async_stream_response method
                    # already emits the stream_chunk events, so we don't need to emit them again here
                    async_stream = await self.model.async_generate_with_history(
                        messages_history=self.memory.memory,
                        prompt=current_prompt,
                        streaming=True,
                    )
                    # Just collect the chunks without re-emitting events
                    async for chunk in async_stream:
                        content += chunk
                    response = ResponseStats(
                        response=content,
                        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                        model=self.model.model,
                        finish_reason="stop",
                    )
                else:
                    response = await self.model.async_generate_with_history(
                        messages_history=self.memory.memory,
                        prompt=current_prompt,
                        streaming=False,
                    )
                    content = response.response

                self.total_tokens = response.usage.total_tokens if not streaming else self.total_tokens

                # Observe response for tool calls
                observation = await self._async_observe_response(content)
                if observation.executed_tool and auto_tool_call: 
                    print("observation.executed_tool : ", observation.executed_tool)
                    # If any news tool is used, return immediately
                    if "googlenews" in observation.executed_tool.lower() or \
                       "duckduckgo" in observation.executed_tool.lower() or \
                       "duckduckgosearch" in observation.executed_tool.lower(): 
                        self._emit_event("chat_response", {"response": observation.next_prompt})
                        return observation.next_prompt
                    # Tool was executed; process result and continue
                    current_prompt = observation.next_prompt
                    
                    # In chat mode, format the response with clear tool call visualization
                    if not self.task_to_solve.strip():  # We're in chat mode
                        # Format the response to clearly show the tool call and result
                        # Use a format that task_runner.py can parse and display nicely
                        
                        # For a cleaner look, insert a special delimiter that task_runner.py can recognize
                        # to separate tool call from result
                        response_content = f"{content}\n\n__TOOL_RESULT_SEPARATOR__{observation.executed_tool}__\n{observation.next_prompt}"
                    else:
                        # In task mode, keep the original behavior
                        response_content = observation.next_prompt
                    
                    tool_iteration += 1
                    self.memory.add(Message(role="assistant", content=content))  # Original tool call
                    self.memory.add(Message(role="user", content=observation.next_prompt))  # Tool result
                    logger.debug(f"Tool executed: {observation.executed_tool}, iteration: {tool_iteration}")
                elif not observation.executed_tool and "<action>" in content and auto_tool_call:
                    # Detected malformed tool call attempt; provide feedback and exit loop
                    response_content = (
                        f"{content}\n\n⚠️ Error: Invalid tool call format detected. "
                        "Please use the exact XML structure as specified in the system prompt:\n"
                        "```xml\n<action>\n<tool_name>\n  <parameter_name>value</parameter_name>\n</tool_name>\n</action>\n```"
                    )
                    break
                else:
                    # No tool executed or auto_tool_call is False; final response
                    response_content = content
                    break

            except Exception as e:
                logger.error(f"Error during async chat: {str(e)}")
                response_content = f"Error: {str(e)}"
                break

        self._update_session_memory(message, response_content)
        self._emit_event("chat_response", {"response": response_content})
        return response_content



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
            # Detect if we're in chat mode by checking if task_to_solve is empty
            is_chat_mode = not self.task_to_solve.strip()
            
            # Use specialized chat mode observation method if in chat mode
            if is_chat_mode:
                return await self._async_observe_response_chat(content, iteration)

            # Parse content for tool usage
            parsed_content = self._parse_tool_usage(content)
            if not parsed_content:
                logger.debug("No tool usage detected in response")
                return ObserveResponseResult(next_prompt=content, executed_tool=None, answer=None)

            # Process tools for regular ReAct mode
            tool_names = list(parsed_content.keys())
            for tool_name in tool_names:
                if tool_name not in parsed_content:
                    continue
                tool_input = parsed_content[tool_name]
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

                # Track files when write_file_tool or writefile is used
                if (tool_name in ["write_file_tool", "writefile", "edit_whole_content", "replace_in_file", "replaceinfile", "EditWholeContent"]) and "file_path" in arguments_with_values:
                    self._track_file(arguments_with_values["file_path"], tool_name)

                variable_name = self.variable_store.add(response)
                new_prompt = self._format_observation_response(response, executed_tool, variable_name, iteration)

                # In chat mode, don't set answer; in task mode, set answer only for task_complete
                is_task_complete_answer = executed_tool == "task_complete" and not is_chat_mode
                
                return ObserveResponseResult(
                    next_prompt=new_prompt,
                    executed_tool=executed_tool,
                    answer=response if is_task_complete_answer else None,
                )

            # If no tools were executed, return original content
            return ObserveResponseResult(next_prompt=content, executed_tool=None, answer=None)

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
            logger.info(f"Tool '{tool_name}' requires validation.")
            validation_id = str(uuid.uuid4())
            logger.info(f"Validation ID: {validation_id}")
            
            self._emit_event(
                "tool_execute_validation_start",
                {
                    "validation_id": validation_id,
                    "tool_name": tool_name, 
                    "arguments": arguments_with_values
                },
            )
            question_validation = (
                "Do you permit the execution of this tool?\n"
                f"Tool: {tool_name}\nArguments:\n"
                "<arguments>\n"
                + "\n".join([f"    <{key}>{value}</{key}>" for key, value in arguments_with_values.items()])
                + "\n</arguments>\nYes or No"
            )
            permission_granted = await self.ask_for_user_validation(validation_id, question_validation)

            self._emit_event(
                "tool_execute_validation_end",
                {
                    "validation_id": validation_id,
                    "tool_name": tool_name,
                    "arguments": arguments_with_values,
                    "granted": permission_granted
                },
            )

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
                response = tool.execute(**converted_args)
                
            # Post-process tool response if needed
            if (tool.need_post_process):
                response = self._post_process_tool_response(tool_name, response) 
                    
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

            for var in self.variable_store.keys():
                escaped_var = re.escape(var).replace('\\$', '$')
                pattern = f"\\${escaped_var}\\$"
                replacement = str(self.variable_store[var])
                text = re.sub(pattern, lambda m: replacement, text)

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
        memory_copy = self.memory.memory.copy()

        if len(memory_copy) < 3:
            logger.warning("Not enough messages to compact memory with summary")
            return "Memory compaction skipped: not enough messages"

        user_message = memory_copy.pop()
        assistant_message = memory_copy.pop()

        prompt_summary = self._render_template('memory_compaction_prompt.j2',
                                             conversation_history="\n\n".join(
                                                 f"[{msg.role.upper()}]: {msg.content}"
                                                 for msg in memory_copy
                                             ))

        summary = await self.model.async_generate_with_history(messages_history=memory_copy, prompt=prompt_summary)

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
            tool_data = xml_parser.extract_elements(text=action["action"], element_names=tool_names)
            # Handle nested parameters within action tags
            for tool_name in tool_data:
                if "<parameter_name>" in tool_data[tool_name]:
                    params = xml_parser.extract_elements(text=tool_data[tool_name], element_names=["parameter_name", "parameter_value"])
                    if "parameter_name" in params and "parameter_value" in params:
                        tool_data[tool_name] = {params["parameter_name"]: params["parameter_value"]}
            return tool_data
        else:
            return xml_parser.extract_elements(text=content, element_names=tool_names)

    def _parse_tool_arguments(self, tool: Tool, tool_input: str | dict) -> dict:
        """Parse the tool arguments from the tool input.

        Args:
            tool: Tool instance
            tool_input: Raw tool input text or pre-parsed dict

        Returns:
            Dictionary of parsed arguments
        """
        if isinstance(tool_input, dict):
            return tool_input  # Already parsed from XML
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
        
    async def _async_observe_response_chat(self, content: str, iteration: int = 1) -> ObserveResponseResult:
        """Specialized observation method for chat mode with tool handling.

        This method processes responses in chat mode, identifying and executing tool calls
        while providing appropriate default parameters when needed. Prevents task_complete usage.

        Args:
            content: The response content to analyze
            iteration: Current iteration number

        Returns:
            ObserveResponseResult with next steps information
        """
        try:
            # Check for tool call patterns in the content
            if "<action>" not in content:
                logger.debug("No tool usage detected in chat response")
                return ObserveResponseResult(next_prompt=content, executed_tool=None, answer=None)
                
            # Parse content for tool usage
            parsed_content = self._parse_tool_usage(content)
            if not parsed_content:
                # Malformed tool call in chat mode; return feedback
                error_prompt = (
                    "⚠️ Error: Invalid tool call format detected. "
                    "Please use the exact XML structure:\n"
                    "```xml\n<action>\n<tool_name>\n  <parameter_name>value</parameter_name>\n</tool_name>\n</action>\n```"
                )
                return ObserveResponseResult(next_prompt=error_prompt, executed_tool=None, answer=None)

            # Check for task_complete attempt and block it with feedback
            if "task_complete" in parsed_content:
                feedback = (
                    "⚠️ Note: The 'task_complete' tool is not available in chat mode. "
                    "This is a conversational mode; tasks are not completed here. "
                    "Please use other tools or continue the conversation."
                )
                return ObserveResponseResult(next_prompt=feedback, executed_tool=None, answer=None)

            # Process tools with prioritization based on tool_mode
            tool_names = list(parsed_content.keys())
            # Prioritize specific tools if tool_mode is set and the tool is available
            if self.tool_mode and self.tool_mode in self.tools.tool_names() and self.tool_mode in tool_names:
                tool_names = [self.tool_mode] + [t for t in tool_names if t != self.tool_mode]

            for tool_name in tool_names:
                if tool_name not in parsed_content:
                    continue
                    
                tool_input = parsed_content[tool_name]
                tool = self.tools.get(tool_name)
                if not tool:
                    return self._handle_tool_not_found(tool_name)

                # Parse tool arguments from the input
                arguments_with_values = self._parse_tool_arguments(tool, tool_input)
                
                # Apply default parameters based on tool schema if missing
                self._apply_default_parameters(tool, arguments_with_values)
                
                # Check for repeated calls
                is_repeated_call = self._is_repeated_tool_call(tool_name, arguments_with_values)
                if is_repeated_call:
                    executed_tool, response = self._handle_repeated_tool_call(tool_name, arguments_with_values)
                else:
                    executed_tool, response = await self._async_execute_tool(tool_name, tool, arguments_with_values)
                
                if not executed_tool:
                    # Tool execution failed
                    return self._handle_tool_execution_failure(response)
                
                # Store result in variable memory for potential future reference
                variable_name = f"result_{executed_tool}_{iteration}"
                self.variable_store[variable_name] = response
                
                # Truncate response if too long for display
                response_display = response
                if len(response) > MAX_RESPONSE_LENGTH:
                    response_display = response[:MAX_RESPONSE_LENGTH]
                    response_display += f"... (truncated, full content available in ${variable_name})"
                
                # Format result in a user-friendly way
                return ObserveResponseResult(
                    next_prompt=response_display,
                    executed_tool=executed_tool,
                    answer=None
                )
                
            # If we get here, no tool was successfully executed
            return ObserveResponseResult(
                next_prompt="I tried to use a tool, but encountered an issue. Please try again with a different request.",
                executed_tool=None,
                answer=None
            )
                
        except Exception as e:
            return self._handle_error(e)
            
    def _apply_default_parameters(self, tool: Tool, arguments_with_values: dict) -> None:
        """Apply default parameters to tool arguments based on tool schema.
        
        This method examines the tool's schema and fills in any missing required parameters
        with sensible defaults based on the tool type.
        
        Args:
            tool: The tool instance
            arguments_with_values: Dictionary of current arguments
        """
        try:
            # Add defaults for common search tools
            if tool.name == "duckduckgo_tool" and "max_results" not in arguments_with_values:
                logger.debug(f"Adding default max_results=5 for {tool.name}")
                arguments_with_values["max_results"] = "5"
                
            # Check tool schema for required parameters
            if hasattr(tool, "schema") and hasattr(tool.schema, "parameters"):
                for param_name, param_info in tool.schema.parameters.items():
                    # If required parameter is missing, try to add a default
                    if param_info.get("required", False) and param_name not in arguments_with_values:
                        if "default" in param_info:
                            logger.debug(f"Adding default value for {param_name} in {tool.name}")
                            arguments_with_values[param_name] = param_info["default"]
        except Exception as e:
            logger.debug(f"Error applying default parameters: {str(e)}")
            # Continue without defaults rather than failing the whole operation
            
    def _post_process_tool_response(self, tool_name: str, response: Any) -> str:
        """Process tool response for better presentation to the user.
        
        This generic method handles common tool response formats:
        - Parses JSON strings into structured data
        - Formats search results into readable text
        - Handles different response types appropriately
        
        Args:
            tool_name: Name of the tool that produced the response
            response: Raw tool response
            
        Returns:
            Processed response as a string
        """
        # Immediately return if response is not a string
        if not isinstance(response, str):
            return response
            
        # Try to parse as JSON if it looks like JSON
        if response.strip().startswith(("{" , "[")) and response.strip().endswith(("}", "]")):
            try:
                # Use lazy import for json to maintain dependency structure
                import json
                parsed = json.loads(response)
                
                # Handle list-type responses (common for search tools)
                if isinstance(parsed, list) and parsed:
                    # Detect if this is a search result by checking for common fields
                    search_result_fields = ['title', 'href', 'url', 'body', 'content', 'snippet']
                    if isinstance(parsed[0], dict) and any(field in parsed[0] for field in search_result_fields):
                        # Format as search results
                        formatted_results = []
                        for idx, result in enumerate(parsed, 1):
                            if not isinstance(result, dict):
                                continue
                                
                            # Extract common fields with fallbacks
                            title = result.get('title', 'No title')
                            url = result.get('href', result.get('url', 'No link'))
                            description = result.get('body', result.get('content', 
                                             result.get('snippet', result.get('description', 'No description'))))
                                
                            formatted_results.append(f"{idx}. {title}\n   URL: {url}\n   {description}\n")
                            
                        if formatted_results:
                            return "\n".join(formatted_results)
                
                # If not handled as a special case, just pretty-print
                return json.dumps(parsed, indent=2, ensure_ascii=False)
                
            except json.JSONDecodeError:
                # Not valid JSON after all
                pass
                
        # Return original response if no special handling applies
        return response

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
        # Check if we're in chat mode
        is_chat_mode = not self.task_to_solve.strip()
        
        if is_chat_mode:
            return self._get_tools_names_prompt_for_chat()
        
        # Default task mode behavior
        tool_names = ', '.join(self.tools.tool_names())
        return self._render_template('tools_prompt.j2', tool_names=tool_names)
        
    def _get_tools_names_prompt_for_chat(self) -> str:
        """Construct a detailed prompt for chat mode that includes tool parameters, excluding task_complete.
        
        Returns:
            Formatted tools prompt with parameter details
        """
        tool_descriptions = []
        
        try:
            for tool_name in self.tools.tool_names():
                if tool_name == "task_complete":
                    continue  # Explicitly exclude task_complete in chat mode
                
                try:
                    tool = self.tools.get(tool_name)
                    params = []
                    
                    # Get parameter details if available
                    try:
                        if hasattr(tool, "schema") and hasattr(tool.schema, "parameters"):
                            schema_params = getattr(tool.schema, "parameters", {})
                            if isinstance(schema_params, dict):
                                for param_name, param_info in schema_params.items():
                                    if not isinstance(param_info, dict):
                                        continue
                                        
                                    required = "(required)" if param_info.get("required", False) else "(optional)"
                                    default = f" default: {param_info['default']}" if "default" in param_info else ""
                                    param_type = param_info.get("type", "string")
                                    param_desc = f"{param_name} ({param_type}) {required}{default}"
                                    params.append(param_desc)
                    except Exception as e:
                        logger.debug(f"Error parsing schema for {tool_name}: {str(e)}")

                    # Enhanced tool-specific parameter descriptions
                    if tool_name == "googlenews":
                        params = [
                            "query (string, required) - The search query string",
                            "language (string, optional) default: en - Language code (e.g., en, fr, es)",
                            "period (string, optional) default: 7d - Time period (1d, 7d, 30d)",
                            "max_results (integer, required) default: 5 - Number of results to return",
                            "country (string, optional) default: US - Country code (e.g., US, GB, FR)",
                            "sort_by (string, optional) default: relevance - Sort by (relevance, date)",
                            "analyze (boolean, optional) default: False - Whether to analyze results"
                        ]
                    elif tool_name == "duckduckgosearch":
                        params = [
                            "query (string, required) - The search query string",
                            "max_results (integer, required) default: 5 - Number of results to return",
                            "time_period (string, optional) default: d - Time period (d: day, w: week, m: month)",
                            "region (string, optional) default: wt-wt - Region code for search results"
                        ]
                    elif tool_name == "llm":
                        params = [
                            "system_prompt (string, required) - The persona or system prompt to guide the language model's behavior",
                            "prompt (string, required) - The question to ask the language model. Supports interpolation with $var$ syntax",
                            "temperature (float, required) default: 0.5 - Sampling temperature between 0.0 (no creativity) and 1.0 (full creativity)"
                        ]
                    elif tool_name == "task_complete":
                        params = [
                            "answer (string, required) - Your final answer or response to complete the task"
                        ]
                    elif "search" in tool_name.lower() and not params:
                        params.append("max_results (integer, optional) default: 5 - Number of results to return")

                    param_str = "\n  - ".join(params) if params else "No parameters required"
                    tool_descriptions.append(f"{tool_name}:\n  - {param_str}")
                except Exception as e:
                    logger.debug(f"Error processing tool {tool_name}: {str(e)}")
                    # Still include the tool in the list, but with minimal info
                    tool_descriptions.append(f"{tool_name}: Error retrieving parameters")
        except Exception as e:
            logger.debug(f"Error generating tool descriptions: {str(e)}")
            return "Error retrieving tool information"
            
        formatted_tools = "\n".join(tool_descriptions) if tool_descriptions else "No tools available."
        return formatted_tools

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
        if not any(isinstance(t, TaskCompleteTool) for t in tools):
            tools.append(TaskCompleteTool())

        tool_manager = ToolManager()
        tool_manager.add_list(tools)
        self.tools = tool_manager

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
            current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            template_dir = current_dir / 'prompts'
            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {str(e)}")
            raise

    def _track_file(self, file_path: str, tool_name: str) -> None:
        """Track files created or modified by tools.
        
        Args:
            file_path: Path to the file to track
            tool_name: Name of the tool that created/modified the file
        """
        try:
            # Handle /tmp directory for write tools
            if tool_name in ["write_file_tool", "writefile", "edit_whole_content", "replace_in_file", "replaceinfile", "EditWholeContent"]:
                if not file_path.startswith("/tmp/"):
                    file_path = os.path.join("/tmp", file_path.lstrip("/"))
            
            # For other tools, ensure we have absolute path
            elif not os.path.isabs(file_path):
                file_path = os.path.abspath(os.path.join(os.getcwd(), file_path))
            
            # Resolve any . or .. in the path
            tracked_path = os.path.realpath(file_path)
            
            # For write tools, ensure path is in /tmp
            if tool_name in ["write_file_tool", "writefile"] and not tracked_path.startswith("/tmp/"):
                logger.warning(f"Attempted to track file outside /tmp: {tracked_path}")
                return
                
            # Add to tracked files if not already present
            if tracked_path not in self.tracked_files:
                self.tracked_files.append(tracked_path)
                logger.debug(f"Added {tracked_path} to tracked files")
                
        except Exception as e:
            logger.error(f"Error tracking file {file_path}: {str(e)}")