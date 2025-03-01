"""NASA APOD (Astronomy Picture of the Day) API tool.

This tool provides access to NASA's APOD API to retrieve astronomy pictures and related information.
It supports fetching both current and historical astronomy pictures with detailed metadata.
"""

import os
from datetime import datetime
from typing import Any, Dict, List

import requests
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class NasaApodTool(Tool):
    """Tool for accessing NASA's Astronomy Picture of the Day (APOD) API.

    Features:
    - Fetch today's astronomy picture
    - Retrieve pictures from specific dates
    - Get random astronomy pictures
    - Support for HD images
    - Detailed metadata including explanation and copyright info
    """

    name: str = "nasa_apod_tool"
    description: str = (
        "NASA Astronomy Picture of the Day (APOD) API tool for retrieving astronomy pictures "
        "and their detailed information including scientific explanations."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="date",
            arg_type="string",
            description="The date of the APOD image to retrieve (YYYY-MM-DD format)",
            required=False,
            default="today",
            example="2024-01-15",
        ),
        ToolArgument(
            name="start_date",
            arg_type="string",
            description="Start date for date range search (YYYY-MM-DD format)",
            required=False,
            example="2024-01-01",
        ),
        ToolArgument(
            name="end_date",
            arg_type="string",
            description="End date for date range search (YYYY-MM-DD format)",
            required=False,
            example="2024-01-07",
        ),
        ToolArgument(
            name="count",
            arg_type="int",
            description="Number of random images to return (1-100)",
            required=False,
            default="1",
            example="5",
        ),
        ToolArgument(
            name="thumbs",
            arg_type="boolean",
            description="Return thumbnail URLs for video content",
            required=False,
            default="True",
            example="True",
        ),
    ]

    def __init__(self):
        """Initialize the NASA APOD tool."""
        super().__init__()
        self.api_key = os.getenv("LANAZA_API_KEY", "DEMO_KEY")
        self.base_url = "https://api.nasa.gov/planetary/apod"

    def _fetch_apod_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch data from NASA APOD API.

        Args:
            params: Query parameters for the API request

        Returns:
            API response data as dictionary

        Raises:
            RuntimeError: If the API request fails
        """
        try:
            params["api_key"] = self.api_key
            response = requests.get(self.base_url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                raise RuntimeError(f"API request failed with status {response.status_code}: {response.text}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch APOD data: {str(e)}")

    def _validate_date(self, date_str: str) -> str:
        """Validate and format date string.

        Args:
            date_str: Date string to validate

        Returns:
            Validated date string in YYYY-MM-DD format

        Raises:
            ValueError: If date format is invalid
        """
        if date_str.lower() == "today":
            return datetime.now().strftime("%Y-%m-%d")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD format.")

    def _format_apod_result(self, data: Dict[str, Any] | List[Dict[str, Any]]) -> str:
        """Format APOD data into readable text.

        Args:
            data: APOD data from API

        Returns:
            Formatted string with APOD information
        """
        if isinstance(data, list):
            return self._format_multiple_results(data)
        
        result = []
        result.append(f"Title: {data.get('title', 'N/A')}")
        result.append(f"Date: {data.get('date', 'N/A')}")
        if 'copyright' in data:
            result.append(f"Copyright: {data['copyright']}")
        
        # Add media links
        if data.get('media_type') == 'video':
            result.append(f"Video URL: {data.get('url', 'N/A')}")
            if data.get('thumbnail_url'):
                result.append(f"Thumbnail URL: {data.get('thumbnail_url')}")
        else:
            result.append(f"Image URL: {data.get('url', 'N/A')}")
            if data.get('hdurl'):
                result.append(f"HD Image URL: {data.get('hdurl')}")
        
        # Add explanation
        if data.get('explanation'):
            result.append("\nExplanation:")
            result.append(data['explanation'])
        
        return "\n".join(result)

    def _format_multiple_results(self, data_list: List[Dict[str, Any]]) -> str:
        """Format multiple APOD results.

        Args:
            data_list: List of APOD data entries

        Returns:
            Formatted string with multiple APOD entries
        """
        results = []
        for i, data in enumerate(data_list, 1):
            results.append(f"\n--- APOD Entry {i} ---")
            results.append(self._format_apod_result(data))
        return "\n".join(results)

    def execute(
        self,
        date: str = "today",
        start_date: str = None,
        end_date: str = None,
        count: int = 1,
        thumbs: bool = True,
    ) -> str:
        """Execute APOD API request with specified parameters.

        Args:
            date: Specific date for APOD image (YYYY-MM-DD)
            start_date: Start date for date range
            end_date: End date for date range
            count: Number of random images to return
            thumbs: Include thumbnails for video content

        Returns:
            Formatted string containing APOD data

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If the API request fails
        """
        # Validate parameters
        params = {"thumbs": str(thumbs).lower()}

        # Handle different query types
        if start_date and end_date:
            params["start_date"] = self._validate_date(start_date)
            params["end_date"] = self._validate_date(end_date)
        elif count > 1:
            params["count"] = min(100, max(1, count))  # Ensure count is between 1 and 100
        else:
            params["date"] = self._validate_date(date)

        try:
            data = self._fetch_apod_data(params)
            return self._format_apod_result(data)
        except Exception as e:
            logger.error(f"Error executing APOD tool: {str(e)}")
            raise

if __name__ == "__main__":
    # Example usage
    tool = NasaApodTool()
    
    # Test with today's APOD
    result = tool.execute()
    print("Today's APOD:")
    print(result)
    
    # Test with specific date
    result = tool.execute(date="2024-01-01")
    print("\nAPOD for 2024-01-01:")
    print(result)
    
    # Test with multiple random images
    result = tool.execute(count=2)
    print("\nTwo random APODs:")
    print(result)
