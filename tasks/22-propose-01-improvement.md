You Goal is to propose detailled improvement for AI ReAct Agent and a concrete plan to implement it.

- Focus on the ReAct Cycle
- Identify areas for improvement, consecutive tool calls
- Fix, bugs
- Propose specific changes
- Provide a concrete plan for implementation



# Table of Contents
- quantalogic/main.py
- quantalogic/agent_config.py
- quantalogic/memory.py
- quantalogic/tool_manager.py
- quantalogic/event_emitter.py
- quantalogic/generative_model.py
- quantalogic/main.py

## File: quantalogic/main.py

- Extension: .py
- Language: python
- Size: 5880 bytes
- Created: 2024-12-31 23:24:10
- Modified: 2024-12-31 23:24:10

### Code

```python
#!/usr/bin/env python
"""Main module for the QuantaLogic agent."""

# Standard library imports
import argparse
import sys

# Third-party imports
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

# Local application imports
from quantalogic.agent_config import MODEL_NAME, create_agent, create_coding_agent, create_orchestrator_agent
from quantalogic.interactive_text_editor import get_multiline_input
from quantalogic.print_event import print_events

main_agent = create_agent(MODEL_NAME)

main_agent.event_emitter.on(
    [
        "task_think_end",
        "task_complete",
        "task_think_start",
        "tool_execution_start",
        "error_max_iterations_reached",
        "memory_full",
        "memory_compacted",
        "memory_summary",
    ],
    print_events,
)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="QuantaLogic AI Assistant")
    parser.add_argument("--version", action="store_true", help="show version information")
    parser.add_argument("--execute-file", type=str, help="execute task from file")
    parser.add_argument("--verbose", action="store_true", help="enable verbose output")
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help='specify the model to use (litellm format, e.g. "openrouter/deepseek-chat")',
    )
    return parser.parse_args()


def get_task_from_file(file_path):
    """Get task content from specified file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File '{file_path}' not found.")
    except PermissionError:
        raise PermissionError(f"Error: Permission denied when reading '{file_path}'.")
    except Exception as e:
        raise Exception(f"Unexpected error reading file: {e}")


def get_task_from_args(args):
    """Extract task from command line arguments."""
    task_args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] in ["--version", "--execute-file", "--verbose", "--model"]:
            i += 2 if sys.argv[i] in ["--execute-file", "--model"] else 1
        else:
            task_args.append(sys.argv[i])
            i += 1
    # Return empty string if only --model is provided
    if not task_args and any(arg in sys.argv for arg in ["--model"]):
        return ""
    return " ".join(task_args)


def display_welcome_message(console, model_name):
    """Display the welcome message and instructions."""
    console.print(
        Panel.fit(
            "[bold cyan]🌟 Welcome to QuantaLogic AI Assistant! 🌟[/bold cyan]\n\n"
            "[green]🎯 How to Use:[/green]\n\n"
            "1. [bold]Describe your task[/bold]: Tell the AI what you need help with.\n"
            '   - Example: "Write a Python function to calculate Fibonacci numbers."\n'
            '   - Example: "Explain quantum computing in simple terms."\n'
            '   - Example: "Generate a list of 10 creative project ideas."\n'
            '   - Example: "Create a project plan for a new AI startup.\n'
            '   - Example: "Help me debug this Python code."\n\n'
            "2. [bold]Submit your task[/bold]: Press [bold]Enter[/bold] twice to send your request.\n\n"
            "3. [bold]Exit the app[/bold]: Leave the input blank and press [bold]Enter[/bold] twice to close the assistant.\n\n"
            f"[yellow]ℹ️ System Info:[/yellow]\n\n"
            f"- Version: {get_version()}\n"
            f"- Model: {model_name}\n\n"
            "[bold magenta]💡 Pro Tips:[/bold magenta]\n\n"
            "- Be as specific as possible in your task description to get the best results!\n"
            "- Use clear and concise language when describing your task\n"
            "- For coding tasks, include relevant context and requirements\n"
            "- The AI can handle complex tasks - don't hesitate to ask challenging questions!",
            title="[bold]Instructions[/bold]",
            border_style="blue",
        )
    )


def main():
    """Main entry point for the QuantaLogic AI Assistant."""
    console = Console()
    args = parse_arguments()

    if args.version:
        console.print(f"QuantaLogic version: {get_version()}")
        sys.exit(0)

    try:
        if args.execute_file:
            task = get_task_from_file(args.execute_file)
        else:
            task = get_task_from_args(args)
            if not task:  # If no task is provided in arguments, go to interactive mode
                display_welcome_message(console, args.model)
                task = get_multiline_input(console).strip()
                if not task:
                    console.print("[yellow]No task provided. Exiting...[/yellow]")
                    sys.exit(2)
    except Exception as e:
        console.print(f"[red]{str(e)}[/red]")
        sys.exit(1)

    # Bypass task preview and confirmation if --model is provided
    if not args.model == MODEL_NAME:
        console.print(
            Panel.fit(
                f"[bold]Task to be submitted:[/bold]\n{task}", title="[bold]Task Preview[/bold]", border_style="blue"
            )
        )
        if not Confirm.ask("[bold]Are you sure you want to submit this task?[/bold]"):
            console.print("[yellow]Task submission cancelled. Exiting...[/yellow]")
            sys.exit(0)

    # agent = create_agent(args.model)
    agent = create_coding_agent(args.model)
    result = agent.solve_task(task=task, max_iterations=3000)

    console.print(
        Panel.fit(f"[bold]Task Result:[/bold]\n{result}", title="[bold]Execution Output[/bold]", border_style="green")
    )


def get_version():
    """Get the current version of the package."""
    return "QuantaLogic version: 1.0.0"


if __name__ == "__main__":
    main()

```

