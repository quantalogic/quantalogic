"""Tools for the QuantaLogic agent."""


# Direct imports of tools
from .agent_tool import AgentTool
from .download_http_file_tool import DownloadHttpFileTool
from .duckduckgo_search_tool import DuckDuckGoSearchTool
from .edit_whole_content_tool import EditWholeContentTool
from .elixir_tool import ElixirTool
from .execute_bash_command_tool import ExecuteBashCommandTool
from .file_tracker_tool import FileTrackerTool
from .grep_app_tool import GrepAppTool
from .input_question_tool import InputQuestionTool
from .jinja_tool import JinjaTool
from .list_directory_tool import ListDirectoryTool
from .llm_tool import LLMTool
from .llm_vision_tool import LLMVisionTool
from .markitdown_tool import MarkitdownTool
from .nodejs_tool import NodeJsTool
from .python_tool import PythonTool
from .read_file_block_tool import ReadFileBlockTool
from .read_file_tool import ReadFileTool
from .read_html_tool import ReadHTMLTool
from .replace_in_file_tool import ReplaceInFileTool
from .ripgrep_tool import RipgrepTool
from .search_definition_names_tool import SearchDefinitionNamesTool
from .sequence_tool import SequenceTool
from .serpapi_search_tool import SerpApiSearchTool
from .sql_query_tool import SQLQueryTool
from .task_complete_tool import TaskCompleteTool
from .tool import Tool, ToolArgument, create_tool
from .unified_diff_tool import UnifiedDiffTool
from .utils.generate_database_report import generate_database_report
from .wikipedia_search_tool import WikipediaSearchTool
from .write_file_tool import WriteFileTool

# Define __all__ to control what gets imported with `from quantalogic.tools import *`
__all__ = [
    'AgentTool',
    'DownloadHttpFileTool',
    'DuckDuckGoSearchTool',
    'EditWholeContentTool',
    'ElixirTool',
    'ExecuteBashCommandTool',
    'generate_database_report',
    'GrepAppTool',
    'InputQuestionTool',
    'JinjaTool',
    'ListDirectoryTool',
    'LLMTool',
    'LLMVisionTool',
    'MarkitdownTool',
    'NodeJsTool',
    'PythonTool',
    'ReadFileBlockTool',
    'ReadFileTool',
    'ReadHTMLTool',
    'ReplaceInFileTool',
    'RipgrepTool',
    'SafePythonInterpreterTool',
    'SearchDefinitionNamesTool',
    'SequenceTool',
    'SerpApiSearchTool',
    'SQLQueryTool',
    'TaskCompleteTool',
    'Tool',
    'ToolArgument',
    'UnifiedDiffTool',
    'WikipediaSearchTool',
    'WriteFileTool',
    'FileTrackerTool',
    "create_tool"
]
