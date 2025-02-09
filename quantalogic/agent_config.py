"""Module for agent configuration and creation."""

# Standard library imports

# Local application imports
from typing import Any
from dotenv import load_dotenv

from quantalogic.agent import Agent
from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.tools import (
    AgentTool,
    DownloadHttpFileTool,
    DuckDuckGoSearchTool,
    EditWholeContentTool,
    ExecuteBashCommandTool,
    InputQuestionTool,
    ListDirectoryTool,
    LLMImageGenerationTool,
    LLMTool,
    LLMVisionTool,
    MarkitdownTool,
    NodeJsTool,
    PythonTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReadHTMLTool,
    ReplaceInFileTool,
    RipgrepTool,
    SafePythonInterpreterTool, 
    SearchDefinitionNames,
    TaskCompleteTool,
    WikipediaSearchTool,
    WriteFileTool,
    GoogleNewsTool,
    PresentationLLMTool,
    SequenceTool,
    SQLQueryTool
)

load_dotenv()

MODEL_NAME = "deepseek/deepseek-chat"


_current_model_name: str = ""

def get_current_model() -> str:
    """Retrieve the currently active model name."""
    if not _current_model_name:
        raise ValueError("No model initialized")
    return _current_model_name

def create_agent(
    model_name: str, 
    vision_model_name: str | None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None
) -> Agent:
    global _current_model_name
    _current_model_name = model_name
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: An agent with the specified model and tools
    """
    tools = [
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
        SearchDefinitionNames(),
        MarkitdownTool(),
        LLMTool(model_name=model_name, on_token=console_print_token if not no_stream else None),
        DownloadHttpFileTool(), 
        LLMImageGenerationTool(
                provider="dall-e",
                model_name="openai/dall-e-3",
                on_token=console_print_token if not no_stream else None
            ),
        ReadHTMLTool(),
       # SafePythonInterpreterTool(allowed_modules=["math", "numpy"])
    ]

    if vision_model_name:
        tools.append(LLMVisionTool(model_name=vision_model_name, on_token=console_print_token if not no_stream else None))

    return Agent(
        model_name=model_name,
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
    )


def create_interpreter_agent(
    model_name: str, 
    vision_model_name: str | None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None
) -> Agent:
    """Create an interpreter agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: An interpreter agent with the specified model and tools
    """
    tools = [
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
        PythonTool(),
        NodeJsTool(),
        SearchDefinitionNames(),
        MarkitdownTool(),
        LLMTool(model_name=model_name, on_token=console_print_token if not no_stream else None),
        DownloadHttpFileTool(),
        ReadHTMLTool(),
    ]
    return Agent(
        model_name=model_name, 
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
    )


def create_full_agent(
    model_name: str, 
    vision_model_name: str | None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None
) -> Agent:
    """Create an agent with the specified model and many tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: An agent with the specified model and tools

    """
    tools = [
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
        PythonTool(),
        NodeJsTool(),
        SearchDefinitionNames(),
        MarkitdownTool(),
        LLMTool(model_name=model_name, on_token=console_print_token if not no_stream else None),
        DownloadHttpFileTool(),
        WikipediaSearchTool(),
        DuckDuckGoSearchTool(),
        ReadHTMLTool(),
      #  SafePythonInterpreterTool(allowed_modules=["math", "numpy"])
    ]

    if vision_model_name:
        tools.append(LLMVisionTool(model_name=vision_model_name,on_token=console_print_token if not no_stream else None))

    return Agent(
        model_name=model_name,
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
    )


def create_basic_agent(
    model_name: str, 
    vision_model_name: str | None = None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: An agent with the specified model and tools
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()


    tools = [
        TaskCompleteTool(),
        ListDirectoryTool(),
        ReadFileBlockTool(),
        SearchDefinitionNames(),
        ReadFileTool(),
        ReplaceInFileTool(),
        WriteFileTool(),
        EditWholeContentTool(),
        ReplaceInFileTool(),
        InputQuestionTool(),
        ExecuteBashCommandTool(),
        LLMTool(model_name=model_name, on_token=console_print_token if not no_stream else None),
        ReadHTMLTool(),
    #    SafePythonInterpreterTool(allowed_modules=["math", "numpy"])
    ]

    if vision_model_name:
        tools.append(LLMVisionTool(model_name=vision_model_name, on_token=console_print_token if not no_stream else None))

    return Agent(
        model_name=model_name,
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
    )

def create_minimal_agent(
    model_name: str, 
    vision_model_name: str | None = None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: An agent with the specified model and tools
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()

    # Create event emitter
    event_emitter = EventEmitter()

    tools = [
        LLMTool(
            model_name=model_name, 
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        DownloadHttpFileTool(),
        WikipediaSearchTool(),
        DuckDuckGoSearchTool(),
        ReadHTMLTool(),
        SearchDefinitionNames(),  
        ReadFileBlockTool(),
        WriteFileTool(),
        ReadFileTool(),
        TaskCompleteTool(), 
    ]

    if vision_model_name:
        tools.append(
            LLMVisionTool(
                model_name=vision_model_name, 
                on_token=console_print_token if not no_stream else None,
                event_emitter=event_emitter
            )
        )

    return Agent(
        model_name=model_name,
        tools=tools,
        event_emitter=event_emitter,  # Pass the event emitter to the agent
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
    )

def create_news_agent(
    model_name: str, 
    vision_model_name: str | None = None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None,
    specific_expertise: str = "Expert agent in getting relevant news and staying updated with the latest news",
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: An agent with the specified model and tools
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()

    # Create event emitter
    event_emitter = EventEmitter()

    tools = [
        LLMTool(
            model_name=model_name, 
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        DownloadHttpFileTool(),
        # WikipediaSearchTool(),
        # DuckDuckGoSearchTool(),
        GoogleNewsTool(
            model_name=model_name,
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        PresentationLLMTool(
            model_name=model_name,
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        TaskCompleteTool(), 
    ]

    if vision_model_name:
        tools.append(
            LLMVisionTool(
                model_name=vision_model_name, 
                on_token=console_print_token if not no_stream else None,
                event_emitter=event_emitter
            )
        )

    return Agent(
        model_name=model_name,
        tools=tools,
        event_emitter=event_emitter,  # Pass the event emitter to the agent
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
        specific_expertise=specific_expertise
    )

def create_image_generation_agent(
    model_name: str, 
    vision_model_name: str | None = None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None,
    specific_expertise: str = "Expert agent in image generation and image editing with DALL-E",
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: An agent with the specified model and tools
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()

    # Create event emitter
    event_emitter = EventEmitter()

    tools = [
        LLMTool(
            model_name=model_name, 
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        LLMImageGenerationTool(
                provider="dall-e",
                model_name="openai/dall-e-3",
                on_token=console_print_token if not no_stream else None
            ), 
        PresentationLLMTool(
            model_name=model_name,
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        LLMVisionTool(
            model_name="gpt-4o-mini", 
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        TaskCompleteTool(), 
    ]

    """ if vision_model_name:
        tools.append(
            LLMVisionTool(
                model_name=vision_model_name, 
                on_token=console_print_token if not no_stream else None,
                event_emitter=event_emitter
            )
        ) """

    return Agent(
        model_name=model_name,
        tools=tools,
        event_emitter=event_emitter,  # Pass the event emitter to the agent
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
        specific_expertise=specific_expertise
    )


def create_custom_agent(
    model_name: str, 
    vision_model_name: str | None = None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None,
    specific_expertise: str = "",
    tools: list[Any] | None = None,
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.
        specific_expertise (str, optional): Specific expertise of the agent.
        tools (list[Any], optional): List of tool configurations to add to the agent.
            Each tool config should have:
            - type: str - The type of tool
            - parameters: dict - The parameters required for the tool

    Returns:
        Agent: An agent with the specified model and tools
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()

    # Create event emitter
    event_emitter = EventEmitter()

    # Define tool mapping with their parameter requirements
    tool_mapping = {
        "llm": lambda params: LLMTool(
            model_name=params.get("model_name", model_name),
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        "llm_vision": lambda params: LLMVisionTool(
            model_name=params.get("vision_model_name", vision_model_name),
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ) if vision_model_name else None,
        "llm_image_generation": lambda params: LLMImageGenerationTool(
            provider=params.get("provider", "dall-e"),
            model_name=params.get("model_name", "openai/dall-e-3"),
            on_token=console_print_token if not no_stream else None,
            # event_emitter=event_emitter
        ),
        "download_http_file": lambda params: DownloadHttpFileTool(),
        "duck_duck_go_search": lambda params: DuckDuckGoSearchTool(),
        "edit_whole_content": lambda params: EditWholeContentTool(),
        "execute_bash_command": lambda params: ExecuteBashCommandTool(),
        "input_question": lambda params: InputQuestionTool(),
        "list_directory": lambda params: ListDirectoryTool(),
        "markitdown": lambda params: MarkitdownTool(),
        "nodejs": lambda params: NodeJsTool(),
        "python": lambda params: PythonTool(),
        "read_file_block": lambda params: ReadFileBlockTool(),
        "read_file": lambda params: ReadFileTool(),
        "read_html": lambda params: ReadHTMLTool(),
        "replace_in_file": lambda params: ReplaceInFileTool(),
        "ripgrep": lambda params: RipgrepTool(),
        "safe_python_interpreter": lambda params: SafePythonInterpreterTool(),
        "search_definition_names": lambda params: SearchDefinitionNames(),
        "wikipedia_search": lambda params: WikipediaSearchTool(),
        "write_file": lambda params: WriteFileTool(),
        "google_news": lambda params: GoogleNewsTool(
            model_name=params.get("model_name", model_name),
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        "presentation_llm": lambda params: PresentationLLMTool(
            model_name=params.get("model_name", model_name),
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        "sequence": lambda params: SequenceTool(
            model_name=params.get("model_name", model_name),
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        "sql_query": lambda params: SQLQueryTool(
            connection_string=params.get("connection_string", ""),
            model_name=params.get("model_name", model_name),
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        "task_complete": lambda params: TaskCompleteTool()
    }
    
    # Initialize empty tools list
    agent_tools = []

    # Add tools only if they are provided
    if tools:
        for tool_config in tools:
            tool_type = tool_config.get("type")
            if tool_type in tool_mapping:
                # Get tool parameters or empty dict if not provided
                tool_params = tool_config.get("parameters", {})
                
                # Create tool instance with parameters
                tool = tool_mapping[tool_type](tool_params)
                
                if tool:  # Some tools (like llm_vision) might return None
                    agent_tools.append(tool)

    # Always add TaskCompleteTool as it's required for the agent to function
    agent_tools.append(TaskCompleteTool())

    return Agent(
        model_name=model_name,
        tools=agent_tools,
        event_emitter=event_emitter,
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
        specific_expertise=specific_expertise
    )
