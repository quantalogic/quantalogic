from quantalogic.agent import Agent
from quantalogic.tools import (
    EditWholeContentTool,
    ExecuteBashCommandTool,
    InputQuestionTool,
    ListDirectoryTool,
    LLMTool,
    LLMVisionTool,
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


def create_coding_agent(model_name: str, vision_model_name: str | None = None, basic: bool = False) -> Agent:
    """Creates and configures a coding agent with a comprehensive set of tools.

    Args:
        model_name (str): Name of the language model to use for the agent's core capabilities
        vision_model_name (str | None): Name of the vision model to use for the agent's core capabilities
        basic (bool, optional): If True, the agent will be configured with a basic set of tools.

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
        "Exercise caution with the surrounding context during search/replace operations."
        "For refactoring tasks, take the time to develop a comprehensive plan for implementing the proposed changes."
    )
    quantalogic_rules_file_content = get_quantalogic_rules_file_content()

    if quantalogic_rules_file_content:
        specific_expertise += "\n\n" "<coding_rules>\n" f"{quantalogic_rules_file_content}" "\n</coding_rules>\n"

    tools = [
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
        ReadFileTool(),
        ExecuteBashCommandTool(),
        InputQuestionTool(),
    ]

    if vision_model_name:
        tools.append(LLMVisionTool(model_name=vision_model_name))

    if not basic:
        tools.append(
            LLMTool(
                model_name=model_name,
                system_prompt="You are a software expert, your role is to answer coding questions.",
                name="coding_consultant",  # Handles implementation-level coding questions                
            )
        )
        tools.append(
            LLMTool(
                model_name=model_name,
                system_prompt="You are a software architect, your role is to answer software architecture questions.",
                name="software_architect",  # Handles system design and architecture questions
            )
        )

    return Agent(
        model_name=model_name,
        tools=tools,
        specific_expertise=specific_expertise,
        get_environment=get_coding_environment,
    )