## File: quantalogic/agent_config.py

- Extension: .py
- Language: python
- Size: 3197 bytes
- Created: 2024-12-31 23:23:30
- Modified: 2024-12-31 23:23:30

### Code

```python
"""Module for agent configuration and creation."""

# Standard library imports

# Local application imports
from quantalogic.agent import Agent
from quantalogic.tools import (
    AgentTool,
    DownloadHttpFileTool,
    EditWholeContentTool,
    ExecuteBashCommandTool,
    InputQuestionTool,
    ListDirectoryTool,
    LLMTool,
    MarkitdownTool,
    NodeJsTool,
    PythonTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReplaceInFileTool,
    RipgrepTool,
    SearchDefinitionNames,
    TaskCompleteTool,
    WriteFileTool,
)
from quantalogic.tools.agent_tool import AgentTool

MODEL_NAME = "openrouter/deepseek/deepseek-chat"


def create_coding_agent(model_name: str) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
    """
    return Agent(
        model_name=model_name,
        tools=[
            TaskCompleteTool(),
            ReadFileTool(),
            ReadFileBlockTool(),
            WriteFileTool(),
            ReplaceInFileTool(),
            EditWholeContentTool(),
            ListDirectoryTool(),
            RipgrepTool(),
            SearchDefinitionNames(),
            LLMTool(model_name=MODEL_NAME),
        ],
        specific_expertise=(
            "Expert in software development and problem-solving."
            "Prefer to localize with precise code snippets before updating the codebase."
            "Always check the codebase before making changes."
            "Prefer to use ReplaceInFileTool for code updates."
            "Prefer to use SearchDefinitionNames for code search."
        ),
    )


coding_agent = create_coding_agent(MODEL_NAME)


def create_agent(model_name) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
    """
    return Agent(
        model_name=model_name,
        tools=[
            TaskCompleteTool(),
            ReadFileTool(),
            ReadFileBlockTool(),
            WriteFileTool(),
            EditWholeContentTool(),
            InputQuestionTool(),
            ListDirectoryTool(),
            ExecuteBashCommandTool(),
            ReplaceInFileTool(),
            RipgrepTool(),
            #            PythonTool(),
            #            NodeJsTool(),
            SearchDefinitionNames(),
            MarkitdownTool(),
            LLMTool(model_name=MODEL_NAME),
            DownloadHttpFileTool(),
        ],
    )


def create_orchestrator_agent(model_name: str) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()

    coding_agent_instance = create_coding_agent(model_name)

    return Agent(
        model_name=model_name,
        tools=[
            TaskCompleteTool(),
            ListDirectoryTool(),
            ReadFileBlockTool(),
            RipgrepTool(),
            SearchDefinitionNames(),
            LLMTool(model_name=MODEL_NAME),
            AgentTool(agent=coding_agent_instance, agent_role="software expert", name="coder_agent_tool"),
        ],
    )

```

