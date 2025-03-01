import importlib
import os
from typing import Any, Optional, Type

from loguru import logger

from quantalogic.agent import Agent, AgentMemory
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.event_emitter import EventEmitter
from quantalogic.tools.tool import Tool

# Configure loguru to output debug messages
logger.remove()  # Remove default handler
logger.add(sink=lambda msg: print(msg, end=""), level="DEBUG")  # Add a new handler that prints to console


def _import_tool(module_path: str, class_name: str) -> Type[Tool]:
    """
    Import a tool class from a module path using standard Python imports.
    
    Args:
        module_path: The module path to import from
        class_name: The name of the class to import
        
    Returns:
        The imported tool class, or None if import fails
    """
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except ImportError as e:
        logger.warning(f"Failed to import {class_name} from {module_path}: {str(e)}")
        return None
    except AttributeError as e:
        logger.warning(f"Failed to find {class_name} in {module_path}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error importing {class_name} from {module_path}: {str(e)}")
        return None

# Helper function to create tool instances
def create_tool_instance(tool_class, **kwargs):
    """
    Creates an instance of a tool class with appropriate parameters.
    
    Args:
        tool_class: The tool class to instantiate
        **kwargs: Parameters to pass to the tool constructor
        
    Returns:
        An instance of the tool class, or None if instantiation fails
    """
    if tool_class is None:
        return None
        
    try:
        # Extract the name from the class name if not provided
        if 'name' not in kwargs:
            class_name = tool_class.__name__
            kwargs['name'] = class_name.lower().replace('tool', '')
            
        # Create and return the tool instance
        instance = tool_class(**kwargs)
        logger.debug(f"Successfully created tool instance: {kwargs.get('name')}")
        return instance
    except Exception as e:
        logger.error(f"Failed to instantiate {tool_class.__name__}: {str(e)}")
        return None

