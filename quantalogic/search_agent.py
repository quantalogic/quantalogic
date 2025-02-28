from quantalogic.agent import Agent
from quantalogic.tools import (
    DuckDuckGoSearchTool,
    InputQuestionTool,
    MarkitdownTool,
    ReadFileBlockTool,
    ReadFileTool,
    RipgrepTool,
    SerpApiSearchTool,
    TaskCompleteTool,
    WikipediaSearchTool,
)


def create_search_agent(
    model_name: str,
    mode_full: bool = False,
    no_stream: bool = False,
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None,
) -> Agent:
    """Creates and configures a search agent with web, knowledge, and privacy-focused search tools.

    Args:
        model_name (str): Name of the language model to use for the agent's core capabilities
        mode_full (bool, optional): If True, the agent will be configured with a full set of tools.
        no_stream (bool, optional): If True, the agent will not stream results.
        compact_every_n_iteration (int | None, optional): Frequency of memory compaction.
        max_tokens_working_memory (int | None, optional): Maximum tokens for working memory.

    Returns:
        Agent: A fully configured search agent instance with:
            - Web search capabilities (SerpAPI, DuckDuckGo)
            - Knowledge search capabilities (Wikipedia)
            - Basic interaction tools
    """
    specific_expertise = (
        "Search expert focused on web and knowledge search operations."
        "Specializes in finding and summarizing information from various sources."
    )

    tools = [
        # Search tools
        DuckDuckGoSearchTool(),  # Privacy-focused web search
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

    if mode_full:
        tools.extend(
            [
                # Search tools
                SerpApiSearchTool(),  # Web search capabilities
            ]
        )

    return Agent(
        model_name=model_name,
        tools=tools,
        specific_expertise=specific_expertise,
        compact_every_n_iterations=compact_every_n_iteration,
        max_tokens_working_memory=max_tokens_working_memory,
    )
