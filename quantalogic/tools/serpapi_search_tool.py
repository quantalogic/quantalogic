"""Tool for interacting with SerpApi for search results."""

import os

from serpapi.google_search import GoogleSearch

from quantalogic.tools.tool import Tool, ToolArgument


class SerpApiSearchTool(Tool):
    """Tool for retrieving paginated search results from SerpApi.

    This tool provides a convenient interface to SerpAPI's search capabilities,
    supporting pagination and structured result formatting.

    Example usage:
    ```python
    tool = SerpApiTool()
    results = tool.execute(
        query="machine learning",
        page=1,
        num_results=10
    )
    print(results)
    ```

    The tool handles:
    - Query validation
    - Pagination management
    - API error handling
    - Result formatting
    """

    name: str = "serpapi_tool"
    description: str = (
        "Retrieves search results from SerpAPI (Google Search) with pagination support. "
        "Handles multiple pages of results and provides structured output."
    )
    arguments: list = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="The search query to execute",
            required=True,
            example="machine learning",
        ),
        ToolArgument(
            name="page",
            arg_type="int",
            description="The page number to retrieve (1-based)",
            required=True,
            default="1",
            example="2",
        ),
        ToolArgument(
            name="num_results",
            arg_type="int",
            description="Number of results to retrieve per page",
            required=True,
            default="10",
            example="20",
        ),
    ]

    def execute(self, query: str, page: int = 1, num_results: int = 10) -> str:
        """Execute a search query using SerpAPI and return results.

        Args:
            query: The search query to execute
            page: The page number to retrieve (1-based)
            num_results: Number of results to retrieve per page (1-100)

        Returns:
            Formatted search results as a string with the following format:
            ==== Page X of results ====
            1. Title
               URL
               Description
            2. Title
               URL
               Description
            ==== End of page X ====

        Raises:
            ValueError: If any parameter is invalid
            RuntimeError: If API request fails or environment variable is missing
        """
        # Validate and convert query
        if not query:
            raise ValueError("Query must be a non-empty string")
        try:
            query = str(query)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Query must be convertible to string: {str(e)}")

        # Validate and convert page
        try:
            page = int(page)
            if page < 1:
                raise ValueError("Page number must be positive")
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid page number: {str(e)}")

        # Validate and convert num_results
        try:
            num_results = int(num_results)
            if num_results < 1 or num_results > 100:
                raise ValueError("Number of results must be between 1 and 100")
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid number of results: {str(e)}")

        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise RuntimeError("SERPAPI_API_KEY environment variable is not set")

        try:
            params = {"q": query, "start": (page - 1) * num_results, "num": num_results, "api_key": api_key}

            search = GoogleSearch(params)
            results = search.get_dict()

            if "error" in results:
                raise RuntimeError(f"API error: {results['error']}")

            # Format results
            output = []
            if "organic_results" in results:
                for idx, result in enumerate(results["organic_results"], 1):
                    output.append(f"{idx}. {result.get('title', 'No title')}")
                    output.append(f"   {result.get('link', 'No URL')}")
                    output.append(f"   {result.get('snippet', 'No description')}")
                    output.append("")

            if not output:
                return "No results found"

            # Add pagination info
            output.insert(0, f"==== Page {page} of results ====")
            output.append(f"==== End of page {page} ====")

            return "\n".join(output)

        except Exception as e:
            raise RuntimeError(f"Search failed: {str(e)}")


def main():
    """Demonstrate SerpApiTool functionality."""
    try:
        tool = SerpApiSearchTool()

        # Test basic search functionality
        print("Testing SerpApiTool with sample query...")
        results = tool.execute(query="Python programming", page=1, num_results=3)
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
