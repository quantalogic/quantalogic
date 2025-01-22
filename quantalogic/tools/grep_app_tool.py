# quantalogic/tools/grep_app_tool.py

import random
import sys
import time
from typing import Any, ClassVar, Dict, Optional, Union

import requests
from loguru import logger
from pydantic import BaseModel, Field, ValidationError, model_validator

from quantalogic.tools.tool import Tool, ToolArgument

# Configurable User Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/14.1.1 Safari/605.1.15"
]

class SearchError(Exception):
    """Custom exception for search-related errors"""
    pass

class GrepAppArguments(BaseModel):
    """Pydantic model for grep.app search arguments"""
    search_query: str = Field(
        ...,
        description="GitHub Code search using simple keyword or regular expression",
        example="code2prompt"
    )
    repository: Optional[str] = Field(
        None,
        description="Filter by repository (e.g. user/repo)",
        example="quantalogic/quantalogic",
    )
    page: int = Field(
        1,
        description="Results page number",
        ge=1
    )
    per_page: int = Field(
        10,
        description="Number of results per page",
        ge=1,
        le=100
    )
    regexp: bool = Field(
        False,
        description="Enable regular expression search"
    )
    case: bool = Field(
        False,
        description="Enable case-sensitive search"
    )
    words: bool = Field(
        False,
        description="Match whole words only"
    )

    @model_validator(mode='before')
    @classmethod
    def convert_types(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert input types before validation"""
        # Convert string numbers to integers
        for field in ['page', 'per_page']:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = int(data[field])
                except ValueError:
                    raise ValueError(f"{field} must be a valid integer")

        # Convert various string representations to booleans
        for field in ['regexp', 'case', 'words']:
            if field in data:
                if isinstance(data[field], str):
                    data[field] = data[field].lower() in ['true', '1', 'yes', 'on']

        return data

    @model_validator(mode='after')
    def validate_search_query(self) -> 'GrepAppArguments':
        """Validate search query is not empty and has reasonable length"""
        if not self.search_query or not self.search_query.strip():
            raise ValueError("Search query cannot be empty")
        if len(self.search_query) > 500:  # Reasonable limit for search query
            raise ValueError("Search query is too long (max 500 characters)")
        return self

class GrepAppTool(Tool):
    """Tool for searching GitHub code via grep.app API"""
    
    BASE_URL: ClassVar[str] = "https://grep.app/api/search"
    TIMEOUT: ClassVar[int] = 10

    def __init__(self):
        super().__init__(
            name="grep_app_tool", 
            description="Searches GitHub code using grep.app API. Returns code matches with metadata."
        )
        self.arguments = [
            ToolArgument(
                name="search_query",
                arg_type="string",
                description="Search query using grep.app syntax",
                required=True
            ),
            ToolArgument(
                name="repository",
                arg_type="string",
                description="Filter by repository",
                required=False
            ),
            ToolArgument(
                name="page",
                arg_type="int",
                description="Pagination page number",
                default="1",
                required=False
            ),
            ToolArgument(
                name="per_page",
                arg_type="int",
                description="Results per page",
                default="10",
                required=False
            ),
            ToolArgument(
                name="regexp",
                arg_type="boolean",
                description="Enable regular expression search",
                default="False",
                required=False
            ),
            ToolArgument(
                name="case",
                arg_type="boolean",
                description="Enable case-sensitive search",
                default="False",
                required=False
            ),
            ToolArgument(
                name="words",
                arg_type="boolean",
                description="Match whole words only",
                default="False",
                required=False
            )
        ]

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with random User-Agent"""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1"
        }
        logger.debug(f"Built headers: {headers}")
        return headers

    def _build_params(self, args: GrepAppArguments) -> Dict[str, Any]:
        """Build request parameters from arguments"""
        params = {
            "q": args.search_query,
            "page": args.page,
            "per_page": args.per_page
        }
        if args.repository:
            params["filter[repo][0]"] = args.repository
        if args.regexp:
            params["regexp"] = "true"
        if args.case:
            params["case"] = "true"
        if args.words:
            params["words"] = "true"
        logger.debug(f"Built params: {params}")
        return params

    def _make_request(self, params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Make the API request"""
        logger.info("Making API request to grep.app")
        response = requests.get(
            self.BASE_URL,
            params=params,
            headers=headers,
            timeout=self.TIMEOUT
        )
        logger.debug(f"API Response Status Code: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise SearchError("Invalid response format from API")
        logger.debug(f"API Response Data: {data}")
        return data

    def execute(self, 
                search_query: str, 
                repository: Optional[str] = None,
                page: Union[int, str] = 1,
                per_page: Union[int, str] = 10,
                regexp: bool = False,
                case: bool = False,
                words: bool = False,
                skip_delay: bool = False) -> str:
        """Execute grep.app API search with pagination and return formatted results as a string"""
        try:
            # Validate and convert arguments
            args = GrepAppArguments(
                search_query=search_query,
                repository=repository,
                page=int(page),
                per_page=int(per_page),
                regexp=regexp,
                case=case,
                words=words
            )

            logger.info(f"Executing search: '{args.search_query}'")
            logger.debug(f"Search parameters: {args.model_dump()}")

            # Add random delay to mimic human behavior (unless skipped for testing)
            if not skip_delay:
                delay = random.uniform(0.5, 1.5)
                logger.debug(f"Sleeping for {delay:.2f} seconds to mimic human behavior")
                time.sleep(delay)

            # Make API request
            headers = self._build_headers()
            params = self._build_params(args)
            results = self._make_request(params, headers)

            # Format and return results
            return self._format_results(results)

        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return self._format_error("Validation Error", str(e))
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return self._format_error(
                "API Error",
                str(e),
                {"Request URL": getattr(e.response, 'url', 'N/A') if hasattr(e, 'response') else 'N/A'}
            )
        except SearchError as e:
            logger.error(f"Search error: {e}")
            return self._format_error("Search Error", str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return self._format_error("Unexpected Error", str(e))

    def _format_results(self, data: Dict[str, Any]) -> str:
        """Format API results into a structured Markdown string"""
        query = data.get('query', '')
        total_results = data.get('hits', {}).get('total', 0)
        hits = data.get("hits", {}).get("hits", [])

        output = [
            "# 🔍 Search Results",
            "",
            f"**Query:** `{query if query else '<empty>'}`  •  **Found:** {total_results} matches",
            ""
        ]

        if not hits:
            output.append("> No matches found for your search query.")
        else:
            for idx, result in enumerate(hits, 1):
                repo = result.get('repo', {}).get('raw', 'N/A')
                file_path = result.get('path', {}).get('raw', 'N/A')
                language = result.get('language', 'N/A').lower()
                content = result.get("content", {})
                
                # Extract the actual code and line info
                snippet = content.get("snippet", "")
                line_num = content.get("line", "")
                
                # Clean up the snippet
                import re
                clean_snippet = re.sub(r'<[^>]+>', '', snippet)
                clean_snippet = re.sub(r'&quot;', '"', clean_snippet)
                clean_snippet = re.sub(r'&lt;', '<', clean_snippet)
                clean_snippet = re.sub(r'&gt;', '>', clean_snippet)
                clean_snippet = clean_snippet.strip()
                
                # Split into lines and clean each line
                raw_lines = clean_snippet.split('\n')
                lines = []
                current_line_num = int(line_num) if line_num else 1
                
                # First pass: collect all lines and their content
                for line in raw_lines:
                    # Remove excess whitespace but preserve indentation
                    stripped = line.rstrip()
                    if not stripped:
                        lines.append(('', current_line_num))
                        current_line_num += 1
                        continue
                    
                    # Remove duplicate indentation
                    if stripped.startswith('    '):
                        stripped = stripped[4:]
                    
                    # Handle URLs that might be split across lines
                    if stripped.startswith(('prompt', '-working')):
                        if lines and lines[-1][0].endswith('/'):
                            # Combine with previous line
                            prev_content, prev_num = lines.pop()
                            lines.append((prev_content + stripped, prev_num))
                            continue
                    
                    # Handle concatenated lines by looking for line numbers
                    line_parts = re.split(r'(\d+)(?=\s*[^\d])', stripped)
                    if len(line_parts) > 1:
                        # Process each part that might be a new line
                        for i in range(0, len(line_parts)-1, 2):
                            prefix = line_parts[i].rstrip()
                            if prefix:
                                if not any(l[0] == prefix for l in lines):  # Avoid duplicates
                                    lines.append((prefix, current_line_num))
                            
                            # Update line number if found
                            try:
                                current_line_num = int(line_parts[i+1])
                            except ValueError:
                                current_line_num += 1
                            
                            # Add the content after the line number
                            if i+2 < len(line_parts):
                                content = line_parts[i+2].lstrip()
                                if content and not any(l[0] == content for l in lines):  # Avoid duplicates
                                    lines.append((content, current_line_num))
                    else:
                        if not any(l[0] == stripped for l in lines):  # Avoid duplicates
                            lines.append((stripped, current_line_num))
                        current_line_num += 1

                # Format line numbers and code
                formatted_lines = []
                max_line_width = len(str(max(line[1] for line in lines))) if lines else 3
                
                # Second pass: format each line
                for line_content, line_no in lines:
                    if not line_content:  # Empty line
                        formatted_lines.append('')
                        continue
                    
                    # Special handling for markdown badges and links
                    if '[![' in line_content or '[!' in line_content:
                        badges = re.findall(r'(\[!\[.*?\]\(.*?\)\]\(.*?\))', line_content)
                        if badges:
                            for badge in badges:
                                if not any(badge in l for l in formatted_lines):  # Avoid duplicates
                                    formatted_lines.append(f"{str(line_no).rjust(max_line_width)} │ {badge}")
                            continue
                    
                    # Add syntax highlighting for comments
                    if line_content.lstrip().startswith(('// ', '# ', '/* ', '* ', '*/')):
                        line_str = f"{str(line_no).rjust(max_line_width)} │ <dim>{line_content}</dim>"
                        if not any(line_str in l for l in formatted_lines):  # Avoid duplicates
                            formatted_lines.append(line_str)
                    else:
                        # Split line into indentation and content for better formatting
                        indent = len(line_content) - len(line_content.lstrip())
                        indentation = line_content[:indent]
                        content = line_content[indent:]
                        
                        # Highlight strings and special syntax
                        content = re.sub(r'(["\'])(.*?)\1', r'<str>\1\2\1</str>', content)
                        content = re.sub(r'\b(function|const|let|var|import|export|class|interface|type|enum)\b', 
                                       r'<keyword>\1</keyword>', content)
                        
                        line_str = f"{str(line_no).rjust(max_line_width)} │ {indentation}{content}"
                        if not any(line_str in l for l in formatted_lines):  # Avoid duplicates
                            formatted_lines.append(line_str)

                # Truncate if too long and add line count
                if len(formatted_lines) > 5:
                    remaining = len(formatted_lines) - 5
                    formatted_lines = formatted_lines[:5]
                    if remaining > 0:
                        formatted_lines.append(f"   ┆ {remaining} more line{'s' if remaining > 1 else ''}")
                
                clean_snippet = '\n'.join(formatted_lines)
                
                # Format the repository link to be clickable
                if '/' in repo:
                    repo_link = f"[`{repo}`](https://github.com/{repo})"
                else:
                    repo_link = f"`{repo}`"

                # Determine the best language display and icon
                lang_display = language if language != 'n/a' else ''
                lang_icon = {
                    'python': '🐍',
                    'typescript': '📘',
                    'javascript': '📒',
                    'markdown': '📝',
                    'toml': '⚙️',
                    'yaml': '📋',
                    'json': '📦',
                    'shell': '🐚',
                    'rust': '🦀',
                    'go': '🔵',
                    'java': '☕',
                    'ruby': '💎',
                }.get(lang_display, '📄')
                
                # Format file path with language icon and line info
                file_info = [f"{lang_icon} `{file_path}`"]
                if line_num:
                    file_info.append(f"Line {line_num}")
                
                output.extend([
                    f"### {repo_link}",
                    " • ".join(file_info),
                    "```",
                    clean_snippet,
                    "```",
                    ""
                ])

        return "\n".join(filter(None, output))

    def _format_error(self, error_type: str, message: str, additional_info: Dict[str, str] = None) -> str:
        """Format error messages consistently using Markdown"""
        output = [
            f"## {error_type}",
            f"**Message:** {message}"
        ]
        
        if additional_info:
            output.append("**Additional Information:**")
            for key, value in additional_info.items():
                output.append(f"- **{key}:** {value}")
        
        output.append(f"## End {error_type}")
        return "\n\n".join(output)

if __name__ == "__main__":
    # Configure logger
    logger.remove()  # Remove default handlers
    logger.add(sys.stderr, level="INFO", format="<green>{time}</green> <level>{message}</level>")

    logger.info("Starting GrepAppTool test cases")
    tool = GrepAppTool()

    test_cases = [
        {
            "name": "Python __init__ Methods Search",
            "args": {
                "search_query": "lang:python def __init__",
                "per_page": 5,
                "skip_delay": True  # Skip delay for testing
            }
        },
        {
            "name": "Logging Patterns Search",
            "args": {
                "search_query": "logger",
                "per_page": 3,
                "skip_delay": True
            }
        },
        {
            "name": "Repository-Specific Search",
            "args": {
                "search_query": "def",
                "repository": "quantalogic/quantalogic",
                "per_page": 5,
                "words": True,
                "skip_delay": True
            }
        },
        {
            "name": "Raphaël MANSUY",
            "args": {
                "search_query": "raphaelmansuy",
                "per_page": 3,
                "skip_delay": True
            }
        }
    ]

    for test in test_cases:
        try:
            logger.info(f"Running test: {test['name']}")
            logger.info(f"Executing with arguments: {test['args']}")
            result = tool.execute(**test['args'])
            print(f"\n### Test: {test['name']}\n{result}\n")
            time.sleep(1)  # Add a small delay between tests to avoid rate limiting
        except Exception as e:
            logger.error(f"{test['name']} Failed: {e}", exc_info=True)