## File: quantalogic/memory.py

- Extension: .py
- Language: python
- Size: 6311 bytes
- Created: 2024-12-31 21:27:54
- Modified: 2024-12-31 21:27:54

### Code

```python
"""Memory for the agent."""
from pydantic import BaseModel


class Message(BaseModel):
    """Represents a message in the agent's memory."""

    role: str
    content: str


class AgentMemory:
    """Memory for the agent."""

    def __init__(self):
        """Initialize the agent memory."""
        self.memory: list[Message] = []

    def add(self, message: Message):
        """Add a message to the agent memory.

        Args:
            message (Message): The message to add to memory.
        """
        self.memory.append(message)

    def reset(self):
        """Reset the agent memory."""
        self.memory.clear()

    def compact(self, n: int = 2):
        """Compact the memory to keep only essential messages.
        
        This method keeps:
        - The system message (if present)
        - First two pairs of user-assistant messages
        - Last n pairs of user-assistant messages (default: 2)

        Args:
            n (int): Number of last message pairs to keep. Defaults to 2.
        """
        if not self.memory:
            return

        # Keep system message if present
        compacted_memory = []
        if self.memory and self.memory[0].role == "system":
            compacted_memory.append(self.memory[0])
            messages = self.memory[1:]
        else:
            messages = self.memory[:]

        # Extract user-assistant pairs
        pairs = []
        i = 0
        while i < len(messages) - 1:
            if messages[i].role == "user" and messages[i + 1].role == "assistant":
                pairs.append((messages[i], messages[i + 1]))
            i += 2

        # Keep first two and last n pairs
        total_pairs_to_keep = 2 + n
        if len(pairs) <= total_pairs_to_keep:
            for user_msg, assistant_msg in pairs:
                compacted_memory.extend([user_msg, assistant_msg])
        else:
            # Add first two pairs
            for pair in pairs[:2]:
                compacted_memory.extend(pair)
            # Add last n pairs
            for pair in pairs[-n:]:
                compacted_memory.extend(pair)

        self.memory = compacted_memory


class VariableMemory:
    """Memory for a variable."""

    def __init__(self):
        """Initialize the variable memory."""
        self.memory: dict[str, tuple[str, str]] = {}
        self.counter: int = 0

    def add(self, value: str) -> str:
        """Add a value to the variable memory.

        Args:
            value (str): The value to add to memory.

        Returns:
            str: The key associated with the added value.
        """
        self.counter += 1
        key = f"var{self.counter}"
        self.memory[key] = (key, value)
        return key

    def reset(self):
        """Reset the variable memory."""
        self.memory.clear()
        self.counter = 0

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a value from the variable memory.

        Args:
            key (str): The key of the value to retrieve.
            default (str, optional): Default value if key is not found. Defaults to None.

        Returns:
            str | None: The value associated with the key, or default if not found.
        """
        return self.memory.get(key, default)[1] if key in self.memory else default

    def __getitem__(self, key: str) -> str:
        """Get a value using dictionary-style access.

        Args:
            key (str): The key of the value to retrieve.

        Returns:
            str: The value associated with the key.

        Raises:
            KeyError: If the key is not found.
        """
        return self.memory[key][1]

    def __setitem__(self, key: str, value: str):
        """Set a value using dictionary-style assignment.

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.
        """
        self.memory[key] = (key, value)

    def __delitem__(self, key: str):
        """Delete a key-value pair using dictionary-style deletion.

        Args:
            key (str): The key to delete.

        Raises:
            KeyError: If the key is not found.
        """
        del self.memory[key]

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the memory.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        return key in self.memory

    def __len__(self) -> int:
        """Get the number of items in the memory.

        Returns:
            int: Number of items in the memory.
        """
        return len(self.memory)

    def keys(self):
        """Return a view of the memory's keys.

        Returns:
            dict_keys: A view of the memory's keys.
        """
        return self.memory.keys()

    def values(self):
        """Return a view of the memory's values.

        Returns:
            dict_values: A view of the memory's values.
        """
        return (value[1] for value in self.memory.values())

    def items(self):
        """Return a view of the memory's items.

        Returns:
            dict_items: A view of the memory's items.
        """
        return ((key, value[1]) for key, value in self.memory.items())

    def pop(self, key: str, default: str | None = None) -> str | None:
        """Remove and return a value for a key.

        Args:
            key (str): The key to remove.
            default (str, optional): Default value if key is not found. Defaults to None.

        Returns:
            str | None: The value associated with the key, or default if not found.
        """
        return self.memory.pop(key, (None, default))[1] if default is not None else self.memory.pop(key)[1]

    def update(self, other: dict[str, str] | None = None, **kwargs):
        """Update the memory with key-value pairs from another dictionary.

        Args:
            other (dict, optional): Dictionary to update from. Defaults to None.
            **kwargs: Additional key-value pairs to update.
        """
        if other is not None:
            for key, value in other.items():
                self.memory[key] = (key, value)
        for key, value in kwargs.items():
            self.memory[key] = (key, value)

```

