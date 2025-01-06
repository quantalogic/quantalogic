"""Module for agent configuration and creation."""

# Standard library imports

# Local application imports
from quantalogic.agent import Agent
from quantalogic.coding_agent import create_coding_agent
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

MODEL_NAME = "deepseek/deepseek-chat"


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
            SearchDefinitionNames(),
            MarkitdownTool(),
            LLMTool(model_name=model_name),
            DownloadHttpFileTool(),
        ],
    )


def create_interpreter_agent(model_name: str) -> Agent:
    """Create an interpreter agent with the specified model and tools.

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
            PythonTool(),
            NodeJsTool(),
            SearchDefinitionNames(),
            DownloadHttpFileTool(),
        ],
    )


def create_full_agent(model_name: str) -> Agent:
    """Create an agent with the specified model and many tools.

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
            PythonTool(),
            NodeJsTool(),
            SearchDefinitionNames(),
            MarkitdownTool(),
            LLMTool(model_name=model_name),
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


