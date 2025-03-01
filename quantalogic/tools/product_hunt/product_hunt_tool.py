"""Product Hunt API tool.

This tool provides access to Product Hunt's GraphQL API to retrieve information about
products, posts, collections, and more.
"""

from datetime import datetime
from typing import Any, Dict, List

from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument

from .services import ProductHuntService


class ProductHuntTool(Tool):
    """Tool for accessing Product Hunt's GraphQL API.
    
    Features:
    - Search for products
    - Get product details
    - Get posts by date
    - Get collections
    - Get topics
    """
    
    name: str = "product_hunt_tool"
    description: str = (
        "Product Hunt API tool for retrieving information about products, "
        "posts, collections, and more using GraphQL API."
    )
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="query_type",
            arg_type="string",
            description="Type of query to execute (posts, product, search, collections)",
            required=True,
            example="posts",
        ),
        ToolArgument(
            name="search_query",
            arg_type="string",
            description="Search query for products/posts",
            required=False,
            example="AI tools",
        ),
        ToolArgument(
            name="date",
            arg_type="string",
            description="Date for posts query (YYYY-MM-DD format)",
            required=False,
            example="2024-02-24",
        ),
        ToolArgument(
            name="first",
            arg_type="int",
            description="Number of items to return (max 20)",
            required=False,
            default="10",
            example="5",
        ),
    ]
    
    def __init__(self):
        """Initialize the Product Hunt tool."""
        super().__init__()
        self.service = ProductHuntService()
        
    def execute(self, **kwargs) -> str:
        """Execute the Product Hunt API tool with provided arguments.
        
        Args:
            **kwargs: Tool arguments including query_type and other parameters
            
        Returns:
            Formatted string containing the API response data
            
        Raises:
            ValueError: If required arguments are missing
            RuntimeError: If the API request fails
        """
        query_type = kwargs.get("query_type")
        if not query_type:
            raise ValueError("query_type is required")
            
        try:
            if query_type == "posts":
                return self._get_posts(kwargs)
            elif query_type == "search":
                return self._search_products(kwargs)
            elif query_type == "collections":
                return self._get_collections(kwargs)
            else:
                raise ValueError(f"Unsupported query_type: {query_type}")
        except Exception as e:
            logger.error(f"Product Hunt tool execution failed: {str(e)}")
            raise RuntimeError(f"Tool execution failed: {str(e)}")
    
    def _get_posts(self, params: Dict[str, Any]) -> str:
        query = """
        query Posts($first: Int, $postedAfter: DateTime, $postedBefore: DateTime) {
            posts(first: $first, postedAfter: $postedAfter, postedBefore: $postedBefore) {
                edges {
                    node {
                        id
                        name
                        tagline
                        description
                        url
                        votesCount
                        website
                        thumbnail {
                            url
                        }
                        topics {
                            edges {
                                node {
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "first": min(int(params.get("first", 10)), 20),
        }
        
        if params.get("date"):
            try:
                date = datetime.strptime(params["date"], "%Y-%m-%d")
                variables["postedAfter"] = date.replace(hour=0, minute=0, second=0).isoformat()
                variables["postedBefore"] = date.replace(hour=23, minute=59, second=59).isoformat()
            except ValueError as e:
                raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {str(e)}")
        
        result = self.service.execute_query(query, variables)
        posts = result.get("data", {}).get("posts", {}).get("edges", [])
        
        if not posts:
            return "No posts found"
            
        formatted_posts = []
        for post in posts:
            node = post["node"]
            topics = [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])]
            formatted_posts.append(
                f"• {node['name']}\n"
                f"  {node['tagline']}\n"
                f"  Topics: {', '.join(topics)}\n"
                f"  Votes: {node['votesCount']}\n"
                f"  URL: {node['url']}\n"
            )
            
        return "\n".join(formatted_posts)
        
    def _search_products(self, params: Dict[str, Any]) -> str:
        query = """
        query Search($query: String!, $first: Int) {
            search(query: $query, first: $first, types: [POST]) {
                edges {
                    node {
                        ... on Post {
                            id
                            name
                            tagline
                            description
                            url
                            votesCount
                            topics {
                                edges {
                                    node {
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        if not params.get("search_query"):
            raise ValueError("search_query is required for search")
            
        variables = {
            "query": params["search_query"],
            "first": min(int(params.get("first", 10)), 20),
        }
        
        result = self.service.execute_query(query, variables)
        products = result.get("data", {}).get("search", {}).get("edges", [])
        
        if not products:
            return "No products found"
            
        formatted_products = []
        for product in products:
            node = product["node"]
            topics = [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])]
            formatted_products.append(
                f"• {node['name']}\n"
                f"  {node['tagline']}\n"
                f"  Topics: {', '.join(topics)}\n"
                f"  Votes: {node['votesCount']}\n"
                f"  URL: {node['url']}\n"
            )
            
        return "\n".join(formatted_products)

        
    def _get_collections(self, params: Dict[str, Any]) -> str:
        query = """
        query Collections($first: Int) {
            collections(first: $first) {
                edges {
                    node {
                        id
                        name
                        description
                        url
                        productsCount
                        posts {
                            totalCount
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "first": min(int(params.get("first", 10)), 20),
        }
        
        result = self.service.execute_query(query, variables)
        collections = result.get("data", {}).get("collections", {}).get("edges", [])
        
        if not collections:
            return "No collections found"
            
        formatted_collections = []
        for collection in collections:
            node = collection["node"]
            formatted_collections.append(
                f"• {node['name']}\n"
                f"  Products: {node['productsCount']}\n"
                f"  Posts: {node['posts']['totalCount']}\n"
                f"  {node['description']}\n"
                f"  URL: {node['url']}\n"
            )
            
        return "\n".join(formatted_collections)