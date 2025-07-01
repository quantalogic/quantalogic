"""Product Hunt API services.

This module provides service functions for interacting with the Product Hunt GraphQL API.
"""

import os
from typing import Any, Dict

import requests
from loguru import logger


class ProductHuntService:
    """Service class for Product Hunt API interactions."""
    
    def __init__(self):
        """Initialize the Product Hunt API service."""
        self.api_key = os.getenv("PRODUCT_HUNT_API_KEY")
        self.api_secret = os.getenv("PRODUCT_HUNT_API_SECRET")
        self.bearer_token = os.getenv("PRODUCT_HUNT_BEARER_TOKEN")
        self.base_url = "https://api.producthunt.com/v2/api/graphql"
        
        if not self.bearer_token:
            raise ValueError("PRODUCT_HUNT_BEARER_TOKEN environment variable is required")

    def execute_query(self, query: str, variables: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Execute a GraphQL query against the Product Hunt API.
        
        Args:
            query: The GraphQL query string
            variables: Optional variables for the GraphQL query
            
        Returns:
            The API response data
            
        Raises:
            RuntimeError: If the API request fails
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bearer_token}",
            "X-Product-Hunt-Api-Key": self.api_key,
            "User-Agent": "QuantaLogic/1.0"
        }
        try:
            response = requests.post(
                self.base_url,
                json={"query": query, "variables": variables or {}},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    raise RuntimeError(f"GraphQL query failed: {data['errors']}")
                return data
            else:
                raise RuntimeError(f"API request failed with status {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"Failed to execute Product Hunt API query: {str(e)}")
            raise RuntimeError(f"Failed to execute Product Hunt API query: {str(e)}")
