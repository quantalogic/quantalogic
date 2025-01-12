"""Module for agent configuration and creation."""

# Standard library imports

# Local application imports
from quantalogic.agent import Agent
from quantalogic.coding_agent import create_coding_agent
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    AgentTool,
    DownloadHttpFileTool,
    DuckDuckGoSearchTool,
    EditWholeContentTool,
    ExecuteBashCommandTool,
    InputQuestionTool,
    ListDirectoryTool,
    LLMTool,
    LLMVisionTool,
    MarkitdownTool,
    NodeJsTool,
    PythonTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReplaceInFileTool,
    RipgrepTool,
    SearchDefinitionNames,
    TaskCompleteTool,
    WikipediaSearchTool,
    WriteFileTool,
)

MODEL_NAME = "deepseek/deepseek-chat"


def create_agent(
    model_name: str, 
    vision_model_name: str | None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.

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
    ]

    if vision_model_name:
        tools.append(LLMVisionTool(model_name=vision_model_name, on_token=console_print_token if not no_stream else None))

    return Agent(
        model_name=model_name,
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration,
    )


def create_interpreter_agent(
    model_name: str, 
    vision_model_name: str | None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None
) -> Agent:
    """Create an interpreter agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.

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
    ]
    return Agent(
        model_name=model_name, 
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration
    )


def create_full_agent(
    model_name: str, 
    vision_model_name: str | None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None
) -> Agent:
    """Create an agent with the specified model and many tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.

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
    ]

    if vision_model_name:
        tools.append(LLMVisionTool(model_name=vision_model_name,on_token=console_print_token if not no_stream else None))

    return Agent(
        model_name=model_name,
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration,
    )


def create_orchestrator_agent(
    model_name: str, 
    vision_model_name: str | None = None, 
    no_stream: bool = False, 
    compact_every_n_iteration: int | None = None
) -> Agent:
    """Create an agent with the specified model and tools.

    Args:
        model_name (str): Name of the model to use
        vision_model_name (str | None): Name of the vision model to use
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.

    Returns:
        Agent: An agent with the specified model and tools
    """
    # Rebuild AgentTool to resolve forward references
    AgentTool.model_rebuild()

    coding_agent_instance = create_coding_agent(model_name)

    tools = [
        TaskCompleteTool(),
        ListDirectoryTool(),
        ReadFileBlockTool(),
        RipgrepTool(),
        SearchDefinitionNames(),
        LLMTool(model_name=model_name, on_token=console_print_token if not no_stream else None),
        AgentTool(agent=coding_agent_instance, agent_role="software expert", name="coder_agent_tool"),
    ]

    if vision_model_name:
        tools.append(LLMVisionTool(model_name=vision_model_name, on_token=console_print_token if not no_stream else None))

    return Agent(
        model_name=model_name,
        tools=tools,
        compact_every_n_iterations=compact_every_n_iteration,
    )