## File: quantalogic/tool_manager.py

- Extension: .py
- Language: python
- Size: 2420 bytes
- Created: 2024-12-31 21:27:54
- Modified: 2024-12-31 21:27:54

### Code

```python
"""Tool dictionary for the agent."""
from loguru import logger
from pydantic import BaseModel

from quantalogic.tools.tool import Tool


class ToolManager(BaseModel):
    """Tool dictionary for the agent."""

    tools: dict[str, Tool] = {}

    def tool_names(self) -> list[str]:
        """Get the names of all tools in the tool dictionary."""
        logger.debug("Getting tool names")
        return list(self.tools.keys())

    def add(self, tool: Tool):
        """Add a tool to the tool dictionary."""
        logger.info(f"Adding tool: {tool.name} to tool dictionary")
        self.tools[tool.name] = tool

    def add_list(self, tools: list[Tool]):
        """Add a list of tools to the tool dictionary."""
        logger.info(f"Adding {len(tools)} tools to tool dictionary")
        for tool in tools:
            self.add(tool)

    def remove(self, tool_name: str) -> bool:
        """Remove a tool from the tool dictionary."""
        logger.info(f"Removing tool: {tool_name} from tool dictionary")
        del self.tools[tool_name]
        return True

    def get(self, tool_name: str) -> Tool:
        """Get a tool from the tool dictionary."""
        logger.debug(f"Getting tool: {tool_name} from tool dictionary")
        return self.tools[tool_name]

    def list(self):
        """List all tools in the tool dictionary."""
        logger.debug("Listing all tools")
        return list(self.tools.keys())

    def execute(self, tool_name: str, **kwargs) -> str:
        """Execute a tool from the tool dictionary."""
        logger.info(f"Executing tool: {tool_name} with arguments: {kwargs}")
        try:
            result = self.tools[tool_name].execute(**kwargs)
            logger.debug(f"Tool {tool_name} execution completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            raise

    def to_markdown(self):
        """Create a comprehensive Markdown representation of the tool dictionary."""
        logger.debug("Creating Markdown representation of tool dictionary")
        markdown = ""
        index: int = 1
        for tool_name, tool in self.tools.items():
            # use the tool's to_markdown method
            markdown += f"### {index}. {tool_name}\n"
            markdown += tool.to_markdown()
            markdown += "\n"
            index += 1
        return markdown

```

## File: quantalogic/event_emitter.py

- Extension: .py
- Language: python
- Size: 7962 bytes
- Created: 2024-12-31 21:27:54
- Modified: 2024-12-31 21:27:54

### Code

