import asyncio
import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Configure logger
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# API Configuration
class HNConfig(dict):
    """API configuration for Hacker News."""
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    ALGOLIA_URL = "https://hn.algolia.com/api/v1"
    TIMEOUT = 10.0  # seconds
    DEFAULT_HEADERS = {"User-Agent": "Enhanced-HN-Client/1.0"}
    CONNECTION_LIMIT = 100
    CONNECTION_LIMIT_PER_HOST = 20

# Data Models
@dataclass
class HNItem(dict):
    """Simple dataclass for Hacker News items."""
    id: int
    time: int
    type: str
    by: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    score: Optional[int] = None
    descendants: Optional[int] = None
    kids: Optional[List[int]] = None
    text: Optional[str] = None
    
    def __getitem__(self, key):
        """Support dictionary-style access to dataclass attributes.
        
        Args:
            key: Attribute name to access
            
        Returns:
            The attribute value if it exists
            
        Raises:
            KeyError: If the attribute doesn't exist
        """
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)
    
    @property
    def datetime(self) -> datetime:
        """Convert Unix timestamp to datetime object."""
        return datetime.fromtimestamp(self.time)
    
    @property
    def formatted_date(self) -> str:
        """Return human-readable date string (YYYY-MM-DD)."""
        return self.datetime.strftime('%Y-%m-%d')
    
    @property
    def formatted_time(self) -> str:
        """Return human-readable time string (HH:MM:SS)."""
        return self.datetime.strftime('%H:%M:%S')
    
    @property
    def formatted_datetime(self) -> str:
        """Return human-readable date and time string."""
        return self.datetime.strftime('%Y-%m-%d %H:%M:%S')

@dataclass
class HNComment(dict):
    """Simple dataclass for Hacker News comments."""
    id: int
    time: int
    parent: int
    type: str = "comment"
    by: Optional[str] = None
    text: Optional[str] = None
    kids: Optional[List[int]] = None
    
    def __getitem__(self, key):
        """Support dictionary-style access to dataclass attributes.
        
        Args:
            key: Attribute name to access
            
        Returns:
            The attribute value if it exists
            
        Raises:
            KeyError: If the attribute doesn't exist
        """
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)
    
    @property
    def datetime(self) -> datetime:
        """Convert Unix timestamp to datetime object."""
        return datetime.fromtimestamp(self.time)
    
    @property
    def formatted_date(self) -> str:
        """Return human-readable date string (YYYY-MM-DD)."""
        return self.datetime.strftime('%Y-%m-%d')
    
    @property
    def formatted_time(self) -> str:
        """Return human-readable time string (HH:MM:SS)."""
        return self.datetime.strftime('%H:%M:%S')
    
    @property
    def formatted_datetime(self) -> str:
        """Return human-readable date and time string."""
        return self.datetime.strftime('%Y-%m-%d %H:%M:%S')

@dataclass
class HNItemDetails(HNItem):
    """Extended item dataclass including comments."""
    comments: Optional[List[Dict]] = None

@dataclass
class HNUser(dict):
    """Simple dataclass for Hacker News user data."""
    id: str
    created: int
    karma: int
    about: Optional[str] = None
    submitted: Optional[List[int]] = None
    items: Optional[List[HNItem]] = None
    
    def __getitem__(self, key):
        """Support dictionary-style access to dataclass attributes.
        
        Args:
            key: Attribute name to access
            
        Returns:
            The attribute value if it exists
            
        Raises:
            KeyError: If the attribute doesn't exist
        """
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

# Helper Functions
async def fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    backoff_factor: float = 0.5,
) -> dict:
    """Fetch data with retry logic and exponential backoff."""
    retries = 0
    while retries < max_retries:
        try:
            async with session.get(url, params=params, timeout=HNConfig.TIMEOUT) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logger.warning(f"Not found: {url}")
                    return {}
                elif 500 <= response.status < 600:
                    logger.warning(f"Server error {response.status} for {url}, retry {retries + 1}/{max_retries}")
                else:
                    raise RuntimeError(f"HTTP error {response.status} for {url}")
        except (aiohttp.ClientError, TimeoutError) as e:
            logger.warning(f"Request to {url} failed: {str(e)}. Retry {retries + 1}/{max_retries}")

        delay = backoff_factor * (2 ** retries)
        await asyncio.sleep(delay)
        retries += 1

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} retries")