# Lazy loading tool imports using a dictionary of functions that return tool classes
TOOL_IMPORTS = {
    # LLM Tools
    "llm": lambda: _import_tool("quantalogic.tools.llm_tool", "LLMTool"),
    "llm_vision": lambda: _import_tool("quantalogic.tools.llm_tool", "LLMVisionTool"),
    "llm_image_generation": lambda: _import_tool("quantalogic.tools.llm_tool", "LLMImageGenerationTool"),
    
    # File Tools
    "download_http_file": lambda: _import_tool("quantalogic.tools.download_file_tool", "PrepareDownloadTool"),
    "write_file": lambda: _import_tool("quantalogic.tools.write_file_tool", "WriteFileTool"),
    "edit_whole_content": lambda: _import_tool("quantalogic.tools.file_tools", "EditWholeContentTool"),
    "read_file_block": lambda: _import_tool("quantalogic.tools.file_tools", "ReadFileBlockTool"),
    "read_file": lambda: _import_tool("quantalogic.tools.file_tools", "ReadFileTool"),
    "replace_in_file": lambda: _import_tool("quantalogic.tools.file_tools", "ReplaceInFileTool"),
    "list_directory": lambda: _import_tool("quantalogic.tools.file_tools", "ListDirectoryTool"),
    
    # Search Tools
    "duck_duck_go_search": lambda: _import_tool("quantalogic.tools", "DuckDuckGoSearchTool"),
    "wikipedia_search": lambda: _import_tool("quantalogic.tools", "WikipediaSearchTool"),
    "google_news": lambda: _import_tool("quantalogic.tools", "GoogleNewsTool"),
    "search_definition_names": lambda: _import_tool("quantalogic.tools", "SearchDefinitionNames"),
    "ripgrep": lambda: _import_tool("quantalogic.tools", "RipgrepTool"),
    
    # Execution Tools
    "execute_bash_command": lambda: _import_tool("quantalogic.tools.execution_tools", "ExecuteBashCommandTool"),
    "nodejs": lambda: _import_tool("quantalogic.tools.execution_tools", "NodeJsTool"),
    "python": lambda: _import_tool("quantalogic.tools.execution_tools", "PythonTool"),
    "safe_python_interpreter": lambda: _import_tool("quantalogic.tools.execution_tools", "SafePythonInterpreterTool"),
    
    # Database Tools
    "sql_query": lambda: _import_tool("quantalogic.tools.database", "SQLQueryTool"),
    "sql_query_advanced": lambda: _import_tool("quantalogic.tools.database", "SQLQueryToolAdvanced"),
    
    # Document Tools
    "markdown_to_pdf": lambda: _import_tool("quantalogic.tools.document_tools", "MarkdownToPdfTool"),
    "markdown_to_pptx": lambda: _import_tool("quantalogic.tools.document_tools", "MarkdownToPptxTool"),
    "markdown_to_html": lambda: _import_tool("quantalogic.tools.document_tools", "MarkdownToHtmlTool"),
    "markdown_to_epub": lambda: _import_tool("quantalogic.tools.document_tools", "MarkdownToEpubTool"),
    "markdown_to_ipynb": lambda: _import_tool("quantalogic.tools.document_tools", "MarkdownToIpynbTool"),
    "markdown_to_latex": lambda: _import_tool("quantalogic.tools.document_tools", "MarkdownToLatexTool"),
    "markdown_to_docx": lambda: _import_tool("quantalogic.tools.document_tools", "MarkdownToDocxTool"),
    
    # Git Tools
    "clone_repo_tool": lambda: _import_tool("quantalogic.tools.git", "CloneRepoTool"),
    "bitbucket_clone_repo_tool": lambda: _import_tool("quantalogic.tools.git", "BitbucketCloneTool"),
    "bitbucket_operations_tool": lambda: _import_tool("quantalogic.tools.git", "BitbucketOperationsTool"),
    "git_operations_tool": lambda: _import_tool("quantalogic.tools.git", "GitOperationsTool"),
    
    # NASA Tools
    "nasa_neows_tool": lambda: _import_tool("quantalogic.tools.nasa_packages", "NasaNeoWsTool"),
    "nasa_apod_tool": lambda: _import_tool("quantalogic.tools.nasa_packages", "NasaApodTool"),
    
    # Composio Tools
    "email_tool": lambda: _import_tool("quantalogic.tools.composio", "ComposioTool"),
    "callendar_tool": lambda: _import_tool("quantalogic.tools.composio", "ComposioTool"),
    "weather_tool": lambda: _import_tool("quantalogic.tools.composio", "ComposioTool"),
    
    # Product Hunt Tools
    "product_hunt_tool": lambda: _import_tool("quantalogic.tools.product_hunt", "ProductHuntTool"),
    
    # RAG Tools
    "rag_tool": lambda: _import_tool("quantalogic.tools.rag_tool", "RagTool"),
    
    # Utility Tools
    "task_complete": lambda: _import_tool("quantalogic.tools.task_complete_tool", "TaskCompleteTool"),
    "input_question": lambda: _import_tool("quantalogic.tools.utilities", "InputQuestionTool"),
    "markitdown": lambda: _import_tool("quantalogic.tools.utilities", "MarkitdownTool"),
    "read_html": lambda: _import_tool("quantalogic.tools.utilities", "ReadHTMLTool"),
    "presentation_llm": lambda: _import_tool("quantalogic.tools.presentation_tools", "PresentationLLMTool"),
    "sequence": lambda: _import_tool("quantalogic.tools.utilities", "SequenceTool"),
    "csv_processor": lambda: _import_tool("quantalogic.tools.utilities", "CSVProcessorTool"),
    "mermaid_validator_tool": lambda: _import_tool("quantalogic.tools.utilities", "MermaidValidatorTool"),
    "download_file_tool": lambda: _import_tool("quantalogic.tools.download_file_tool", "PrepareDownloadTool"),
}