```python
import threading
from typing import Any, Callable


class EventEmitter:
    """A thread-safe event emitter class for managing event listeners and emissions."""

    def __init__(self) -> None:
        """Initialize an empty EventEmitter instance.

        Creates an empty dictionary to store event listeners,
        where each event can have multiple callable listeners.
        Also initializes a list for wildcard listeners that listen to all events.
        """
        self._listeners: dict[str, list[Callable[..., Any]]] = {}
        self._wildcard_listeners: list[Callable[..., Any]] = []
        self._lock = threading.RLock()

    def on(self, event: str | list[str], listener: Callable[..., Any]) -> None:
        """Register an event listener for one or more events.

        If event is a list, the listener is registered for each event in the list.

        Parameters:
        - event (str | list[str]): The event name or a list of event names to listen to.
        - listener (Callable): The function to call when the specified event(s) are emitted.
        """
        if isinstance(event, str):
            events = [event]
        elif isinstance(event, list):
            events = event
        else:
            raise TypeError("Event must be a string or a list of strings.")

        with self._lock:
            for evt in events:
                if evt == "*":
                    if listener not in self._wildcard_listeners:
                        self._wildcard_listeners.append(listener)
                else:
                    if evt not in self._listeners:
                        self._listeners[evt] = []
                    if listener not in self._listeners[evt]:
                        self._listeners[evt].append(listener)

    def once(self, event: str | list[str], listener: Callable[..., Any]) -> None:
        """Register a one-time event listener for one or more events.

        The listener is removed after it is invoked the first time the event is emitted.

        Parameters:
        - event (str | list[str]): The event name or a list of event names to listen to.
        """

        def wrapper(*args: Any, **kwargs: Any) -> None:
            self.off(event, wrapper)
            listener(*args, **kwargs)

        self.on(event, wrapper)

    def off(
        self,
        event: str | list[str] | None = None,
        listener: Callable[..., Any] = None,
    ) -> None:
        """Unregister an event listener.

        If event is None, removes the listener from all events.

        Parameters:
        - event (str | list[str] | None): The name of the event or a list of event names to stop listening to.
                                           If None, removes the listener from all events.
        - listener (Callable): The function to remove from the event listeners.
        """
        with self._lock:
            if event is None:
                # Remove from all specific events
                for evt_list in self._listeners.values():
                    if listener in evt_list:
                        evt_list.remove(listener)
                # Remove from wildcard listeners
                if listener in self._wildcard_listeners:
                    self._wildcard_listeners.remove(listener)
            else:
                if isinstance(event, str):
                    events = [event]
                elif isinstance(event, list):
                    events = event
                else:
                    raise TypeError(
                        "Event must be a string, a list of strings, or None."
                    )

                for evt in events:
                    if evt == "*":
                        if listener in self._wildcard_listeners:
                            self._wildcard_listeners.remove(listener)
                    elif evt in self._listeners:
                        try:
                            self._listeners[evt].remove(listener)
                        except ValueError:
                            pass  # Listener was not found for this event

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to all registered listeners.

        First, invokes wildcard listeners, then listeners registered to the specific event.

        Parameters:
        - event (str): The name of the event to emit.
        - args: Positional arguments to pass to the listeners.
        - kwargs: Keyword arguments to pass to the listeners.
        """
        with self._lock:
            listeners = list(self._wildcard_listeners)
            if event in self._listeners:
                listeners.extend(self._listeners[event])

        for listener in listeners:
            try:
                listener(event,*args, **kwargs)
            except Exception as e:
                # Log the exception or handle it as needed
                print(f"Error in listener {listener}: {e}")

    def clear(self, event: str) -> None:
        """Clear all listeners for a specific event.

        Parameters:
        - event (str): The name of the event to clear listeners from.
        """
        with self._lock:
            if event in self._listeners:
                del self._listeners[event]

    def clear_all(self) -> None:
        """Clear all listeners for all events, including wildcard listeners."""
        with self._lock:
            self._listeners.clear()
            self._wildcard_listeners.clear()

    def listeners(self, event: str) -> list[Callable[..., Any]]:
        """Retrieve all listeners registered for a specific event, including wildcard listeners.

        Parameters:
        - event (str): The name of the event.

        Returns:
        - List of callables registered for the event.
        """
        with self._lock:
            listeners = list(self._wildcard_listeners)
            if event in self._listeners:
                listeners.extend(self._listeners[event])
            return listeners

    def has_listener(
        self, event: str | None, listener: Callable[..., Any]
    ) -> bool:
        """Check if a specific listener is registered for an event.

        Parameters:
        - event (str | None): The name of the event. If None, checks in wildcard listeners.
        - listener (Callable): The listener to check.

        Returns:
        - True if the listener is registered for the event, False otherwise.
        """
        with self._lock:
            if event is None:
                return listener in self._wildcard_listeners
            elif event == "*":
                return listener in self._wildcard_listeners
            else:
                return listener in self._listeners.get(event, [])


if __name__ == "__main__":
    def on_data_received(data):
        print(f"Data received: {data}")

    def on_any_event(event, data):
        print(f"Event '{event}' emitted with data: {data}")

    emitter = EventEmitter()

    # Register specific event listener
    emitter.on('data', on_data_received)

    # Register wildcard listener
    emitter.on('*', on_any_event)

    # Emit 'data' event
    emitter.emit('data', 'Sample Data')

    # Output:
    # Event 'data' emitted with data: Sample Data
    # Data received: Sample Data

    # Emit 'update' event
    emitter.emit('update', 'Update Data')

    # Output:
    # Event 'update' emitted with data: Update Data

    # Register a one-time listener
    def once_listener(data):
        print(f"Once listener received: {data}")

    emitter.once('data', once_listener)

    # Emit 'data' event
    emitter.emit('data', 'First Call')

    # Output:
    # Event 'data' emitted with data: First Call
    # Data received: First Call
    # Once listener received: First Call

    # Emit 'data' event again
    emitter.emit('data', 'Second Call')

    # Output:
    # Event 'data' emitted with data: Second Call
    # Data received: Second Call
    # (Once listener is not called again)    
```

