"""NASA NeoWs (Near Earth Object Web Service) API tool.

This tool provides access to NASA's NeoWs API to retrieve information about near-Earth asteroids.
It supports searching by date ranges, looking up specific asteroids, and browsing the overall dataset.
"""

import asyncio
import os
from typing import List

from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument

from .models import Asteroid
from .services import NasaApiService, NeoWsService


class NasaNeoWsTool(Tool):
    """Tool for accessing NASA's Near Earth Object Web Service (NeoWs).

    Features:
    - Search asteroids by date range
    - Lookup specific asteroids by ID
    - Browse the overall asteroid dataset
    """

    name: str = "nasa_neows_tool"
    description: str = (
        "NASA Near Earth Object Web Service (NeoWs) API tool for retrieving information "
        "about near-Earth asteroids, including their orbits, sizes, and approach distances."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="operation",
            arg_type="string",
            description="Operation to perform (feed, lookup, browse)",
            required=True,
            default="feed",
            example="feed",
        ),
        ToolArgument(
            name="start_date",
            arg_type="string",
            description="Start date for asteroid search (YYYY-MM-DD format)",
            required=False,
            example="2024-01-01",
        ),
        ToolArgument(
            name="end_date",
            arg_type="string",
            description="End date for asteroid search (YYYY-MM-DD format)",
            required=False,
            example="2024-01-07",
        ),
        ToolArgument(
            name="asteroid_id",
            arg_type="string",
            description="NASA JPL small body ID for asteroid lookup",
            required=False,
            example="3542519",
        ),
    ]

    def __init__(self):
        """Initialize the NASA NeoWs tool."""
        super().__init__()
        api_service = NasaApiService(os.getenv("LANAZA_API_KEY", "DEMO_KEY"))
        self.service = NeoWsService(api_service)

    def _format_feed_results(self, data: dict) -> str:
        """Format feed results into readable text."""
        result = [f"Element Count: {data.get('element_count', 0)} asteroids found"]
        
        for date, asteroids in data.get('near_earth_objects', {}).items():
            result.extend([
                f"\nDate: {date}",
                f"Number of asteroids: {len(asteroids)}"
            ])
            
            for ast_data in asteroids:
                asteroid = Asteroid(**ast_data)
                result.extend([
                    "\n" + asteroid.format_info(),
                    "-" * 50
                ])
        
        return "\n".join(result)

    async def execute(
        self,
        operation: str = "feed",
        start_date: str = None,
        end_date: str = None,
        asteroid_id: str = None,
    ) -> str:
        """Execute NeoWs API request with specified parameters."""
        try:
            if operation == "feed":
                data = await self.service.get_feed(start_date, end_date)
                return self._format_feed_results(data)
            
            elif operation == "lookup":
                if not asteroid_id:
                    raise ValueError("asteroid_id is required for lookup operation")
                data = await self.service.lookup_asteroid(asteroid_id)
                return Asteroid(**data).format_info()
            
            elif operation == "browse":
                data = await self.service.browse_asteroids()
                result = ["Browse Results:"]
                for ast_data in data.get('near_earth_objects', []):
                    asteroid = Asteroid(**ast_data)
                    result.extend([
                        "\n" + asteroid.format_info(),
                        "-" * 50
                    ])
                return "\n".join(result)
            
            else:
                raise ValueError(f"Invalid operation: {operation}. Must be one of: feed, lookup, browse")
            
        except Exception as e:
            logger.error(f"Error executing NeoWs tool: {str(e)}")
            raise

if __name__ == "__main__":
    # Example usage
    tool = NasaNeoWsTool()
    
    async def test_tool():
        # Test feed operation
        print("Testing Feed Operation:")
        result = await tool.execute(operation="feed")
        print(result)
        
        # Test lookup operation
        print("\nTesting Lookup Operation:")
        result = await tool.execute(operation="lookup", asteroid_id="3542519")
        print(result)
        
        # Test browse operation
        print("\nTesting Browse Operation:")
        result = await tool.execute(operation="browse")
        print(result)

    asyncio.run(test_tool())