def create_custom_agent(
    model_name: str,
    vision_model_name: Optional[str] = None,
    no_stream: bool = False,
    compact_every_n_iteration: Optional[int] = None,
    max_tokens_working_memory: Optional[int] = None,
    specific_expertise: str = "",
    tools: Optional[list[dict[str, Any]]] = None,
    memory: Optional[AgentMemory] = None
) -> Agent:
    """Create an agent with lazy-loaded tools and graceful error handling.

    Args:
        model_name: Name of the model to use
        vision_model_name: Name of the vision model to use
        no_stream: If True, disable streaming
        compact_every_n_iteration: Frequency of memory compaction
        max_tokens_working_memory: Maximum tokens for working memory
        specific_expertise: Specific expertise of the agent
        tools: List of tool configurations with type and parameters
        memory: Memory object to use for the agent

    Returns:
        Agent: Configured agent instance
    """
    # Create storage directory for RAG
    storage_dir = os.path.join(os.path.dirname(__file__), "storage", "rag")
    os.makedirs(storage_dir, exist_ok=True)

    # Create event emitter
    event_emitter = EventEmitter()

    # Define tool configurations using create_tool_instance for proper instantiation
    tool_configs = {
        "llm": lambda params: create_tool_instance(TOOL_IMPORTS["llm"](), **params),
        "llm_vision": lambda params: create_tool_instance(TOOL_IMPORTS["llm_vision"](), **params) if vision_model_name else None,
        "llm_image_generation": lambda params: create_tool_instance(TOOL_IMPORTS["llm_image_generation"](), **params),
        "download_http_file": lambda params: create_tool_instance(TOOL_IMPORTS["download_http_file"](), **params),
        "duck_duck_go_search": lambda params: create_tool_instance(TOOL_IMPORTS["duck_duck_go_search"](), **params),
        "write_file": lambda params: create_tool_instance(TOOL_IMPORTS["write_file"](), **params),
        "task_complete": lambda params: create_tool_instance(TOOL_IMPORTS["task_complete"](), **params),
        "edit_whole_content": lambda params: create_tool_instance(TOOL_IMPORTS["edit_whole_content"](), name="edit_whole_content", **params),
        "execute_bash_command": lambda params: create_tool_instance(TOOL_IMPORTS["execute_bash_command"](), name="execute_bash_command", **params),
        "input_question": lambda params: create_tool_instance(TOOL_IMPORTS["input_question"](), name="input_question", **params),
        "list_directory": lambda params: create_tool_instance(TOOL_IMPORTS["list_directory"](), name="list_directory", **params),
        "markitdown": lambda params: create_tool_instance(TOOL_IMPORTS["markitdown"](), name="markitdown", **params),
        "nodejs": lambda params: create_tool_instance(TOOL_IMPORTS["nodejs"](), name="nodejs", **params),
        "python": lambda params: create_tool_instance(TOOL_IMPORTS["python"](), name="python", **params),
        "read_file_block": lambda params: create_tool_instance(TOOL_IMPORTS["read_file_block"](), name="read_file_block", **params),
        "read_file": lambda params: create_tool_instance(TOOL_IMPORTS["read_file"](), name="read_file", **params),
        "read_html": lambda params: create_tool_instance(TOOL_IMPORTS["read_html"](), name="read_html", **params),
        "replace_in_file": lambda params: create_tool_instance(TOOL_IMPORTS["replace_in_file"](), name="replace_in_file", **params),
        "ripgrep": lambda params: create_tool_instance(TOOL_IMPORTS["ripgrep"](), name="ripgrep", **params),
        "safe_python_interpreter": lambda params: create_tool_instance(TOOL_IMPORTS["safe_python_interpreter"](), name="safe_python_interpreter", **params),
        "search_definition_names": lambda params: create_tool_instance(TOOL_IMPORTS["search_definition_names"](), name="search_definition_names", **params),
        "wikipedia_search": lambda params: create_tool_instance(TOOL_IMPORTS["wikipedia_search"](), name="wikipedia_search", **params),
        "google_news": lambda params: create_tool_instance(TOOL_IMPORTS["google_news"](), name="google_news", **params),
        "presentation_llm": lambda params: create_tool_instance(TOOL_IMPORTS["presentation_llm"](), name="presentation_llm", **params),
        "sequence": lambda params: create_tool_instance(TOOL_IMPORTS["sequence"](), name="sequence", **params),
        "sql_query": lambda params: create_tool_instance(TOOL_IMPORTS["sql_query"](), name="sql_query", **params),
        "sql_query_advanced": lambda params: create_tool_instance(TOOL_IMPORTS["sql_query_advanced"](), name="sql_query_advanced", **params),
        "clone_repo_tool": lambda params: create_tool_instance(TOOL_IMPORTS["clone_repo_tool"](), name="clone_repo_tool", **params),
        "bitbucket_clone_repo_tool": lambda params: create_tool_instance(TOOL_IMPORTS["bitbucket_clone_repo_tool"](), name="bitbucket_clone_repo_tool", **params),
        "bitbucket_operations_tool": lambda params: create_tool_instance(TOOL_IMPORTS["bitbucket_operations_tool"](), name="bitbucket_operations_tool", **params),
        "git_operations_tool": lambda params: create_tool_instance(TOOL_IMPORTS["git_operations_tool"](), name="git_operations_tool", **params),
        "markdown_to_pdf": lambda params: create_tool_instance(TOOL_IMPORTS["markdown_to_pdf"](), name="markdown_to_pdf", **params),
        "markdown_to_pptx": lambda params: create_tool_instance(TOOL_IMPORTS["markdown_to_pptx"](), name="markdown_to_pptx", **params),
        "markdown_to_html": lambda params: create_tool_instance(TOOL_IMPORTS["markdown_to_html"](), name="markdown_to_html", **params),
        "markdown_to_epub": lambda params: create_tool_instance(TOOL_IMPORTS["markdown_to_epub"](), name="markdown_to_epub", **params),
        "markdown_to_ipynb": lambda params: create_tool_instance(TOOL_IMPORTS["markdown_to_ipynb"](), name="markdown_to_ipynb", **params),
        "markdown_to_latex": lambda params: create_tool_instance(TOOL_IMPORTS["markdown_to_latex"](), name="markdown_to_latex", **params),
        "markdown_to_docx": lambda params: create_tool_instance(TOOL_IMPORTS["markdown_to_docx"](), name="markdown_to_docx", **params),
        "csv_processor": lambda params: create_tool_instance(TOOL_IMPORTS["csv_processor"](), name="csv_processor", **params),
        "mermaid_validator_tool": lambda params: create_tool_instance(TOOL_IMPORTS["mermaid_validator_tool"](), name="mermaid_validator_tool", **params),
        "download_file_tool": lambda params: create_tool_instance(TOOL_IMPORTS["download_file_tool"](), name="download_file_tool", **params),
        "email_tool": lambda params: create_tool_instance(TOOL_IMPORTS["email_tool"](), name="email_tool", **params),
        "callendar_tool": lambda params: create_tool_instance(TOOL_IMPORTS["callendar_tool"](), name="callendar_tool", **params),
        "weather_tool": lambda params: create_tool_instance(TOOL_IMPORTS["weather_tool"](), name="weather_tool", **params),
        "nasa_neows_tool": lambda params: create_tool_instance(TOOL_IMPORTS["nasa_neows_tool"](), name="nasa_neows_tool", **params),
        "nasa_apod_tool": lambda params: create_tool_instance(TOOL_IMPORTS["nasa_apod_tool"](), name="nasa_apod_tool", **params),
        "product_hunt_tool": lambda params: create_tool_instance(TOOL_IMPORTS["product_hunt_tool"](), name="product_hunt_tool", **params),
        "rag_tool": lambda params: create_tool_instance(TOOL_IMPORTS["rag_tool"](), name="rag_tool", **params),
        
        # Special handling for Composio tools
        "email_tool": lambda params: create_tool_instance(TOOL_IMPORTS["email_tool"](), action="EMAIL", name="email_tool", **params),
        "callendar_tool": lambda params: create_tool_instance(TOOL_IMPORTS["callendar_tool"](), action="CALLENDAR", name="callendar_tool", **params),
        "weather_tool": lambda params: create_tool_instance(TOOL_IMPORTS["weather_tool"](), action="WEATHER", name="weather_tool", **params),
    }

    # Log available tool types before processing
    logger.debug("Available tool types:")
    for tool_type in tool_configs.keys():
        logger.debug(f"- {tool_type}")

    # Define write tools that trigger automatic download tool addition
    write_tools = {"write_file", "edit_whole_content", "replace_in_file"}
    agent_tools = []
    has_write_tool = False

    # Process requested tools
    if tools:
        logger.debug(f"Total tools to process: {len(tools)}")
        for tool_config in tools:
            tool_type = tool_config.get("type")
            logger.debug(f"Processing tool type: {tool_type}")
            
            if tool_type in tool_configs:
                try:
                    # Get the tool creation function
                    tool_create_func = tool_configs.get(tool_type)
                    if not tool_create_func:
                        logger.warning(f"No creation function found for tool type: {tool_type}")
                        continue
                    
                    # Create tool instance with parameters
                    tool_params = tool_config.get("parameters", {})
                    
                    # Create tool instance with parameters
                    tool_instance = tool_create_func(tool_params)
                    
                    if tool_instance:  # Check if tool creation was successful
                        agent_tools.append(tool_instance)
                        logger.info(f"Successfully added tool: {tool_type}")
                        if tool_type in write_tools:
                            has_write_tool = True
                    else:
                        logger.warning(f"Tool {tool_type} was not created (returned None)")
                except ImportError as e:
                    logger.warning(f"Failed to load tool {tool_type}: Required library missing - {str(e)}")
                except ValueError as e:
                    if "API_KEY" in str(e):
                        logger.warning(f"Failed to create tool {tool_type}: Missing API key - {str(e)}")
                    else:
                        logger.error(f"Failed to create tool {tool_type}: {str(e)}", exc_info=True)
                except Exception as e:
                    logger.error(f"Failed to create tool {tool_type}: {str(e)}", exc_info=True)
            else:
                logger.warning(f"Unknown tool type: {tool_type} - Skipping")

    # Add download tool if any write tool is present
    if has_write_tool:
        try:
            # Get the tool class first
            download_tool_class = TOOL_IMPORTS["download_file_tool"]()
            if download_tool_class:
                # Create an instance with the name 'download'
                download_tool = create_tool_instance(download_tool_class, name="download")
                if download_tool:
                    agent_tools.append(download_tool)
                    logger.info("Added download tool automatically due to write tool presence")
                else:
                    logger.warning("Failed to instantiate download tool")
            else:
                logger.warning("Download tool class not found")
        except ImportError as e:
            logger.warning(f"Failed to load download tool: Required library missing - {str(e)}")
        except Exception as e:
            logger.error(f"Failed to add download tool: {str(e)}")


    # Create and return the agent
    try:
        return Agent(
            model_name=model_name,
            tools=agent_tools,
            event_emitter=event_emitter,
            compact_every_n_iterations=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
            specific_expertise=specific_expertise,
            memory=memory if memory else AgentMemory(),
        )
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise

