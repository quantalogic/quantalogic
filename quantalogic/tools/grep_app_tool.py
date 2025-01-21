# quantalogic/tools/grep_app_tool.py

import os
import random
import sys
import time
from typing import Any, ClassVar, Dict, List, Optional, Union

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
        description="Code search query using grep.app syntax",
        example="lang:python def __init__"
    )
    repository: Optional[str] = Field(
        None,
        description="Filter by repository (e.g. user/repo)",
        example="quantalogic/ai-tools",
        pattern=r"^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$"
    )
    file_type: Optional[str] = Field(
        None,
        description="Filter by file extension",
        example="py"
    )
    page: int = Field(
        1,
        description="Results page number",
        ge=1,
        example=1
    )
    per_page: int = Field(
        10,
        description="Results per page (1-100)",
        ge=1,
        le=100,
        example=10
    )

    @model_validator(mode='after')
    def check_search_query(self) -> 'GrepAppArguments':
        if not self.search_query or not self.search_query.strip():
            raise ValueError("Search query cannot be empty or whitespace")
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
                name="file_type",
                arg_type="string",
                description="Filter by file extension",
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
            params["repo"] = args.repository
        if args.file_type:
            params["filter"] = f"extension:{args.file_type}"
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
                file_type: Optional[str] = None, 
                page: Union[int, str] = 1,
                per_page: Union[int, str] = 10) -> str:
        """Execute grep.app API search with pagination and return formatted results as a string"""
        try:
            # Validate and convert arguments
            args = GrepAppArguments(
                search_query=search_query,
                repository=repository,
                file_type=file_type,
                page=int(page),
                per_page=int(per_page)
            )

            logger.info(f"Executing search: '{args.search_query}'")
            logger.debug(f"Search parameters: {args.dict()}")

            # Add random delay to mimic human behavior
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
            f"## Grep.app Search Results",
            f"**Query:** `{query}`",
            f"**Total Results:** {total_results}",
            "---"
        ]

        if not hits:
            output.append("**No matches found.**")
        else:
            # Create Markdown table header
            table_header = "| Repository | File Path | Language | Code Snippet |\n| --- | --- | --- | --- |"
            output.append(table_header)

            # Populate table rows
            for result in hits:
                repo = result.get('repo', {}).get('raw', 'N/A').replace('|', '\\|')
                file_path = result.get('path', {}).get('raw', 'N/A').replace('|', '\\|')
                language = result.get('language', 'N/A').replace('|', '\\|')
                snippet = result.get("content", {}).get("snippet", "").strip().replace('|', '\\|').replace('\n', ' ')
                # Limit snippet length to 200 characters to prevent excessively long lines
                snippet = (snippet[:197] + '...') if len(snippet) > 200 else snippet
                # Escape pipe characters to prevent table formatting issues
                output.append(f"| `{repo}` | `{file_path}` | `{language}` | `{snippet}` |")

        output.append("---")
        output.append("**End of Results**")

        return "\n".join(output)

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
                "per_page": 5
            }
        },
        {
            "name": "Logging Patterns Search",
            "args": {
                "search_query": "logger",
                "file_type": "py",
                "per_page": 3
            }
        },
                {
            "name": "Raphaël MANSUY",
            "args": {
                "search_query": "raphaelmansuy",
                "per_page": 3
            }
        }

    ]

    for test in test_cases:
        try:
            logger.info(f"Running test: {test['name']}")
            logger.info(f"Executing with arguments: {test['args']}")
            result = tool.execute(**test['args'])
            print(f"\n### Test: {test['name']}\n{result}\n")
        except Exception as e:
            logger.error(f"{test['name']} Failed: {e}", exc_info=True)