## File: quantalogic/generative_model.py

- Extension: .py
- Language: python
- Size: 8220 bytes
- Created: 2024-12-31 22:22:49
- Modified: 2024-12-31 22:22:49

### Code

```python
"""Generative model module for AI-powered text generation."""

import openai
from litellm import completion, exceptions, get_max_tokens, get_model_info, token_counter
from loguru import logger
from pydantic import BaseModel, Field, field_validator

MIN_RETRIES = 3

class Message(BaseModel):
    """Represents a message in a conversation with a specific role and content."""

    role: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

    @field_validator("role", "content")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that the field is not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace-only")
        return v


class TokenUsage(BaseModel):
    """Represents token usage statistics for a language model."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ResponseStats(BaseModel):
    """Represents detailed statistics for a model response."""

    response: str
    usage: TokenUsage
    model: str
    finish_reason: str | None = None


class GenerativeModel:
    """Generative model for AI-powered text generation with configurable parameters."""

    def __init__(
        self,
        model: str = "ollama/qwen2.5-coder:14b",
        temperature: float = 0.7,
    ) -> None:
        """Initialize a generative model with configurable parameters.

        Configure the generative model with specified model,
        temperature, and maximum token settings.

        Args:
            model: Model identifier.
                Defaults to "ollama/qwen2.5-coder:14b".
            temperature: Sampling temperature between 0 and 1.
                Defaults to 0.7.
        """
        self.model = model
        self.temperature = temperature

    # Define retriable exceptions based on LiteLLM's exception mapping
    RETRIABLE_EXCEPTIONS = (
        exceptions.RateLimitError,  # Rate limits - should retry
        exceptions.APIConnectionError,  # Connection issues - should retry
        exceptions.ServiceUnavailableError,  # Service issues - should retry
        exceptions.Timeout,  # Timeout - should retry
        exceptions.APIError,  # Generic API errors - should retry
    )

    # Non-retriable exceptions that need specific handling
    CONTEXT_EXCEPTIONS = (
        exceptions.ContextWindowExceededError,
        exceptions.InvalidRequestError,
    )

    POLICY_EXCEPTIONS = (exceptions.ContentPolicyViolationError,)

    AUTH_EXCEPTIONS = (
        exceptions.AuthenticationError,
        exceptions.PermissionDeniedError,
    )

    # Retry on specific retriable exceptions
    def generate_with_history(self, messages_history: list[Message], prompt: str) -> ResponseStats:
        """Generate a response with conversation history.

        Generates a response based on previous conversation messages
        and a new user prompt.

        Args:
            messages_history: Previous conversation messages.
            prompt: Current user prompt.

        Returns:
            Detailed response statistics.

        Raises:
            openai.AuthenticationError: If authentication fails.
            openai.InvalidRequestError: If the request is invalid (e.g., context length exceeded).
            openai.APIError: For content policy violations or other API errors.
            Exception: For other unexpected errors.
        """
        messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages_history]
        messages.append({"role": "user", "content": str(prompt)})

        try:
            logger.debug(f"Generating response for prompt: {prompt}")

            response = completion(
                temperature=self.temperature,
                model=self.model,
                messages=messages,
                num_retries=MIN_RETRIES,
            )

            token_usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

            print(response.usage)

            return ResponseStats(
                response=response.choices[0].message.content,
                usage=token_usage,
                model=self.model,
                finish_reason=response.choices[0].finish_reason,
            )

        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "message": str(e),
                "model": self.model,
                "provider": getattr(e, "llm_provider", "unknown"),
                "status_code": getattr(e, "status_code", None),
            }

            logger.error("LLM Generation Error: {}", error_details)

            # Handle authentication and permission errors
            if isinstance(e, self.AUTH_EXCEPTIONS):
                raise openai.AuthenticationError(
                    f"Authentication failed with provider {error_details['provider']}"
                ) from e

            # Handle context window errors
            if isinstance(e, self.CONTEXT_EXCEPTIONS):
                raise openai.InvalidRequestError(f"Context window exceeded or invalid request: {str(e)}") from e

            # Handle content policy violations
            if isinstance(e, self.POLICY_EXCEPTIONS):
                raise openai.APIError(f"Content policy violation: {str(e)}") from e

            # For other exceptions, preserve the original error type if it's from OpenAI
            if isinstance(e, openai.OpenAIError):
                raise

            # Wrap unknown errors in APIError
            raise openai.APIError(f"Unexpected error during generation: {str(e)}") from e

    def generate(self, prompt: str) -> ResponseStats:
        """Generate a response without conversation history.

        Generates a response for a single user prompt without
        any previous conversation context.

        Args:
            prompt: User prompt.

        Returns:
            Detailed response statistics.
        """
        return self.generate_with_history([], prompt)

    def get_max_tokens(self) -> int:
        """Get the maximum number of tokens that can be generated by the model."""
        return get_max_tokens(self.model)

    def token_counter(self, messages: list[Message]) -> int:
        """Count the number of tokens in a list of messages."""
        litellm_messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages]
        return token_counter(model=self.model, messages=litellm_messages)

    def token_counter_with_history(self, messages_history: list[Message], prompt: str) -> int:
        """Count the number of tokens in a list of messages and a prompt."""
        litellm_messages = [{"role": msg.role, "content": str(msg.content)} for msg in messages_history]
        litellm_messages.append({"role": "user", "content": str(prompt)})
        return token_counter(model=self.model, messages=litellm_messages)

    def get_model_info(self) -> dict | None:
        """Get information about the model."""
        model_info = get_model_info(self.model)

        if not model_info:
            # Search without prefix "openrouter/"
            model_info = get_model_info(self.model.replace("openrouter/", ""))

        return model_info

    def get_model_max_input_tokens(self) -> int:
        """Get the maximum number of input tokens for the model."""
        try:
            model_info = self.get_model_info()
            max_tokens = model_info.get("max_input_tokens") if model_info else None
            return max_tokens
        except Exception as e:
            logger.error(f"Error getting max input tokens for {self.model}: {e}")
            return None

    def get_model_max_output_tokens(self) -> int | None:
        """Get the maximum number of output tokens for the model."""
        try:
            model_info = self.get_model_info()
            return model_info.get("max_output_tokens") if model_info else None
        except Exception as e:
            logger.error(f"Error getting max output tokens for {self.model}: {e}")
            return None
```