if __name__ == "__main__":
    # Example usage
    tools_config = [
        {"type": "duck_duck_go_search", "parameters": {}},
    ]
    
    agent = create_custom_agent(
        model_name="openrouter/openai/gpt-4o-mini",
        specific_expertise="General purpose assistant",
        tools=tools_config
    )
    print(f"Created agent with {len(agent.tools.tool_names())} tools")
    
    # Display all tool names
    print("Agent Tools:")
    for tool_name in agent.tools.tool_names():
        print(f"- {tool_name}")

    # Set up event monitoring to track agent's lifecycle
    # The event system provides:
    # 1. Real-time observability into the agent's operations
    # 2. Debugging and performance monitoring
    # 3. Support for future analytics and optimization efforts
    agent.event_emitter.on(
        event=[
            "task_complete",
            "task_think_start",
            "task_think_end",
            "tool_execution_start",
            "tool_execution_end",
            "error_max_iterations_reached",
            "memory_full",
            "memory_compacted",
            "memory_summary",
        ],
        listener=console_print_events,
    )

    # Enable token streaming for detailed output
    agent.event_emitter.on(event=["stream_chunk"], listener=console_print_token)

    # Solve task with streaming enabled
    result = agent.solve_task("Who is the Prime Minister of France in 2025 ?", max_iterations=10, streaming=True)
    print(result)