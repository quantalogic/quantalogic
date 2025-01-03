"""Enhanced QuantaLogic agent implementing the ReAct framework."""

import os
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict

from quantalogic.event_emitter import EventEmitter
from quantalogic.generative_model import GenerativeModel
from quantalogic.memory import AgentMemory, Message, VariableMemory
from quantalogic.prompts import system_prompt
from quantalogic.tool_manager import ToolManager
from quantalogic.tools.task_complete_tool import TaskCompleteTool
from quantalogic.tools.tool import Tool
from quantalogic.xml_parser import ToleranceXMLParser
from quantalogic.xml_tool_parser import ToolParser

# Configure logger based on environment variable
log_level = os.getenv("LOG_LEVEL", "ERROR")
logger.remove()
logger.add(sys.stderr, level=log_level)


# Maximum ratio occupancy of the occupied memory
MAX_OCCUPANCY = 90.0

# Maximum response length in characters
MAX_RESPONSE_LENGTH = 1024 * 32

DEFAULT_MAX_INPUT_TOKENS = 128 * 1024
DEFAULT_MAX_OUTPUT_TOKENS = 4096


def get_environment() -> str:
    """Retrieve the current environment details."""
    try:
        logger.debug("Retrieving environment details.")
        shell = os.getenv("SHELL", "bash")
        current_dir = os.getcwd()
        operating_system = os.name
        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        environment_details = (
            f"Current shell: {shell}\n"
            f"Current directory: {current_dir}\n"
            f"Operating system: {operating_system}\n"
            f"Date and time: {date_time}"
        )
        logger.debug(f"Environment details:\n{environment_details}")
        return environment_details
    except Exception as e:
        logger.error(f"Error retrieving environment details: {str(e)}")
        return "Environment details unavailable."


def default_ask_for_user_validation(question: str = "Do you want to continue?") -> bool:
    """Prompt the user for validation using Rich.

    Args:
        question (str): The validation question.

    Returns:
        bool: User's confirmation.
    """
    from rich.prompt import Confirm

    return Confirm.ask(question, default=True)


class AgentConfig(BaseModel):
    """Configuration settings for the Agent."""

    environment_details: str
    tools_markdown: str
    system_prompt: str


class ObserveResponseResult(BaseModel):
    """Represents the result of observing the assistant's response."""

    next_prompt: str
    executed_tool: str | None = None
    answer: str | None = None


