from typing import Union

"""Tool for interacting with Wikipedia API for search results."""

import requests  # noqa: E402

from quantalogic.tools.tool import Tool, ToolArgument  # noqa: E402


class WikipediaSearchTool(Tool):
    """Tool for retrieving paginated search results from Wikipedia.

    This tool provides a convenient interface to Wikipedia's search API,
    supporting pagination and structured result formatting.

    Example usage:
    ```python
    tool = WikipediaSearchTool()
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

    name: str = "wikipedia_tool"
    description: str = (
        "Retrieves search results from Wikipedia with pagination support. "
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
            description="Number of results to retrieve per page (1-50)",
            required=True,
            default="10",
            example="20",
        ),
    ]

    def execute(self, query: str, page: Union[str, int] = 1, num_results: Union[str, int] = 10) -> str:
        """Execute a search query using Wikipedia API and return results.

        Args:
            query: The search query to execute
            page: The page number to retrieve (1-based)
            num_results: Number of results to retrieve per page (1-50)

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
            RuntimeError: If API request fails
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        try:
            page = int(page) if str(page).strip() else 1
            num_results = int(num_results) if str(num_results).strip() else 10
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid parameter type: {e}. Expected integers for page and num_results")

        if page < 1:
            raise ValueError("Page number must be positive")

        if num_results < 1 or num_results > 50:
            raise ValueError("Number of results must be between 1 and 50")

        try:
            # Wikipedia API endpoint
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": num_results,
                "sroffset": (page - 1) * num_results,
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            output = []
            if "query" in data and "search" in data["query"]:
                for idx, result in enumerate(data["query"]["search"], 1):
                    title = result.get("title", "No title")
                    snippet = result.get("snippet", "No description")
                    url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

                    output.append(f"{idx}. {title}")
                    output.append(f"   {url}")
                    output.append(f"   {snippet}")
                    output.append("")

            if not output:
                return "No results found"

            output.insert(0, f"==== Page {page} of results ====")
            output.append(f"==== End of page {page} ====")

            return "\n".join(output)

        except Exception as e:
            raise RuntimeError(f"Search failed: {str(e)}")


def main():
    """Demonstrate WikipediaSearchTool functionality."""
    try:
        tool = WikipediaSearchTool()

        # Test basic search functionality
        print("Testing WikipediaSearchTool with sample query...")
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
