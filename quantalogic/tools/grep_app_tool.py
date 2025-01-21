import os
import random
import time
import sys
from typing import List, Optional, Union, Dict, Any, ClassVar

import requests
from loguru import logger
from pydantic import BaseModel, Field, field_validator, ValidationError

from quantalogic.tools.tool import Tool, ToolArgument

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
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

    @field_validator('search_query')
    def validate_search_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Search query cannot be empty")
        return v.strip()

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
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1"
        }

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
        return params

    def execute(self, search_query: str, repository: Optional[str] = None,
                file_type: Optional[str] = None, page: Union[int, str] = 1,
                per_page: Union[int, str] = 10) -> str:
        """Execute grep.app API search with pagination"""
        try:
            # Validate and convert arguments
            args = GrepAppArguments(
                search_query=search_query,
                repository=repository,
                file_type=file_type,
                page=int(page),
                per_page=int(per_page)
            )

            # Add random delay to mimic human behavior
            time.sleep(random.uniform(0.5, 1.5))

            # Make API request
            response = requests.get(
                self.BASE_URL,
                params=self._build_params(args),
                headers=self._build_headers(),
                timeout=self.TIMEOUT
            )
            response.raise_for_status()

            results = response.json()
            return self._format_results(results)

        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return self._format_error("Validation Error", str(e))
        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return self._format_error(
                "API Error",
                str(e),
                {"Request URL": getattr(e.response, 'url', 'N/A') if hasattr(e, 'response') else 'N/A'}
            )
        except Exception as e:
            logger.error(f"Processing error: {str(e)}")
            return self._format_error("Processing Error", str(e))

    def _format_results(self, data: Dict[str, Any]) -> str:
        """Format API results into standardized output"""
        output = [
            "==== Grep.app Results ====",
            f"Query: {data.get('query', '')}",
            f"Total Results: {data.get('hits', {}).get('total', 0)}",
            "==== Matches ===="
        ]
        
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            output.append("No matches found.")
        else:
            for result in hits:
                output.extend([
                    f"Repo: {result.get('repo', {}).get('raw', '')}",
                    f"File: {result.get('path', {}).get('raw', '')}",
                    f"Language: {result.get('language', '')}",
                    "Code:",
                    result.get("content", {}).get("snippet", ""),
                    "----"
                ])
        
        output.append("==== End of Results ====")
        return "\n".join(output)

    def _format_error(self, error_type: str, message: str, additional_info: Dict[str, str] = None) -> str:
        """Format error messages consistently"""
        output = [
            f"==== {error_type} ====",
            f"Message: {message}"
        ]
        
        if additional_info:
            for key, value in additional_info.items():
                output.append(f"{key}: {value}")
        
        output.append(f"==== End {error_type} ====")
        return "\n".join(output)

if __name__ == "__main__":
    logger.remove()  # Remove default handlers
    logger.add(sys.stderr, level="INFO")  # Add console handler
    logger.info("Starting GrepAppTool test cases")
    tool = GrepAppTool()

    test_cases = [
        {
            "name": "Python __init__ Methods Search",
            "args": {
                "search_query": "quantalogic",
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
        }
    ]

    for test in test_cases:
        try:
            logger.info(f"Running test: {test['name']}")
            result = tool.execute(**test['args'])
            logger.info(f"Test Results:\n{result}")
        except Exception as e:
            logger.error(f"{test['name']} Failed: {e}", exc_info=True)