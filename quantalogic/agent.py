"""Enhanced QuantaLogic agent implementing the ReAct framework."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

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
    """Enhanced QuantaLogic agent implementing ReAct framework."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="forbid"
    )

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
    ):
        """Initialize the agent with model, memory, tools, and configurations."""
        try:
            logger.debug("Initializing agent...")
            
            # Create event emitter
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
        """Set the model name."""
        self._model_name = value
        # Update the model instance with the new name
        self.model = GenerativeModel(model=value, event_emitter=self.event_emitter)

    def clear_memory(self):
        """Clear the memory and reset the session."""
        self._reset_session(clear_memory=True)

    def solve_task(self, task: str, max_iterations: int = 30, streaming: bool = False, clear_memory: bool = True) -> str:
        """Solve the given task using the ReAct framework.

        Args:
            task (str): The task description.
            max_iterations (int, optional): Maximum number of iterations to attempt solving the task.
                Defaults to 30 to prevent infinite loops and ensure timely task completion.
            streaming (bool, optional): Whether to use streaming mode for generating responses.
            clear_memory (bool, optional): Whether to clear the memory before solving the task.

        Returns:
            str: The final response after task completion.
        """
        logger.debug(f"Solving task... {task}")
        self._reset_session(task_to_solve=task, max_iterations=max_iterations,clear_memory=clear_memory)

        # Generate task summary
        self.task_to_solve_summary = self._generate_task_summary(task)

        # Add system prompt to memory
        # Check if system prompt is already in memory
        # if not add it
        # The system message is always the first message in memory
        if not self.memory.memory or self.memory.memory[0].role != "system":
            self.memory.add(Message(role="system", content=self.config.system_prompt))

        self._emit_event(
            "session_start",
            {"system_prompt": self.config.system_prompt, "content": task},
        )

        self.max_output_tokens = self.model.get_model_max_output_tokens() or DEFAULT_MAX_OUTPUT_TOKENS
        self.max_input_tokens = self.model.get_model_max_input_tokens() or DEFAULT_MAX_INPUT_TOKENS

        done = False
        current_prompt = self._prepare_prompt_task(task)

        self.current_iteration = 1

        # Emit event: Task Solve Start
        self._emit_event(
            "task_solve_start",
            {"initial_prompt": current_prompt, "task": task},
        )

        answer: str = ""

        while not done:
            try:
                self._update_total_tokens(message_history=self.memory.memory, prompt=current_prompt)

                # Emit event: Task Think Start after updating total tokens
                self._emit_event("task_think_start", {"prompt": current_prompt})

                self._compact_memory_if_needed(current_prompt)

                if streaming:
                    # For streaming, collect the response chunks
                    content = ""
                    for chunk in self.model.generate_with_history(
                        messages_history=self.memory.memory, prompt=current_prompt, streaming=True
                    ):
                        content += chunk

                    # Create a response object similar to non-streaming mode
                    result = ResponseStats(
                        response=content,
                        usage=TokenUsage(
                            prompt_tokens=0,  # We don't have token counts in streaming mode
                            completion_tokens=0,
                            total_tokens=0,
                        ),
                        model=self.model.model,
                        finish_reason="stop",
                    )
                else:
                    result = self.model.generate_with_history(
                        messages_history=self.memory.memory, prompt=current_prompt, streaming=False
                    )

                content = result.response
                if not streaming:  # Only update tokens for non-streaming mode
                    token_usage = result.usage
                    self.total_tokens = token_usage.total_tokens

                # Emit event: Task Think End
                self._emit_event(
                    "task_think_end",
                    {
                        "response": content,
                    },
                )

                # Process the assistant's response
                result = self._observe_response(content, iteration=self.current_iteration)

                current_prompt = result.next_prompt

                if result.executed_tool == "task_complete":
                    self._emit_event(
                        "task_complete",
                        {
                            "response": result.answer,
                        },
                    )
                    answer = result.answer
                    done = True

                self._update_session_memory(current_prompt, content)

                self.current_iteration += 1
                if self.current_iteration >= self.max_iterations:
                    done = True
                    self._emit_event("error_max_iterations_reached")

            except Exception as e:
                logger.error(f"Error during task solving: {str(e)}")
                # Optionally, decide to continue or break based on exception type
                answer = f"Error: {str(e)}"
                done = True

        # Emit event: Task Solve End
        self._emit_event("task_solve_end")

        logger.debug(f"Task solved: {answer}")

        return answer

    def _reset_session(self, task_to_solve: str = "", max_iterations: int = 30,clear_memory: bool = True):
        """Reset the agent's session."""
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
        self.total_tokens = self.model.token_counter_with_history(message_history, prompt)

    def _compact_memory_if_needed(self, current_prompt: str = ""):
        """Compacts the memory if it exceeds the maximum occupancy or token limit."""
        ratio_occupied = self._calculate_context_occupancy()
        
        # Compact memory if any of these conditions are met:
        # 1. Memory occupancy exceeds MAX_OCCUPANCY, or
        # 2. Current iteration is a multiple of compact_every_n_iterations, or
        # 3. Working memory exceeds max_tokens_working_memory (if set)
        should_compact_by_occupancy = ratio_occupied >= MAX_OCCUPANCY
        should_compact_by_iteration = (
            self.compact_every_n_iterations is not None and 
            self.current_iteration > 0 and 
            self.current_iteration % self.compact_every_n_iterations == 0
        )
        should_compact_by_token_limit = (
            self.max_tokens_working_memory is not None and 
            self.total_tokens > self.max_tokens_working_memory
        )
        
        if should_compact_by_occupancy or should_compact_by_iteration or should_compact_by_token_limit:
            if should_compact_by_occupancy:
                logger.debug(f"Memory compaction triggered: Occupancy {ratio_occupied}% exceeds {MAX_OCCUPANCY}%")
            
            if should_compact_by_iteration:
                logger.debug(f"Memory compaction triggered: Iteration {self.current_iteration} is a multiple of {self.compact_every_n_iterations}")
            
            self._emit_event("memory_full")
            self.memory.compact()
            self.total_tokens = self.model.token_counter_with_history(self.memory.memory, current_prompt)
            self._emit_event("memory_compacted")

    def _emit_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """
        Emit an event with system context and optional additional data.

        Why: Provides a standardized way to track and log system events
        with consistent contextual information.
        """
        # Use empty dict as default to avoid mutable default argument
        event_data = {
            "iteration": self.current_iteration,
            "total_tokens": self.total_tokens,
            "context_occupancy": self._calculate_context_occupancy(),
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
        }

        # Merge additional data if provided
        if data:
            event_data.update(data)

        self.event_emitter.emit(event_type, event_data)

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
                    executed_tool, response = self._execute_tool(tool_name, tool, arguments_with_values)

                if not executed_tool:
                    return self._handle_tool_execution_failure(response)

                variable_name = self.variable_store.add(response)
                new_prompt = self._format_observation_response(response, variable_name, iteration)

                return ObserveResponseResult(
                    next_prompt=new_prompt,
                    executed_tool=executed_tool,
                    answer=response if executed_tool == "task_complete" else None,
                )

        except Exception as e:
            return self._handle_error(e)

    def _parse_tool_usage(self, content: str) -> dict:
        """Extract tool usage from the response content."""
        if not content or not isinstance(content, str):
            return {}
        
        xml_parser = ToleranceXMLParser()
        tool_names = self.tools.tool_names()
        return xml_parser.extract_elements(text=content, element_names=tool_names)

    def _parse_tool_arguments(self, tool, tool_input: str) -> dict:
        """Parse the tool arguments from the tool input."""
        tool_parser = ToolParser(tool=tool)
        return tool_parser.parse(tool_input)

    def _is_repeated_tool_call(self, tool_name: str, arguments_with_values: dict) -> bool:
        """Check if the tool call is repeated."""
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
        return is_repeated_call and repeat_count >= 2

    def _handle_no_tool_usage(self) -> ObserveResponseResult:
        """Handle the case where no tool usage is found in the response."""
        return ObserveResponseResult(
            next_prompt="Error: No tool usage found in response.", executed_tool=None, answer=None
        )

    def _handle_tool_not_found(self, tool_name: str) -> ObserveResponseResult:
        """Handle the case where the tool is not found."""
        logger.warning(f"Tool '{tool_name}' not found in tool manager.")
        return ObserveResponseResult(
            next_prompt=f"Error: Tool '{tool_name}' not found in tool manager.",
            executed_tool="",
            answer=None,
        )

    def _handle_repeated_tool_call(self, tool_name: str, arguments_with_values: dict) -> (str,str):
        """Handle the case where a tool call is repeated."""
        repeat_count = self.last_tool_call.get("count", 0)
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
        return tool_name, error_message

    def _handle_tool_execution_failure(self, response: str) -> ObserveResponseResult:
        """Handle the case where tool execution fails."""
        return ObserveResponseResult(
            next_prompt=response,
            executed_tool="",
            answer=None,
        )

    def _handle_error(self, error: Exception) -> ObserveResponseResult:
        """Handle any exceptions that occur during response observation."""
        logger.error(f"Error in _observe_response: {str(error)}")
        return ObserveResponseResult(
            next_prompt=f"An error occurred while processing the response: {str(error)}",
            executed_tool=None,
            answer=None,
        )

    def _format_observation_response(self, response: str, variable_name: str, iteration: int) -> str:
        """Format the observation response with the given response, variable name, and iteration."""
        response_display = response
        if len(response) > MAX_RESPONSE_LENGTH:
            response_display = response[:MAX_RESPONSE_LENGTH]
            response_display += (
                f"... content was truncated full content available by interpolation in variable {variable_name}"
            )

        # Format the response message
        formatted_response = (
            f"Your next step: you Must now plan the next tool call to complete the based on this new observation\n"
            f"\n--- Observations for iteration {iteration} / max {self.max_iterations} ---\n"
            f"\n--- Tool execution result in ${variable_name}$ ---\n"
            f"<{variable_name}>\n{response_display}\n</{variable_name}>\n\n"
            f"--- Tools ---\n{self._get_tools_names_prompt()}\n"
            f"--- Variables ---\n{self._get_variable_prompt()}\n"
            "Analyze this response to determine the next steps. If the step failed, reconsider your approach.\n"
            f"--- Task to solve summary ---\n{self.task_to_solve_summary}\n"
            "--- Format ---\n"
            "Respond only with two XML blocks in markdown as specified in system prompt.\n"
            "No extra comments must be added.\n"
            "```xml\n"
            "<thinking>\n"
            "...\n"
            "</thinking>\n"
            "```\n"
            "```xml\n"
            "< ...tool_name... >\n"
            "...\n"
            "</ ...tool_name... >\n"
            "```"
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

        Note:
            Predefined variable properties take precedence over dynamically provided values.
            This ensures consistent behavior when tools have both predefined properties
            and runtime-provided arguments. The precedence order is:
            1. Predefined properties from tool.get_injectable_properties_in_execution()
            2. Runtime-provided arguments from arguments_with_values
        """
        # Handle tool validation if required
        if tool.need_validation:
            logger.debug(f"Tool '{tool_name}' requires validation.")
            self._emit_event(
                "tool_execute_validation_start",
                {"tool_name": tool_name, "arguments": arguments_with_values},
            )

            question_validation: str = (
                "Do you permit the execution of this tool?\n"
                f"Tool: {tool_name}\n"
                "Arguments:\n"
                "<arguments>\n"
                + "\n".join([f"    <{key}>{value}</{key}>" for key, value in arguments_with_values.items()])
                + "\n</arguments>\n"
                "Yes or No"
            )
            permission_granted = self.ask_for_user_validation(question_validation)

            self._emit_event(
                "tool_execute_validation_end",
                {"tool_name": tool_name, "arguments": arguments_with_values},
            )

            if not permission_granted:
                logger.debug(f"Execution of tool '{tool_name}' was denied by the user.")
                return "", f"Error: execution of tool '{tool_name}' was denied by the user."

        # Emit event: Tool Execution Start
        self._emit_event(
            "tool_execution_start",
            {"tool_name": tool_name, "arguments": arguments_with_values},
        )

        try:
            # Execute the tool synchronously
            arguments_with_values_interpolated = {
                key: self._interpolate_variables(value) for key, value in arguments_with_values.items()
            }
            
            arguments_with_values_interpolated = arguments_with_values_interpolated

            # test if tool need variables in context 
            if tool.need_variables:
                # Inject variables into the tool if needed
                arguments_with_values_interpolated["variables"] = self.variable_store
            if tool.need_caller_context_memory:
                # Inject caller context into the tool if needed
                arguments_with_values_interpolated["caller_context_memory"] = self.memory.memory

            try:
                # Convert arguments to proper types
                converted_args = self.tools.validate_and_convert_arguments(
                    tool_name, 
                    arguments_with_values_interpolated
                )
            except ValueError as e:
                return "", f"Argument Error: {str(e)}"

            # Add injectable variables
            injectable_properties = tool.get_injectable_properties_in_execution()
            for key, value in injectable_properties.items():
                converted_args[key] = value

            # Call tool execute with named arguments
            response = tool.execute(**converted_args)
            executed_tool = tool.name
        except Exception as e:
            response = f"Error executing tool: {tool_name}: {str(e)}\n"
            executed_tool = ""

        # Emit event: Tool Execution End
        self._emit_event(
            "tool_execution_end",
            {
                "tool_name": tool_name,
                "arguments": arguments_with_values,
                "response": response,
            },
        )

        return executed_tool, response

    def _interpolate_variables(self, text: str) -> str:
        """Interpolate variables using $var$ syntax in the given text."""
        try:
            import re
            for var in self.variable_store.keys():
                # Escape the variable name for regex, but use raw value for replacement
                pattern = rf'\${re.escape(var)}\$'
                replacement = self.variable_store[var]
                text = re.sub(pattern, replacement, text)
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
            "\n"
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
            "4. Use task_complete tool to confirm task completion\n"
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
            if len(self.variable_store.keys()) > 0
            else "None\n"
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
        summary = self.model.generate_with_history(
            messages_history=memory_copy, prompt=prompt_summary
        )
        # Remove user message
        memory_copy.pop()
        # Replace by summary
        memory_copy.append(Message(role="user", content=summary.response))
        memory_copy.append(assistant_message)
        memory_copy.append(user_message)
        self.memory.memory = memory_copy
        return summary.response

    def _generate_task_summary(self, content: str) -> str:
        """Generate a concise task-focused summary using the generative model.

        Args:
            content (str): The content to summarize

        Returns:
            str: Generated task summary
        """
        try:
            prompt = (
                "Create an ultra-concise task summary that captures ONLY: \n"
                "1. Primary objective/purpose\n"
                "2. Core actions/requirements\n"
                "3. Desired end-state/outcome\n\n"
                "Guidelines:\n"
                "- Use imperative voice\n"
                "- Exclude background, explanations, and examples\n"
                "- Compress information using semantic density\n"
                "- Strict 2-3 sentence maximum (under 50 words)\n"
                "- Format: 'Concise Task Summary: [Your summary]'\n\n"
                f"Input Task Description:\n{content}\n\n"
                "Concise Task Summary:"
            )
            result = self.model.generate(prompt=prompt)
            logger.debug(f"Generated summary: {result.response}")
            return result.response.strip() + "\n🚨 The FULL task is in <task> tag in the previous messages.\n"
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return f"Summary generation failed: {str(e)}"

    def _update_session_memory(self, user_content: str, assistant_content: str) -> None:
        """
        Log session messages to memory and emit events.

        Args:
            user_content (str): The user's content.
            assistant_content (str): The assistant's content.
        """
        self.memory.add(Message(role="user", content=user_content))
        self._emit_event(
            "session_add_message",
            {"role": "user", "content": user_content},
        )

        self.memory.add(Message(role="assistant", content=assistant_content))

        self._emit_event(
            "session_add_message",
            {"role": "assistant", "content": assistant_content},
        )

    def update_model(self, new_model_name: str) -> None:
        """Update the model name and recreate the model instance."""
        self.model_name = new_model_name
        self.model = GenerativeModel(model=new_model_name, event_emitter=self.event_emitter)