def clean_html(text: str) -> str:
    """Convert HTML content to plain text."""
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace("<p>", "\n").replace("</p>", "")
    text = re.sub(r"<a\s+href=[^>]*>(.*?)</a>", r"\1", text)
    text = re.sub(r"<[^>]*>", "", text)
    return text.strip()

# Main Client
class HackerNewsClient:
    """Enhanced client for interacting with the Hacker News API."""
    
    def __init__(self):
        self._session = None
        self._connector = aiohttp.TCPConnector(
            limit=HNConfig.CONNECTION_LIMIT,
            limit_per_host=HNConfig.CONNECTION_LIMIT_PER_HOST,
            force_close=False,
            enable_cleanup_closed=True
        )

    async def __aenter__(self):
        """Asynchronous context manager entry point.
        
        Initializes and returns the client session.
        
        Returns:
            self: The initialized HackerNewsClient instance
        """
        self._session = aiohttp.ClientSession(
            headers=HNConfig.DEFAULT_HEADERS,
            connector=self._connector,
            timeout=aiohttp.ClientTimeout(total=HNConfig.TIMEOUT)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Asynchronous context manager exit point.
        
        Cleans up the client session.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        if self._session:
            await self._session.close()

    async def _fetch_items_batch(self, item_ids: List[int]) -> List[Dict]:
        """Fetch multiple items in parallel using asyncio.gather."""
        tasks = [
            fetch_with_retry(self._session, f"{HNConfig.BASE_URL}/item/{item_id}.json")
            for item_id in item_ids
        ]
        return await asyncio.gather(*tasks)
        
    async def get_items_paginated(
        self, 
        endpoint: str, 
        page: int = 1, 
        per_page: int = 10,
        max_items: int = 100
    ) -> List[HNItem]:
        """Get paginated items from an endpoint.
        
        Args:
            endpoint: API endpoint (e.g. 'topstories', 'newstories')
            page: Page number (1-based)
            per_page: Items per page
            max_items: Maximum total items to fetch
            
        Returns:
            List of HNItem objects for the requested page
        """
        # Fetch all IDs first
        all_ids = await fetch_with_retry(
            self._session, 
            f"{HNConfig.BASE_URL}/{endpoint}.json"
        )
        
        if not all_ids:
            return []
            
        # Apply max_items limit
        all_ids = all_ids[:max_items]
        
        # Calculate pagination bounds
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_ids = all_ids[start_idx:end_idx]
        
        # Fetch items in parallel
        items_data = await self._fetch_items_batch(page_ids)
        return [HNItem(**item) for item in items_data if item]
        
    async def get_top_items(self, page: int = 1, per_page: int = 30) -> List[HNItem]:
        """Get paginated top items."""
        return await self.get_items_paginated("topstories", page, per_page)
        
    async def get_new_items(self, page: int = 1, per_page: int = 30) -> List[HNItem]:
        """Get paginated new items."""
        return await self.get_items_paginated("newstories", page, per_page)
        
    async def get_best_items(self, page: int = 1, per_page: int = 30) -> List[HNItem]:
        """Get paginated best items."""
        return await self.get_items_paginated("beststories", page, per_page)
        
    async def get_ask_items(self, page: int = 1, per_page: int = 30) -> List[HNItem]:
        """Get paginated Ask HN items."""
        items = await self.get_items_paginated("askstories", page, per_page)
        return [item for item in items if item.type == "story" and 
               (item.title or "").startswith("Ask HN:")]
        
    async def get_show_items(self, page: int = 1, per_page: int = 30) -> List[HNItem]:
        """Get paginated Show HN items."""
        items = await self.get_items_paginated("showstories", page, per_page)
        return [item for item in items if item.type == "story" and 
               (item.title or "").startswith("Show HN:")]
        
    async def get_job_items(self, page: int = 1, per_page: int = 30) -> List[HNItem]:
        """Get paginated job items."""
        return await self.get_items_paginated("jobstories", page, per_page)

    async def get_item(self, item_id: int) -> Optional[HNItem]:
        """Fetch a single item by ID."""
        data = await fetch_with_retry(self._session, f"{HNConfig.BASE_URL}/item/{item_id}.json")
        if not data or data.get("deleted") or data.get("dead"):
            return None

        return HNItem(
            id=data.get("id"),
            time=data.get("time", 0),
            type=data.get("type", "story"),
            by=data.get("by"),
            title=data.get("title"),
            url=data.get("url"),
            score=data.get("score"),
            descendants=data.get("descendants"),
            kids=data.get("kids"),
            text=data.get("text")
        )

    async def get_item_with_comments(
        self, item_id: int, comment_depth: int = 2, clean_text: bool = False
    ) -> Optional[HNItemDetails]:
        """Fetch an item with its comments.
        
        Note: Comments may include a dynamic 'replies' attribute for nested comments.
        """
        item = await self.get_item(item_id)
        if not item or item.type not in ["story", "job"]:
            return None

        item_details = HNItemDetails(**item.__dict__)

        if not item.kids:
            item_details.comments = []
            return item_details

        comments = await self._get_comments(item.kids, comment_depth, clean_text)
        item_details.comments = comments
        return item_details

    async def _get_comments(
        self, comment_ids: List[int], depth: int = 1, clean_text: bool = False, current_depth: int = 0
    ) -> List[Dict]:
        """Recursively fetch comments."""
        if current_depth >= depth or not comment_ids:
            return []

        comments = []
        for comment_id in comment_ids:
            data = await fetch_with_retry(self._session, f"{HNConfig.BASE_URL}/item/{comment_id}.json")
            if not data or data.get("type") != "comment" or data.get("deleted") or data.get("dead"):
                continue

            text = data.get("text", "")
            if clean_text:
                text = clean_html(text)

            comment = {
                "id": data.get("id"),
                "by": data.get("by"),
                "text": text,
                "time": data.get("time", 0),
                "kids": data.get("kids"),
                "parent": data.get("parent", 0),
                "type": "comment"
            }

            if current_depth < depth - 1 and comment["kids"]:
                child_comments = await self._get_comments(
                    comment["kids"], depth, clean_text, current_depth + 1
                )
                comment["replies"] = child_comments  # Dynamic attribute

            comments.append(comment)

        return comments

    async def get_user(self, username: str) -> Optional[HNUser]:
        """Fetch user information."""
        data = await fetch_with_retry(self._session, f"{HNConfig.BASE_URL}/user/{username}.json")
        if not data:
            return None

        return HNUser(
            id=data.get("id", ""),
            created=data.get("created", 0),
            karma=data.get("karma", 0),
            about=data.get("about"),
            submitted=data.get("submitted")
        )

    async def get_user_with_items(
        self, username: str, limit: int = 10, include_types: List[str] = ["story"]
    ) -> Optional[HNUser]:
        """Fetch user with submitted items."""
        user = await self.get_user(username)
        if not user or not user.submitted:
            return user

        items = []
        for item_id in user.submitted[:limit * 3]:
            item = await self.get_item(item_id)
            if item and item.type in include_types:
                items.append(item)
                if len(items) >= limit:
                    break

        user.items = items
        return user

    async def search(
        self, query: str, sort_by_date: bool = False, limit: int = 20, prefix: Optional[str] = None
    ) -> List[HNItem]:
        """Search for items using Algolia API."""
        endpoint = "search_by_date" if sort_by_date else "search"
        url = f"{HNConfig.ALGOLIA_URL}/{endpoint}"

        if prefix:
            query = f"{prefix} {query}"

        params = {
            "query": query,
            "hitsPerPage": limit,
            "tags": "story",  # Default to stories
        }

        result = await fetch_with_retry(self._session, url, params=params)
        hits = result.get("hits", [])

        items = []
        for hit in hits:
            if "objectID" not in hit or "title" not in hit:
                continue

            item = HNItem(
                id=int(hit.get("objectID")),
                time=hit.get("created_at_i", 0),
                type="story",
                by=hit.get("author"),
                title=hit.get("title"),
                url=hit.get("url"),
                score=hit.get("points"),
                descendants=hit.get("num_comments"),
                kids=hit.get("children", []),
                text=hit.get("story_text")
            )
            items.append(item)

        return items

# Simplified Tools with @create_tool
async def get_hn_items(item_type: str = "top", page: int = 1, per_page: int = 30) -> List[HNItem]:
    """Fetch popular items from Hacker News.
    
    Args:
        item_type: Type of items to fetch. One of:
            - 'top': Top stories (default)
            - 'new': Newest stories
            - 'best': Highest voted stories
            - 'ask_hn': Ask HN posts
            - 'show_hn': Show HN posts
            - 'job': Job postings
        page: Page number (1-based)
        per_page: Items per page (1-100, default 30)
    
    Returns:
        List[HNItem]: A list of HNItem objects containing:
            - id (int): Unique item ID
            - title (str): Story title
            - url (str): Story URL if external link
            - score (int): Upvotes count
            - by (str): Author username
            - time (int): Unix timestamp of posting
            - descendants (int): Comment count for stories
            - type (str): Always "story" for this endpoint
    
    Example Return:
        [
            HNItem(
                id=12345,
                title="Show HN: My new project",
                url="https://example.com",
                score=42,
                by="username",
                time=1672531200,
                descendants=10,
                type="story"
            ),
            ...
        ]
    """
    item_type_map = {
        "top": "top_items",
        "new": "new_items",
        "best": "best_items",
        "ask_hn": "ask_items",
        "show_hn": "show_items",
        "job": "job_items"
    }

    if item_type not in item_type_map:
        raise ValueError(f"Invalid item_type: '{item_type}'. Valid options: {', '.join(item_type_map.keys())}")

    per_page = max(1, min(100, per_page))

    async with HackerNewsClient() as client:
        method = getattr(client, f"get_{item_type_map[item_type]}")
        return await method(page=page, per_page=per_page)

async def get_hn_item_details(item_id: int, comment_depth: int = 2, clean_text: bool = True) -> Dict:
    """Fetch a Hacker News item with its comment hierarchy.
    
    Args:
        item_id: Unique ID of the item to fetch
        comment_depth: Depth of nested comments to retrieve (0-3, default 2)
            - 0: No comments
            - 1: Top-level comments only
            - 2: Comments + replies (default)
            - 3: Full comment tree
        clean_text: Whether to clean HTML tags from text (default True)
    
    Returns:
        Dict: A dictionary containing item details and comments
    """
    if not isinstance(item_id, int) or item_id <= 0:
        raise ValueError(f"Invalid item_id: {item_id}. Must be a positive integer.")

    comment_depth = max(0, min(3, comment_depth))

    async with HackerNewsClient() as client:
        item = await client.get_item_with_comments(item_id, comment_depth, clean_text)
        if not item:
            raise ValueError(f"Item with id {item_id} not found")
        return item.__dict__ if hasattr(item, '__dict__') else item

async def get_hn_user(username: str, include_items: bool = True, num_items: int = 10, item_types: List[str] = ["story"]) -> HNUser:
    """Fetch detailed information about a Hacker News user.
    
    Args:
        username: The user's unique username (case-sensitive)
        include_items: Whether to fetch user's submitted items (default True)
        num_items: Number of items to retrieve (1-30, default 10)
        item_types: List of item types to include. Options:
            - "story": Story submissions (default)
            - "comment": Comment submissions
            - "job": Job postings
            - "poll": Poll submissions
            
    Returns:
        HNUser: User profile containing:
            - id (str): Username
            - created (int): Account creation timestamp
            - karma (int): User's reputation score
            - about (str): Profile description (HTML cleaned)
            - submitted (List[int]): IDs of submitted items
            - items (List[HNItem]): Detailed items if include_items=True
                - Only includes types specified in item_types
    
    Example Return:
        HNUser(
            id="username",
            created=1269374400,
            karma=1234,
            about="I build things",
            submitted=[12345, 54321],
            items=[
                HNItem(
                    id=12345,
                    title="My Show HN project",
                    type="story",
                    score=42
                )
            ]
        )
    """
    if not username or not isinstance(username, str):
        raise ValueError("Username must be a non-empty string")

    num_items = max(1, min(30, num_items))

    async with HackerNewsClient() as client:
        if include_items:
            user = await client.get_user_with_items(username, num_items, item_types)
        else:
            user = await client.get_user(username)

        if not user:
            raise ValueError(f"User '{username}' not found")
        return user

async def search_hn(
    query: str,
    sort_by_date: bool = False,
    num_results: int = 20,
    content_type: str = "story"
) -> List[HNItem]:
    """
    Search for items on Hacker News.
    
    Args:
        query: Search query
        sort_by_date: When True, sort by newest first
        num_results: Number of results to return (1-50)
        content_type: Filter by content type ('story', 'ask_hn', 'show_hn', 'all')
        
    Returns:
        List of items matching the query
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")

    num_results = max(1, min(50, num_results))

    content_type_map = {
        "all": None,
        "story": None,
        "ask_hn": "Ask HN:",
        "show_hn": "Show HN:"
    }

    if content_type not in content_type_map:
        raise ValueError(f"Invalid content_type: '{content_type}'. Valid options: {', '.join(content_type_map.keys())}")

    async with HackerNewsClient() as client:
        return await client.search(query, sort_by_date, num_results, content_type_map[content_type])

# Example Usage
async def main():
    """Demonstrate the enhanced Hacker News client with tools."""
    # Fetch top items
    top_items = await get_hn_items(item_type="top", page=1, per_page=5)
    print("=== Top 5 Hacker News Items ===")
    for item in top_items:
        print(f"\n{item.title}")
        print(f"  - Type: {item.type}")
        print(f"  - Author: {item.by}")
        print(f"  - Posted: {item.formatted_datetime}")
        print(f"  - Score: {item.score}")
        print(f"  - Comments: {item.descendants}")
        print(f"  - URL: {item.url}")

    # Fetch item with comments
    if top_items:
        item_details = await get_hn_item_details(top_items[0].id, comment_depth=1, clean_text=True)
        print("\n=== Detailed View for Top Story ===")
        print(f"Title: {item_details['title']}")
        print(f"Author: {item_details['by']}")
        print(f"Posted: {datetime.fromtimestamp(item_details['time']).strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nRecent Comments:")
        for comment in item_details.get('comments', [])[:3]:
            print(f"\n- {comment['by']} ({datetime.fromtimestamp(comment['time']).strftime('%Y-%m-%d %H:%M')}):")
            print(f"  {comment['text'][:100]}{'...' if len(comment['text']) > 100 else ''}")

    # Fetch user with items
    user = await get_hn_user("dang", include_items=True, num_items=3, item_types=["story", "job"])
    print("\n=== User Profile ===")
    print(f"Username: {user.id}")
    print(f"Karma: {user.karma}")
    print(f"Created: {datetime.fromtimestamp(user.created).strftime('%Y-%m-%d')}")
    print("\nRecent Submissions:")
    for item in user.items or []:
        print(f"\n- {item.title} ({item.type})")
        print(f"  Posted: {item.formatted_datetime}")
        print(f"  Score: {item.score}")
        print(f"  URL: {item.url or 'N/A'}")

    # Search Ask HN posts
    ask_items = await search_hn("python", sort_by_date=True, num_results=5, content_type="ask_hn")
    print("\n=== Recent Python-related Ask HN Posts ===")
    for item in ask_items:
        print(f"\n- {item.title}")
        print(f"  Author: {item.by}")
        print(f"  Posted: {item.formatted_datetime}")
        print(f"  Score: {item.score}")
        print(f"  URL: {item.url or 'N/A'}")

    print("\n=== Demo Complete ===")

if __name__ == "__main__":
    asyncio.run(main())