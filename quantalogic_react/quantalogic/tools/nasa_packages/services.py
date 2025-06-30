"""Services for interacting with NASA APIs."""

from datetime import datetime, timedelta
from typing import Any, Dict, List

import aiohttp
from loguru import logger


class NasaApiService:
    """Service for making NASA API requests."""
    
    def __init__(self, api_key: str):
        """Initialize with API key."""
        self.api_key = api_key
        self.base_url = "https://api.nasa.gov/neo/rest/v1"

    async def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an API request to NASA endpoints.
        
        Args:
            endpoint: API endpoint path
            params: Optional query parameters
            
        Returns:
            API response data
            
        Raises:
            RuntimeError: If request fails
        """
        params = params or {}
        params["api_key"] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    error_text = await response.text()
                    raise RuntimeError(f"API error {response.status}: {error_text}")
        except Exception as e:
            logger.error(f"NASA API request failed: {str(e)}")
            raise RuntimeError(f"Failed to fetch data: {str(e)}")

class NeoWsService:
    """Service for Near Earth Object Web Service operations."""
    
    def __init__(self, api_service: NasaApiService):
        """Initialize with API service."""
        self.api = api_service

    @staticmethod
    def validate_date(date_str: str) -> str:
        """Validate date string format."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")

    async def get_feed(self, start_date: str, end_date: str = None) -> Dict[str, Any]:
        """Get asteroid feed for date range."""
        start_date = self.validate_date(start_date)
        if not end_date:
            end_date = (datetime.strptime(start_date, "%Y-%m-%d") + 
                       timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            end_date = self.validate_date(end_date)
            
        return await self.api.fetch_data("feed", {
            "start_date": start_date,
            "end_date": end_date
        })

    async def lookup_asteroid(self, asteroid_id: str) -> Dict[str, Any]:
        """Look up specific asteroid by ID."""
        return await self.api.fetch_data(f"neo/{asteroid_id}")

    async def browse_asteroids(self) -> Dict[str, Any]:
        """Browse asteroid dataset."""
        return await self.api.fetch_data("neo/browse")
