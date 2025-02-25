"""Module for agent configuration and creation."""

# Standard library imports

# Local application imports
import os
import logging
import json
from dotenv import load_dotenv
from typing import Any

from quantalogic.agent import Agent
from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.memory import AgentMemory
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
    SQLQueryTool,
    ComposioTool,
    CloneRepoTool,
    GitOperationsTool,
    SQLQueryToolAdvanced,
    MarkdownToPdfTool,
    MarkdownToPptxTool,
    MarkdownToHtmlTool,
    MarkdownToEpubTool,
    MarkdownToIpynbTool,
    MarkdownToLatexTool,
    MarkdownToDocxTool,
    BitbucketCloneTool,
    BitbucketOperationsTool,
    CSVProcessorTool,
    PrepareDownloadTool,
    MermaidValidatorTool,
    NasaNeoWsTool,
    NasaApodTool,
    ProductHuntTool,
    RagTool
)
from composio import ComposioToolSet, Action

load_dotenv()

MODEL_NAME = "deepseek/deepseek-chat"

logger = logging.getLogger(__name__)

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
        SafePythonInterpreterTool(allowed_modules=["math", "numpy"])
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


def create_custom_agent(
    model_name: str, 
    vision_model_name: str | None = None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None,
    specific_expertise: str = "",
    tools: list[Any] | None = None,
    memory: AgentMemory | None = None
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

    storage_dir = os.path.join(os.path.dirname(__file__), "storage", "rag")
    os.makedirs(storage_dir, exist_ok=True)
    
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
            model_name=params.get("vision_model_name") or vision_model_name,
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        "llm_image_generation": lambda params: LLMImageGenerationTool(
            # provider=params.get("provider", "dall-e"),
            provider="dall-e",
            # model_name=params.get("model_name", "openai/dall-e-3"),
            model_name="openai/dall-e-3",
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
            # model_name=params.get("model_name", model_name),
            # on_token=console_print_token if not no_stream else None,
            # event_emitter=event_emitter
        ),
        "presentation_llm": lambda params: PresentationLLMTool(
            model_name=params.get("model_name", model_name),
            additional_info=params.get("additional_info", ""),
            on_token=console_print_token if not no_stream else None,
            event_emitter=event_emitter
        ),
        "sequence": lambda params: SequenceTool(
            model_name=params.get("model_name", model_name),
            on_token=console_print_token if not no_stream else None,
            # event_emitter=event_emitter
        ),
        "sql_query": lambda params: SQLQueryTool(
            connection_string=params.get("connection_string", ""),
            model_name=params.get("model_name", model_name),
            on_token=console_print_token if not no_stream else None,
            # event_emitter=event_emitter
        ),
        "sql_query_advanced": lambda params: SQLQueryToolAdvanced(
            connection_string=params.get("connection_string", ""),
            model_name=params.get("model_name", model_name),
            on_token=console_print_token if not no_stream else None,
            # event_emitter=event_emitter
        ),
        "clone_repo_tool": lambda params: CloneRepoTool(auth_token=params.get("auth_token", "")),
        "bitbucket_clone_repo_tool": lambda params: BitbucketCloneTool(access_token=params.get("access_token", "")),
        "bitbucket_operations_tool": lambda params: BitbucketOperationsTool(access_token=params.get("access_token", "")),
        "git_operations_tool": lambda params: GitOperationsTool(auth_token=params.get("auth_token", "")),
        "markdown_to_pdf": lambda params: MarkdownToPdfTool(),
        "markdown_to_pptx": lambda params: MarkdownToPptxTool(),
        "markdown_to_html": lambda params: MarkdownToHtmlTool(),
        "markdown_to_epub": lambda params: MarkdownToEpubTool(),
        "markdown_to_ipynb": lambda params: MarkdownToIpynbTool(),
        "markdown_to_latex": lambda params: MarkdownToLatexTool(),
        "markdown_to_docx": lambda params: MarkdownToDocxTool(),
        "csv_processor": lambda params: CSVProcessorTool(),
        "mermaid_validator_tool": lambda params: MermaidValidatorTool(),
        "download_file_tool": lambda params: PrepareDownloadTool(),
        "email_tool": lambda params: ComposioTool(
            action="GMAIL_SEND_EMAIL",
            name="email_tool",
            description="Send emails via Gmail",
            need_validation=False
        ),
        "callendar_tool": lambda params: ComposioTool(
            action="GOOGLECALENDAR_CREATE_EVENT",
            name="callendar_tool",
            description="Create events in Google Calendar",
            need_validation=False
        ),
        "weather_tool": lambda params: ComposioTool(
            action="WEATHERMAP_WEATHER",
            name="weather_tool",
            description="Get weather information for a location"
        ),
        "nasa_neows_tool": lambda params: NasaNeoWsTool(),
        "nasa_apod_tool": lambda params: NasaApodTool(),
        "product_hunt_tool": lambda params : ProductHuntTool(),
        "rag_tool": lambda params: RagTool(
            vector_store=params.get("vector_store", "chroma"),
            embedding_model=params.get("embedding_model", "openai"),
            persist_dir=storage_dir,
            document_paths=params.get("document_paths", [])
        )
    }

    # Define write tools that should trigger automatic download tool addition
    WRITE_TOOLS = {"write_file", "edit_whole_content", "replace_in_file"}
    
    agent_tools = []
    has_write_tool = any(
        tool_config.get("type") in WRITE_TOOLS 
        for tool_config in (tools or [])
    )

    # Add tools only if they are provided
    if tools:
        for tool_config in tools:
            tool_type = tool_config.get("type")
            logger.debug(f"Processing tool type: {tool_type}")
            
            if tool_type in tool_mapping:
                try:
                    # Get tool parameters or empty dict if not provided
                    tool_params = tool_config.get("parameters", {})
                    
                    # Create tool instance with parameters
                    tool = tool_mapping[tool_type](tool_params)
                    logger.debug(f"Created tool instance: {tool}")
                    
                    if tool:  # Some tools (like llm_vision) might return None
                        agent_tools.append(tool)
                        logger.info(f"Added tool: {tool_type}")
                except Exception as e:
                    logger.error(f"Failed to create tool {tool_type}: {str(e)}")

    # If any write tool was added, also add the download tool
    if has_write_tool:
        try:
            agent_tools.append(PrepareDownloadTool())
            logger.info("Added download tool automatically")
        except Exception as e:
            logger.error(f"Failed to add download tool: {str(e)}")

    agent_tools.append(TaskCompleteTool())
    
    return Agent(
        model_name=model_name,
        tools=agent_tools,
        event_emitter=event_emitter,
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
        specific_expertise=specific_expertise,
        memory=memory,
    )
