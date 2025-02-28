"""Tool for interacting with DuckDuckGo for search results."""

from duckduckgo_search import DDGS

from quantalogic.tools.tool import Tool, ToolArgument


class DuckDuckGoSearchTool(Tool):
    """Tool for retrieving search results from DuckDuckGo.

    This tool provides a convenient interface to DuckDuckGo's search capabilities,
    supporting multiple search types and structured JSON output.

    Example usage:
    ```python
    tool = DuckDuckGoSearchTool()
    results = tool.execute(
        query="machine learning",
        search_type="text",
        max_results=10,
        region="us-en",
        safesearch="moderate"
    )
    print(results)
    ```

    The tool handles:
    - Query validation
    - API error handling
    - Multiple search types (text, images, videos, news)
    - Scope filtering (region, safesearch, timelimit)
    - JSON result formatting
    """

    name: str = "duckduckgo_tool"
    description: str = "Retrieves search results from DuckDuckGo. " "Provides structured output of search results."
    arguments: list = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="The search query to execute",
            required=True,
            example="machine learning",
        ),
        ToolArgument(
            name="max_results",
            arg_type="int",
            description="Maximum number of results to retrieve (1-50)",
            required=True,
            default="10",
            example="20",
        ),
        ToolArgument(
            name="search_type",
            arg_type="string",
            description="Type of search to perform (text, images, videos, news)",
            required=False,
            default="text",
            example="images",
        ),
        ToolArgument(
            name="region",
            arg_type="string",
            description="Region for search results (e.g., 'wt-wt', 'us-en')",
            required=False,
            default="wt-wt",
            example="us-en",
        ),
        ToolArgument(
            name="safesearch",
            arg_type="string",
            description="Safesearch level ('on', 'moderate', 'off')",
            required=False,
            default="moderate",
            example="moderate",
        ),
        ToolArgument(
            name="timelimit",
            arg_type="string",
            description="Time limit for results (e.g., 'd' for day, 'w' for week)",
            required=False,
            default=None,
            example="d",
        ),
    ]

    def execute(
        self,
        query: str,
        max_results: int = 10,
        search_type: str = "text",
        region: str = "wt-wt",
        safesearch: str = "moderate",
        timelimit: str = None,
    ) -> str:
        """Execute a search query using DuckDuckGo and return results.

        Args:
            query: The search query to execute
            max_results: Maximum number of results to retrieve (1-50)
            search_type: Type of search to perform (text, images, videos, news)
            region: Region for search results (e.g., "wt-wt", "us-en")
            safesearch: Safesearch level ("on", "moderate", "off")
            timelimit: Time limit for results (e.g., "d" for day, "w" for week)

        Returns:
            Pretty-printed JSON string of search results.

        Raises:
            ValueError: If any parameter is invalid
            RuntimeError: If search fails
        """
        # Handle empty string parameters by setting to defaults
        query = str(query) if query else query
        search_type = search_type if search_type else "text"
        region = region if region else "wt-wt"
        safesearch = safesearch if safesearch else "moderate"
        timelimit = timelimit if timelimit else None

        # Validate and convert query
        if not query:
            raise ValueError("Query must be a non-empty string")
        try:
            query = str(query)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Query must be convertible to string: {str(e)}")

        # Validate and convert max_results
        try:
            max_results = int(max_results)
            if max_results < 1 or max_results > 50:
                raise ValueError("Number of results must be between 1 and 50")
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid number of results: {str(e)}")

        # Validate search_type
        if search_type not in ["text", "images", "videos", "news"]:
            raise ValueError("search_type must be one of: text, images, videos, news")

        # Validate safesearch
        if safesearch not in ["on", "moderate", "off"]:
            raise ValueError("safesearch must be one of: on, moderate, off")

        try:
            ddgs = DDGS()

            # Perform the appropriate search based on search_type
            if search_type == "text":
                results = ddgs.text(
                    keywords=query,
                    region=region,
                    safesearch=safesearch,
                    timelimit=timelimit,
                    max_results=max_results,
                )
            elif search_type == "images":
                results = ddgs.images(
                    keywords=query,
                    region=region,
                    safesearch=safesearch,
                    timelimit=timelimit,
                    max_results=max_results,
                )
            elif search_type == "videos":
                results = ddgs.videos(
                    keywords=query,
                    region=region,
                    safesearch=safesearch,
                    timelimit=timelimit,
                    max_results=max_results,
                )
            elif search_type == "news":
                results = ddgs.news(
                    keywords=query,
                    region=region,
                    safesearch=safesearch,
                    timelimit=timelimit,
                    max_results=max_results,
                )

            # Return pretty-printed JSON
            import json

            return json.dumps(results, indent=4, ensure_ascii=False)

        except Exception as e:
            raise RuntimeError(f"Search failed: {str(e)}")


def main():
    """Demonstrate DuckDuckGoSearchTool functionality."""
    try:
        tool = DuckDuckGoSearchTool()

        # Test basic search functionality
        print("Testing DuckDuckGoSearchTool with sample query...")
        results = tool.execute(query="Python programming", max_results=3)
        print(results)

        # Test error handling
        print("\nTesting error handling with invalid query...")
        try:
            tool.execute(query="")
        except ValueError as e:
            print(f"Caught expected ValueError: {e}")

    except Exception as e:
        print(f"Error in main: {e}")


if __name__ == "__main__":
    main()
