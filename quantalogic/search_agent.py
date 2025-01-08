from quantalogic.agent import Agent
from quantalogic.tools import InputQuestionTool, SerpApiSearchTool, TaskCompleteTool, WikipediaSearchTool, ReadFileBlockTool,ReadFileTool, MarkitdownTool, RipgrepTool


def create_search_agent(model_name: str) -> Agent:
    """Creates and configures a search agent with web and knowledge search tools.

    Args:
        model_name (str): Name of the language model to use for the agent's core capabilities

    Returns:
        Agent: A fully configured search agent instance with:
            - Web search capabilities (SerpAPI)
            - Knowledge search capabilities (Wikipedia)
            - Basic interaction tools
    """
    specific_expertise = (
        "Search expert focused on web and knowledge search operations."
        "Specializes in finding and summarizing information from various sources."
    )

    tools = [
        # Search tools
        SerpApiSearchTool(),  # Web search capabilities
        WikipediaSearchTool(),  # Knowledge search capabilities
        # Basic interaction tools
        TaskCompleteTool(),  # Marks task completion
        InputQuestionTool(),  # Handles user queries
        # LLM tools
        ReadFileBlockTool(),  # Reads specific file sections
        ReadFileTool(),  # Reads entire file
        MarkitdownTool(),  # Converts markdown to text
        # Code search tools
        RipgrepTool(),  # Code search capabilities
    ]

    return Agent(
        model_name=model_name,
        tools=tools,
        specific_expertise=specific_expertise,
    )
