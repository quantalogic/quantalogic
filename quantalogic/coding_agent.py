from quantalogic.agent import Agent
from quantalogic.tools import (
    EditWholeContentTool,
    ExecuteBashCommandTool,
    ListDirectoryTool,
    LLMTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReplaceInFileTool,
    RipgrepTool,
    SearchDefinitionNames,
    TaskCompleteTool,
    WriteFileTool,
)
from quantalogic.utils import get_coding_environment
from quantalogic.utils.get_quantalogic_rules_content import get_quantalogic_rules_file_content


def create_coding_agent(model_name: str) -> Agent:
    """Creates and configures a coding agent with a comprehensive set of tools.

    Args:
        model_name (str): Name of the language model to use for the agent's core capabilities

    Returns:
        Agent: A fully configured coding agent instance with:
            - File manipulation tools
            - Code search capabilities
            - Specialized language model tools for coding and architecture
    """
    specific_expertise = (
        "Software expert focused on pragmatic solutions."
        "Validates codebase pre/post changes."
        "Employs SearchDefinitionNames for code search; ReplaceInFileTool for updates."
        "For refactoring tasks, self reflect on a detailed plan to implement the proposed changes."
    )
    quantalogic_rules_file_content = get_quantalogic_rules_file_content()

    if quantalogic_rules_file_content:
        specific_expertise += (
            "\n\n"
            "<coding_rules>\n"
            f"{quantalogic_rules_file_content}"
            "\n</coding_rules>\n"
        )

    return Agent(
        model_name=model_name,
        tools=[
            # Core file manipulation tools
            TaskCompleteTool(),  # Marks task completion
            ReadFileBlockTool(),  # Reads specific file sections
            WriteFileTool(),  # Creates new files
            ReplaceInFileTool(),  # Updates file sections
            EditWholeContentTool(),  # Modifies entire files
            # Code navigation and search tools
            ListDirectoryTool(),  # Lists directory contents
            RipgrepTool(),  # Searches code with regex
            SearchDefinitionNames(),  # Finds code definitions
            # Specialized language model tools
            LLMTool(
                model_name=model_name,
                system_prompt="You are a software expert, your role is to answer coding questions.",
                name="coding_consultant",  # Handles implementation-level coding questions
            ),
            LLMTool(
                model_name=model_name,
                system_prompt="You are a software architect, your role is to answer software architecture questions.",
                name="software_architect",  # Handles system design and architecture questions
            ),
            ReadFileTool(),
            ExecuteBashCommandTool(),
        ],
        specific_expertise=specific_expertise,
        get_environment=get_coding_environment,
    )