class Agent(BaseModel):
    """Enhanced QuantaLogic agent implementing ReAct framework."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra='forbid'
    )

    specific_expertise: str
    model: GenerativeModel
    memory: AgentMemory = AgentMemory()
    variable_store: VariableMemory = VariableMemory()
    tools: ToolManager = ToolManager()
    event_emitter: EventEmitter = EventEmitter()
    config: AgentConfig
    task_to_solve: str
    ask_for_user_validation: Callable[[str], bool] = default_ask_for_user_validation
    last_tool_call: dict[str, Any] = {}  # Stores the last tool call information
    total_tokens: int = 0  # Total tokens in the conversation

    def __init__(
        self,
        model_name: str = "ollama/qwen2.5-coder:14b",
        memory: AgentMemory = AgentMemory(),
        tools: list[Tool] = [TaskCompleteTool()],
        ask_for_user_validation: Callable[[str], bool] = default_ask_for_user_validation,
        task_to_solve: str = "",
        specific_expertise: str = "General AI assistant with coding and problem-solving capabilities",
    ):
        """Initialize the agent with model, memory, tools, and configurations."""
        try:
            # Add TaskCompleteTool to the tools list if not already present
            if TaskCompleteTool() not in tools:
                tools.append(TaskCompleteTool())

            tool_manager = ToolManager(tools={tool.name: tool for tool in tools})
            environment = get_environment()
            tools_markdown = tool_manager.to_markdown()

            system_prompt_text = system_prompt(
                tools=tools_markdown, environment=environment, expertise=specific_expertise
            )

            config = AgentConfig(
                environment_details=environment,
                tools_markdown=tools_markdown,
                system_prompt=system_prompt_text,
            )

            super().__init__(
                model=GenerativeModel(model=model_name),
                memory=memory,
                variable_store=VariableMemory(),
                tools=tool_manager,
                config=config,
                ask_for_user_validation=ask_for_user_validation,
                task_to_solve=task_to_solve,
                specific_expertise=specific_expertise,
            )
            logger.info("Agent initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}")
            raise

    def solve_task(self, task: str, max_iterations: int = 30) -> str:
        """Solve the given task using the ReAct framework.

        Args:
            task (str): The task description.
            max_iterations (int, optional): Maximum number of iterations to attempt solving the task.
                Defaults to 30 to prevent infinite loops and ensure timely task completion.

        Returns:
            str: The final response after task completion.
        """
        self.task_to_solve = task
        content = ""
        task_prompt = self._prepare_prompt_task(task)

        self.memory.reset()
        self.variable_store.reset()
        self.total_tokens = 0

        # Add system prompt to memory
        self.memory.add(Message(role="system", content=self.config.system_prompt))

        self.event_emitter.emit(
            "session_start",
            {"system_prompt": self.config.system_prompt, "content": task},
        )

        max_output_tokens = self.model.get_model_max_output_tokens() or DEFAULT_MAX_OUTPUT_TOKENS
        max_input_tokens = self.model.get_model_max_input_tokens() or DEFAULT_MAX_INPUT_TOKENS

        done = False
        current_prompt = task_prompt

        current_iteration = 1

        # Emit event: Task Solve Start
        self.event_emitter.emit(
            "task_solve_start",
            {"iteration": current_iteration, "initial_prompt": current_prompt, "task": task},
        )

        answer: str = ""

        while not done:
            try:
                self.total_tokens = self.model.token_counter_with_history(self.memory.memory, prompt=current_prompt)
                # Emit event: Task Think Start
                self.event_emitter.emit(
                    "task_think_start",
                    {
                        "iteration": current_iteration,
                        "current_prompt": current_prompt,
                        "task": task,
                        "total_tokens": self.total_tokens,
                        "context_occupancy": self._calculate_context_occupancy(),
                        "max_input_tokens": max_input_tokens,
                        "max_output_tokens": max_output_tokens,
                    },
                )

                ratio_occupied = self._calculate_context_occupancy()
                if (ratio_occupied >= MAX_OCCUPANCY):
                    self.event_emitter.emit(
                        "memory_full",
                        {
                            "iteration": current_iteration,
                            "total_tokens": self.total_tokens,
                            "context_occupancy": self._calculate_context_occupancy(),
                            "max_input_tokens": max_input_tokens,
                            "max_output_tokens": max_output_tokens,
                        },
                    )
                    self.memory.compact()
                    self.total_tokens = self.model.token_counter_with_history(self.memory.memory, current_prompt)
                    self.event_emitter.emit(
                        "memory_compacted",
                        {
                            "iteration": current_iteration,
                            "total_tokens": self.total_tokens,
                            "context_occupancy": self._calculate_context_occupancy(),
                            "max_input_tokens": max_input_tokens,
                            "max_output_tokens": max_output_tokens,
                        },
                    )

                # Generate response from the model
                result = self.model.generate_with_history(messages_history=self.memory.memory, prompt=current_prompt)

                content = result.response
                token_usage = result.usage

                self.total_tokens = token_usage.total_tokens

                # Emit event: Task Think End
                self.event_emitter.emit(
                    "task_think_end",
                    {
                        "iteration": current_iteration,
                        "current_prompt": current_prompt,
                        "response": content,
                        "task": task,
                        "token_usage": token_usage,
                        "total_tokens": self.total_tokens,
                        "context_occupancy": self._calculate_context_occupancy(),
                        "max_input_tokens": max_input_tokens,
                        "max_output_tokens": max_output_tokens,
                    },
                )

                # Process the assistant's response
                result = self._observe_response(result.response, iteration=current_iteration)

                current_prompt = result.next_prompt

                if result.executed_tool == "task_complete":
                    self.event_emitter.emit(
                        "task_complete",
                        {
                            "iteration": current_iteration,
                            "current_prompt": current_prompt,
                            "task": task,
                            "total_tokens": self.total_tokens,
                            "max_input_tokens": max_input_tokens,
                            "context_occupancy": self._calculate_context_occupancy(),
                            "max_output_tokens": max_output_tokens,
                        },
                    )
                    answer = result.answer
                    done = True

                self.memory.add(Message(role="user", content=current_prompt))
                self.memory.add(Message(role="assistant", content=content))

                self.event_emitter.emit(
                    "session_add_message",
                    {"role": "user", "content": current_prompt},
                )
                self.event_emitter.emit(
                    "session_add_message",
                    {"role": "assistant", "content": content},
                )

                current_iteration += 1
                if current_iteration >= max_iterations:
                    done = True
                    self.event_emitter.emit(
                        "error_max_iterations_reached",
                        {
                            "iteration": current_iteration,
                            "current_prompt": current_prompt,
                            "task": task,
                            "total_tokens": self.total_tokens,
                            "max_input_tokens": max_input_tokens,
                            "context_occupancy": self._calculate_context_occupancy(),
                            "max_output_tokens": max_output_tokens,
                        },
                    )

            except Exception as e:
                logger.error(f"Error during task solving: {str(e)}")
                # Optionally, decide to continue or break based on exception type
                answer = f"Error: {str(e)}"
                done = True

        # Emit event: Task Solve End
        self.event_emitter.emit(
            "task_solve_end",
            {
                "iteration": current_iteration,
                "current_prompt": current_prompt,
                "task": task,
                "total_tokens": self.total_tokens,
                "context_occupancy": self._calculate_context_occupancy(),
                "max_input_tokens": max_input_tokens,
                "max_output_tokens": max_output_tokens,
            },
        )

        return answer

    def _observe_response(self, content: str, iteration: int = 1) -> ObserveResponseResult:
        """Analyze the assistant's response and determine next steps.

        Args:
            content (str): The assistant's response content.
            iteration (int, optional): The current iteration number of task solving.
                Helps track the progress and prevent infinite loops. Defaults to 1.

        Returns:
            ObserveResponseResult: A result indicating if the task is done and the next prompt.
        """
        try:
            xml_parser = ToleranceXMLParser()
            tool_names = self.tools.tool_names()
            executed_tool = ""

            # Extract tool usage from the response
            parsed_content = xml_parser.extract_elements(text=content, element_names=tool_names)

            for tool_name, tool_input in parsed_content.items():
                tool = self.tools.get(tool_name)
                if not tool:
                    logger.warning(f"Tool '{tool_name}' not found in tool manager.")
                    return ObserveResponseResult(
                        next_prompt=f"Error: Tool '{tool_name}' not found in tool manager.",
                        executed_tool="",
                        answer=None,
                    )

                tool_parser = ToolParser(tool=tool)
                arguments_with_values: dict[str, str] = tool_parser.parse(tool_input)

                # Check for consecutive identical tool calls
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
                    if repeat_count >= 2:
                        error_message = (
                            "Error: Detected repeated identical tool call pattern.\n"
                            f"Tool: {tool_name}\n"
                            f"Arguments: {arguments_with_values}\n"
                            f"Repeated {repeat_count} times\n\n"
                            "PLEASE:\n"
                            "1. Review your previous steps\n"
                            "2. Consider a different approach\n"
                            "3. Use a different tool or modify the arguments\n"
                            "4. Ensure you're making progress towards the goal"
                        )
                        logger.warning(f"Blocking repeated tool call: {tool_name}")
                        return ObserveResponseResult(
                            next_prompt=error_message,
                            executed_tool="",
                            answer=None,
                        )
                    
                    # Update repeat count
                    current_call["count"] = repeat_count
                else:
                    current_call["count"] = 1

                # Execute tool and store current call as last call
                executed_tool, response = self._execute_tool(tool_name, tool, arguments_with_values)
                self.last_tool_call = current_call

                if not executed_tool:
                    return ObserveResponseResult(
                        next_prompt=response,
                        executed_tool="",
                        answer=None,
                    )

                # Store the response in variable memory
                variable_name = self.variable_store.add(response)

                # Format the response
                new_prompt = self._format_observation_response(
                    response=response, variable_name=variable_name, iteration=iteration
                )

                return ObserveResponseResult(
                    next_prompt=new_prompt,
                    executed_tool=executed_tool,
                    answer=response if executed_tool == "task_complete" else None,
                )

            # No tool usage found
            return ObserveResponseResult(
                next_prompt="Error: No tool usage found in response.", executed_tool=None, answer=None
            )

        except Exception as e:
            logger.error(f"Error in _observe_response: {str(e)}")
            return ObserveResponseResult(
                next_prompt=f"An error occurred while processing the response: {str(e)}",
                executed_tool=None,
                answer=None,
            )

    def _format_observation_response(self, response: str, variable_name: str, iteration: int) -> str:
        """Format the observation response with the given response, variable name, and iteration."""
        response_display = response
        if len(response) > MAX_RESPONSE_LENGTH:
            response_display = response[:MAX_RESPONSE_LENGTH]
            response_display += (
                f"... content was trunctated full content available by interpolation in variable {variable_name}"
            )

        # Format the response message
        formatted_response = (
            "\n"
            f"--- Observations for iteration {iteration} ---\n"
            "\n"
            f"\n --- Tool execution result stored in variable ${variable_name}$ --- \n"
            "\n"
            f"<{variable_name}>\n{response_display}\n</{variable_name}>\n" + "\n"
            "\n"
            f"--- Tools --- \n"
            "\n"
            f"{self._get_tools_names_prompt()}"
            "\n"
            f"--- Variables --- \n"
            "\n"
            f"{self._get_variable_prompt()}"
            "\n"
            f"--- Task to solve --- \n"
            "\n"
            f"<task>\n{self.task_to_solve}\n</task>\n"
            "\n"
            "You must analyze this answer and evaluate what to do next.\n"
            "If the step failed, take a step back and rethink your approach.\n"
            "\n"
            "--- Format ---\n"
            "\n"
            "You MUST respond with exactly two XML blocks formatted in markdown:\n"
            "\n"
            " - One <thinking> block detailing your analysis,\n"
            " - One <tool_name> block specifying the chosen tool and its arguments, as outlined in the system prompt.\n"
        )

        return formatted_response

    def _execute_tool(self, tool_name: str, tool, arguments_with_values: dict) -> tuple[str, Any]:
        """Execute a tool with validation if required.

        Args:
            tool_name: Name of the tool to execute
            tool: Tool instance
            arguments_with_values: Dictionary of argument names and values

        Returns:
            tuple containing:
                - executed_tool name (str)
                - tool execution response (Any)
        """
        # Handle tool validation if required
        if tool.need_validation:
            logger.debug(f"Tool '{tool_name}' requires validation.")
            self.event_emitter.emit(
                "tool_execute_validation_start",
                {"tool_name": tool_name, "arguments": arguments_with_values},
            )

            question_validation: str = (
                "Do you permit the execution of this tool?"
                f"Tool: {tool_name}"
                f"Arguments: {arguments_with_values}"
                "Yes or No"
            ).join("\n")
            permission_granted = self.ask_for_user_validation(question_validation)

            self.event_emitter.emit(
                "tool_execute_validation_end",
                {"tool_name": tool_name, "arguments": arguments_with_values},
            )

            if not permission_granted:
                logger.debug(f"Execution of tool '{tool_name}' was denied by the user.")
                return "", f"Error: execution of tool '{tool_name}' was denied by the user."

        # Emit event: Tool Execution Start
        self.event_emitter.emit(
            "tool_execution_start",
            {"tool_name": tool_name, "arguments": arguments_with_values},
        )

        try:
            # Execute the tool synchronously
            arguments_with_values_interpolated = {
                key: self._interpolate_variables(value) for key, value in arguments_with_values.items()
            }
            # Call tool execute with named arguments
            response = tool.execute(**arguments_with_values_interpolated)
            executed_tool = tool.name
        except Exception as e:
            response = f"Error executing tool: {tool_name}: {str(e)}\n"
            executed_tool = ""

        # Emit event: Tool Execution End
        self.event_emitter.emit(
            "tool_execution_end",
            {
                "tool_name": tool_name,
                "arguments": arguments_with_values,
                "response": response,
            },
        )

        return executed_tool, response

    def _interpolate_variables(self, text: str) -> str:
        """Interpolate variables using $var1$ syntax in the given text."""
        try:
            for var in self.variable_store.keys():
                text = text.replace(f"${var}$", self.variable_store[var])
            return text
        except Exception as e:
            logger.error(f"Error in _interpolate_variables: {str(e)}")
            return text

    def _prepare_prompt_task(self, task: str) -> str:
        """Prepare the initial prompt for the task.

        Args:
            task (str): The task description.

        Returns:
            str: The formatted task prompt.
        """
        prompt_task: str = (
            "## Your task to solve:\n"
            f"<task>\n{task}\n</task>\n"
            "\n### Tools:\n"
            "-----------------------------\n"
            f"{self._get_tools_names_prompt()}\n"
            "### Variables:\n"
            "-----------------------------\n"
            f"{self._get_variable_prompt()}\n"
        )
        return prompt_task

    def _get_tools_names_prompt(self) -> str:
        """Construct a detailed prompt that lists the available tools for task execution."""
        prompt_use_tools: str = (
            "To accomplish this task, you have access to these tools:\n"
            "\n"
            f"{', '.join(self.tools.tool_names())}\n\n"
            "Instructions:\n"
            "\n"
            "1. Select ONE tool per message\n"
            "2. You will receive the tool's output in the next user response\n"
            "3. Choose the most appropriate tool for each step\n"
        )
        return prompt_use_tools

    def _get_variable_prompt(self) -> str:
        """Construct a prompt that explains how to use variables."""
        prompt_use_variables: str = (
            "To use a variable interpolation, use the format $variable_name$ in function arguments.\n"
            "Example: <write_file><file_path>/path/to/file.txt</file_path><content>$var1$</write_file>\n"
            "\n"
            "Available variables:\n"
            "\n"
            f"{', '.join(self.variable_store.keys())}\n"
        )
        return prompt_use_variables

    def _calculate_context_occupancy(self) -> float:
        """Calculate the number of tokens in percentages for prompt and completion."""
        total_tokens = self.total_tokens
        # Calculate token usage of prompt
        max_tokens = self.model.get_model_max_input_tokens()

        # Handle None value and prevent division by zero
        if max_tokens is None or max_tokens <= 0:
            logger.warning(f"Invalid max tokens value: {max_tokens}. Using default of {DEFAULT_MAX_INPUT_TOKENS}.")
            max_tokens = DEFAULT_MAX_INPUT_TOKENS

        return round((total_tokens / max_tokens) * 100, 2)

    def _compact_memory_with_summary(self) -> str:
        prompt_summary = (
            "Summarize the conversation concisely:\n"
            "format in markdown:\n"
            "<thinking>\n"
            " - 1. **Completed Steps**: Briefly describe the steps.\n"
            " - 2. **Variables Used**: List the variables.\n"
            " - 3. **Progress Analysis**: Assess progress.\n"
            "</thinking>\n"
            "Keep the summary clear and actionable.\n"
        )

        # Get all message system, except the last assistant / user message
        memory_copy = self.memory.memory.copy()

        # Remove the last assistant / user message
        user_message = memory_copy.pop()
        assistant_message = memory_copy.pop()
        summary = self.model.generate_with_history(messages_history=memory_copy, prompt=prompt_summary)
        # Remove user message
        memory_copy.pop()
        # Replace by summary
        memory_copy.append(Message(role="user", content=summary.response))
        memory_copy.append(assistant_message)
        memory_copy.append(user_message)
        self.memory.memory = memory_copy
        return summary.response
