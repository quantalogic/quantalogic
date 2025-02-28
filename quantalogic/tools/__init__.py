"""Tools for the QuantaLogic agent."""

import importlib
import sys
from typing import Any, Dict


class LazyLoader:
    """
    Lazily import a module only when its attributes are accessed.
    This helps reduce startup time by deferring imports until needed.
    """
    def __init__(self, module_path: str):
        self.module_path = module_path
        self._module = None

    def __getattr__(self, name: str) -> Any:
        if self._module is None:
            self._module = importlib.import_module(self.module_path)
        return getattr(self._module, name)


# Map of tool names to their import paths
_TOOL_IMPORTS = {
    "AgentTool": ".agent_tool",
    "ComposioTool": ".composio.composio",
    "GenerateDatabaseReportTool": ".database.generate_database_report_tool",
    "SQLQueryToolAdvanced": ".database.sql_query_tool_advanced",
    "MarkdownToDocxTool": ".document_tools.markdown_to_docx_tool",
    "MarkdownToEpubTool": ".document_tools.markdown_to_epub_tool",
    "MarkdownToHtmlTool": ".document_tools.markdown_to_html_tool",
    "MarkdownToIpynbTool": ".document_tools.markdown_to_ipynb_tool",
    "MarkdownToLatexTool": ".document_tools.markdown_to_latex_tool",
    "MarkdownToPdfTool": ".document_tools.markdown_to_pdf_tool",
    "MarkdownToPptxTool": ".document_tools.markdown_to_pptx_tool",
    "DownloadHttpFileTool": ".download_http_file_tool",
    "DuckDuckGoSearchTool": ".duckduckgo_search_tool",
    "EditWholeContentTool": ".edit_whole_content_tool",
    "ElixirTool": ".elixir_tool",
    "ExecuteBashCommandTool": ".execute_bash_command_tool",
    "BitbucketCloneTool": ".git.bitbucket_clone_repo_tool",
    "BitbucketOperationsTool": ".git.bitbucket_operations_tool",
    "CloneRepoTool": ".git.clone_repo_tool",
    "GitOperationsTool": ".git.git_operations_tool",
    "GoogleNewsTool": ".google_packages.google_news_tool",
    "GrepAppTool": ".grep_app_tool",
    "LLMImageGenerationTool": ".image_generation.dalle_e",
    "InputQuestionTool": ".input_question_tool",
    "JinjaTool": ".jinja_tool",
    "ListDirectoryTool": ".list_directory_tool",
    "LLMTool": ".llm_tool",
    "LLMVisionTool": ".llm_vision_tool",
    "MarkitdownTool": ".markitdown_tool",
    "NasaApodTool": ".nasa_packages.nasa_apod_tool",
    "NasaNeoWsTool": ".nasa_packages.nasa_neows_tool",
    "NodeJsTool": ".nodejs_tool",
    "PresentationLLMTool": ".presentation_tools.presentation_llm_tool",
    "ProductHuntTool": ".product_hunt.product_hunt_tool",
    "PythonTool": ".python_tool",
    "RagTool": ".rag_tool.rag_tool",
    "ReadFileBlockTool": ".read_file_block_tool",
    "ReadFileTool": ".read_file_tool",
    "ReadHTMLTool": ".read_html_tool",
    "ReplaceInFileTool": ".replace_in_file_tool",
    "RipgrepTool": ".ripgrep_tool",
    "SafePythonInterpreterTool": ".safe_python_interpreter_tool",
    "SearchDefinitionNames": ".search_definition_names",
    "SequenceTool": ".sequence_tool",
    "SerpApiSearchTool": ".serpapi_search_tool",
    "SQLQueryTool": ".sql_query_tool",
    "TaskCompleteTool": ".task_complete_tool",
    "Tool": ".tool",
    "ToolArgument": ".tool",
    "UnifiedDiffTool": ".unified_diff_tool",
    "CSVProcessorTool": ".utilities.csv_processor_tool",
    "PrepareDownloadTool": ".utilities.download_file_tool",
    "MermaidValidatorTool": ".utilities.mermaid_validator_tool",
    "WikipediaSearchTool": ".wikipedia_search_tool",
    "WriteFileTool": ".write_file_tool",
}

# Create lazy loaders for each module path
_lazy_modules: Dict[str, LazyLoader] = {}
for tool, path in _TOOL_IMPORTS.items():
    full_path = f"{__package__}{path}"
    if full_path not in _lazy_modules:
        _lazy_modules[full_path] = LazyLoader(full_path)

# Set up attributes for lazy loading
_tools_to_lazy_modules = {}
for tool, path in _TOOL_IMPORTS.items():
    full_path = f"{__package__}{path}"
    _tools_to_lazy_modules[tool] = _lazy_modules[full_path]

# Define __all__ so that import * works properly
__all__ = list(_TOOL_IMPORTS.keys())

# Set up lazy loading for each tool
for tool, lazy_module in _tools_to_lazy_modules.items():
    # This will create properties that lazily load the requested tool
    setattr(sys.modules[__name__], tool, getattr(lazy_module, tool))