## File: quantalogic/main.py

- Extension: .py
- Language: python
- Size: 5880 bytes
- Created: 2024-12-31 23:24:10
- Modified: 2024-12-31 23:24:10

### Code

```python
#!/usr/bin/env python
"""Main module for the QuantaLogic agent."""

# Standard library imports
import argparse
import sys

# Third-party imports
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

# Local application imports
from quantalogic.agent_config import MODEL_NAME, create_agent, create_coding_agent, create_orchestrator_agent
from quantalogic.interactive_text_editor import get_multiline_input
from quantalogic.print_event import print_events

main_agent = create_agent(MODEL_NAME)

main_agent.event_emitter.on(
    [
        "task_think_end",
        "task_complete",
        "task_think_start",
        "tool_execution_start",
        "error_max_iterations_reached",
        "memory_full",
        "memory_compacted",
        "memory_summary",
    ],
    print_events,
)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="QuantaLogic AI Assistant")
    parser.add_argument("--version", action="store_true", help="show version information")
    parser.add_argument("--execute-file", type=str, help="execute task from file")
    parser.add_argument("--verbose", action="store_true", help="enable verbose output")
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help='specify the model to use (litellm format, e.g. "openrouter/deepseek-chat")',
    )
    return parser.parse_args()


def get_task_from_file(file_path):
    """Get task content from specified file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File '{file_path}' not found.")
    except PermissionError:
        raise PermissionError(f"Error: Permission denied when reading '{file_path}'.")
    except Exception as e:
        raise Exception(f"Unexpected error reading file: {e}")


def get_task_from_args(args):
    """Extract task from command line arguments."""
    task_args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] in ["--version", "--execute-file", "--verbose", "--model"]:
            i += 2 if sys.argv[i] in ["--execute-file", "--model"] else 1
        else:
            task_args.append(sys.argv[i])
            i += 1
    # Return empty string if only --model is provided
    if not task_args and any(arg in sys.argv for arg in ["--model"]):
        return ""
    return " ".join(task_args)


def display_welcome_message(console, model_name):
    """Display the welcome message and instructions."""
    console.print(
        Panel.fit(
            "[bold cyan]🌟 Welcome to QuantaLogic AI Assistant! 🌟[/bold cyan]\n\n"
            "[green]🎯 How to Use:[/green]\n\n"
            "1. [bold]Describe your task[/bold]: Tell the AI what you need help with.\n"
            '   - Example: "Write a Python function to calculate Fibonacci numbers."\n'
            '   - Example: "Explain quantum computing in simple terms."\n'
            '   - Example: "Generate a list of 10 creative project ideas."\n'
            '   - Example: "Create a project plan for a new AI startup.\n'
            '   - Example: "Help me debug this Python code."\n\n'
            "2. [bold]Submit your task[/bold]: Press [bold]Enter[/bold] twice to send your request.\n\n"
            "3. [bold]Exit the app[/bold]: Leave the input blank and press [bold]Enter[/bold] twice to close the assistant.\n\n"
            f"[yellow]ℹ️ System Info:[/yellow]\n\n"
            f"- Version: {get_version()}\n"
            f"- Model: {model_name}\n\n"
            "[bold magenta]💡 Pro Tips:[/bold magenta]\n\n"
            "- Be as specific as possible in your task description to get the best results!\n"
            "- Use clear and concise language when describing your task\n"
            "- For coding tasks, include relevant context and requirements\n"
            "- The AI can handle complex tasks - don't hesitate to ask challenging questions!",
            title="[bold]Instructions[/bold]",
            border_style="blue",
        )
    )


def main():
    """Main entry point for the QuantaLogic AI Assistant."""
    console = Console()
    args = parse_arguments()

    if args.version:
        console.print(f"QuantaLogic version: {get_version()}")
        sys.exit(0)

    try:
        if args.execute_file:
            task = get_task_from_file(args.execute_file)
        else:
            task = get_task_from_args(args)
            if not task:  # If no task is provided in arguments, go to interactive mode
                display_welcome_message(console, args.model)
                task = get_multiline_input(console).strip()
                if not task:
                    console.print("[yellow]No task provided. Exiting...[/yellow]")
                    sys.exit(2)
    except Exception as e:
        console.print(f"[red]{str(e)}[/red]")
        sys.exit(1)

    # Bypass task preview and confirmation if --model is provided
    if not args.model == MODEL_NAME:
        console.print(
            Panel.fit(
                f"[bold]Task to be submitted:[/bold]\n{task}", title="[bold]Task Preview[/bold]", border_style="blue"
            )
        )
        if not Confirm.ask("[bold]Are you sure you want to submit this task?[/bold]"):
            console.print("[yellow]Task submission cancelled. Exiting...[/yellow]")
            sys.exit(0)

    # agent = create_agent(args.model)
    agent = create_coding_agent(args.model)
    result = agent.solve_task(task=task, max_iterations=3000)

    console.print(
        Panel.fit(f"[bold]Task Result:[/bold]\n{result}", title="[bold]Execution Output[/bold]", border_style="green")
    )


def get_version():
    """Get the current version of the package."""
    return "QuantaLogic version: 1.0.0"


if __name__ == "__main__":
    main()

```

---
