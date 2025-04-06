import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

import aiohttp
from pydantic import BaseModel, Field, ValidationError

from quantalogic.tools import create_tool

logger = logging.getLogger(__name__)

# Rate limiting with proper async context manager
class RateLimiter:
    def __init__(self, max_concurrent: int = 50):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limit(self, coro):
        """Execute the coroutine under the rate limit."""
        async with self.semaphore:
            return await coro

# Global rate limiter
RATE_LIMITER = RateLimiter(max_concurrent=50)

# API configuration
class HNConfig:
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    ALGOLIA_URL = "https://hn.algolia.com/api/v1"
    TIMEOUT = 10.0  # seconds
    DEFAULT_HEADERS = {"User-Agent": "QuantaLogic-HN-Client/1.0"}


# Pydantic Models with improved documentation and structure
class ItemType(str, Enum):
    story = 'story'
    comment = 'comment'
    job = 'job'
    poll = 'poll'
    pollopt = 'pollopt'


class Item(BaseModel):
    id: int
    by: str = Field(description="Username of the item's author")
    time: int = Field(description="Creation timestamp (Unix time)")
    kids: Optional[List[int]] = Field(default=None, description="List of comment IDs")
    type: ItemType
    deleted: Optional[bool] = Field(default=None, description="True if the item is deleted")
    comments: Optional[List['Comment']] = None  # Forward reference for recursive comments
    dead: Optional[bool] = Field(default=None, description="True if the item is dead")

    class Config:
        extra = 'ignore'
        json_schema_extra = {
            "example": {
                "id": 123456,
                "by": "username",
                "time": 1617183600,
                "type": "story"
            }
        }


class Story(Item):
    type: ItemType = ItemType.story
    title: str = Field(description="Story title")
    url: Optional[str] = Field(default=None, description="URL of the story")
    text: Optional[str] = Field(default=None, description="Story text if self-post")
    score: int = Field(description="Story score (points)")
    descendants: Optional[int] = Field(default=None, description="Total comment count")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123456,
                "by": "username",
                "time": 1617183600,
                "title": "Example Story",
                "url": "https://example.com",
                "score": 100,
                "type": "story"
            }
        }


class Comment(Item):
    type: ItemType = ItemType.comment
    text: str = Field(description="Comment text in HTML")
    parent: Optional[int] = Field(default=None, description="Parent story or comment ID")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123456,
                "by": "username",
                "time": 1617183600,
                "text": "This is a comment",
                "type": "comment"
            }
        }


class User(BaseModel):
    id: str = Field(description="Username")
    created: int = Field(description="Creation timestamp (Unix time)")
    karma: int = Field(description="User's karma points")
    about: Optional[str] = Field(default=None, description="User's about text in HTML")
    submitted: List[int] = Field(description="IDs of user's submissions")

    class Config:
        extra = 'ignore'


class UserInfo(BaseModel):
    user: User
    submitted_stories: List[Story] = Field(description="User's submitted stories")


class SearchResults(BaseModel):
    hits: List[Story] = Field(description="Matching stories")
    page: int = Field(description="Current page number")
    total_hits: int = Field(description="Total number of matches")
    processing_time_ms: int = Field(description="Search processing time in milliseconds")


class StorySort(str, Enum):
    top = 'top'
    new = 'new'
    best = 'best'
    ask = 'ask'
    show = 'show'
    job = 'job'


async def fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    backoff_factor: float = 0.5
) -> dict:
    """Fetch data from URL with exponential backoff retries for transient errors."""
    retries = 0
    while retries < max_retries:
        try:
            # Properly await the rate limiter
            async with RATE_LIMITER.semaphore:
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
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Request to {url} failed: {str(e)}. Retry {retries + 1}/{max_retries}")
        
        # Exponential backoff with jitter
        delay = backoff_factor * (2 ** retries) * (0.5 + 0.5 * asyncio.get_event_loop().time() % 1)
        await asyncio.sleep(delay)
        retries += 1
    
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} retries")


async def fetch_and_parse_item(
    session: aiohttp.ClientSession,
    item_id: int
) -> Optional[Union[Item, Story, Comment]]:
    """Fetch and parse a Hacker News item with improved validation and error handling."""
    url = f"{HNConfig.BASE_URL}/item/{item_id}.json"
    try:
        data = await fetch_with_retry(session, url)
        if not data:
            logger.debug(f"Item {item_id} not found or empty")
            return None
    except RuntimeError as e:
        logger.error(f"Failed to fetch item {item_id}: {str(e)}")
        raise

    if data.get('deleted', False) or data.get('dead', False):
        logger.debug(f"Skipping deleted or dead item {item_id}")
        return None

    try:
        item_type = data.get('type')
        if item_type == ItemType.story.value:
            return Story(**data)
        elif item_type == ItemType.comment.value:
            if not data.get('by') or not data.get('text'):
                logger.debug(f"Comment {item_id} missing required fields")
                return None
            return Comment(**data)
        else:
            logger.info(f"Item {item_id} has type {item_type}, using generic Item")
            return Item(**data)
    except ValidationError as e:
        logger.error(f"Validation failed for item {item_id}: {str(e)}")
        return None


async def fetch_items_batch(
    session: aiohttp.ClientSession,
    item_ids: List[int],
    batch_size: int = 10
) -> List[Optional[Union[Item, Story, Comment]]]:
    """Batch fetch items with improved concurrency control and error handling."""
    if not item_ids:
        return []
        
    results = []
    # Process in batches to avoid overwhelming the API
    for i in range(0, len(item_ids), batch_size):
        batch = item_ids[i:i+batch_size]
        tasks = [fetch_and_parse_item(session, item_id) for item_id in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and None values
        valid_items = []
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Error processing item: {str(result)}")
            elif result is not None:
                valid_items.append(result)
        
        results.extend(valid_items)
    
    return results


async def fetch_comments(
    session: aiohttp.ClientSession,
    item: Union[Story, Comment],
    max_depth: int = 3,
    current_depth: int = 0
) -> None:
    """Recursively fetch comments with depth control to prevent excessive API calls."""
    if current_depth >= max_depth:
        # Mark that there may be more comments
        if item.kids and not item.comments:
            item.comments = []
        return
        
    if item.kids:
        comments = await fetch_items_batch(session, item.kids)
        valid_comments = [c for c in comments if isinstance(c, Comment)]
        
        # Recursively fetch child comments with incremented depth
        if current_depth < max_depth - 1:
            await asyncio.gather(*[
                fetch_comments(session, comment, max_depth, current_depth + 1) 
                for comment in valid_comments
            ])
            
        item.comments = valid_comments
    else:
        item.comments = []


class HackerNewsClient:
    """Client for interacting with the Hacker News API."""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the client with an optional session."""
        self._session = session
        self._own_session = session is None
        
    async def __aenter__(self):
        """Support for async context manager."""
        if self._own_session:
            self._session = aiohttp.ClientSession(headers=HNConfig.DEFAULT_HEADERS)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        if self._own_session and self._session:
            await self._session.close()
            
    @property
    def session(self) -> aiohttp.ClientSession:
        """Get the client session, creating one if needed."""
        if self._session is None:
            self._session = aiohttp.ClientSession(headers=HNConfig.DEFAULT_HEADERS)
            self._own_session = True
        return self._session
    
    async def get_stories(self, story_type: StorySort = StorySort.top, limit: int = 30) -> List[Story]:
        """Fetch stories by type with improved error handling."""
        ENDPOINTS = {
            StorySort.top: 'topstories',
            StorySort.new: 'newstories',
            StorySort.best: 'beststories',
            StorySort.ask: 'askstories',
            StorySort.show: 'showstories',
            StorySort.job: 'jobstories'
        }
        
        try:
            story_ids = await fetch_with_retry(
                self.session,
                f"{HNConfig.BASE_URL}/{ENDPOINTS[story_type]}.json"
            )
            items = await fetch_items_batch(self.session, story_ids[:limit])
            return [item for item in items if isinstance(item, Story)]
        except Exception as e:
            logger.error(f"Failed to fetch {story_type} stories: {str(e)}")
            raise
    
    async def get_story_with_comments(
        self, 
        story_id: int, 
        comment_depth: int = 2
    ) -> Optional[Story]:
        """Fetch a single story with nested comments."""
        story = await fetch_and_parse_item(self.session, story_id)
        if not isinstance(story, Story):
            return None
            
        await fetch_comments(self.session, story, max_depth=comment_depth)
        return story
    
    async def get_user(self, username: str) -> Optional[User]:
        """Fetch user information."""
        try:
            user_data = await fetch_with_retry(
                self.session,
                f"{HNConfig.BASE_URL}/user/{username}.json"
            )
            if not user_data:
                return None
            return User(**user_data)
        except Exception as e:
            logger.error(f"Failed to fetch user {username}: {str(e)}")
            return None
    
    async def get_user_stories(
        self, 
        username: str, 
        limit: int = 10
    ) -> UserInfo:
        """Fetch user data with their submitted stories."""
        user = await self.get_user(username)
        if not user:
            raise ValueError(f"User {username} not found")
            
        story_ids = [id for id in user.submitted[:limit*3]]  # Fetch more to account for comments/deleted items
        items = await fetch_items_batch(self.session, story_ids)
        stories = [item for item in items if isinstance(item, Story)][:limit]
        
        return UserInfo(
            user=user,
            submitted_stories=stories
        )
    
    async def search(
        self, 
        query: str, 
        sort_by_date: bool = False, 
        limit: int = 20,
        tags: Optional[List[str]] = None
    ) -> SearchResults:
        """Search stories using the Algolia API with improved field mapping."""
        url = f"{HNConfig.ALGOLIA_URL}/{'search_by_date' if sort_by_date else 'search'}"
        
        params = {
            "query": query,
            "hitsPerPage": limit,
            "tags": f"({','.join(tags)})" if tags else "story",
        }
        
        try:
            result = await fetch_with_retry(self.session, url, params=params)
            
            stories = [
                Story(
                    id=int(hit["objectID"]),
                    by=hit.get("author", "unknown"),
                    time=hit.get("created_at_i", 0),
                    title=hit.get("title", "Untitled"),
                    url=hit.get("url"),
                    text=hit.get("story_text"),
                    score=hit.get("points", 0),
                    kids=hit.get("children", []),
                    type=ItemType.story
                )
                for hit in result.get("hits", [])
                if "objectID" in hit and "title" in hit
            ]
            
            return SearchResults(
                hits=stories,
                page=result.get("page", 0),
                total_hits=result.get("nbHits", 0),
                processing_time_ms=result.get("processingTimeMS", 0)
            )
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            raise


@create_tool
async def mcp_hn_get_stories(
    story_type: str = "top", 
    num_stories: int = 30
) -> List[Dict]:
    """
    Fetch popular stories from Hacker News.
    
    Args:
        story_type: Type of stories to fetch - 'top', 'new', 'best', 'ask', 'show', or 'job'
        num_stories: Number of stories to retrieve (max 100)
        
    Returns:
        List of story objects
    """
    try:
        story_type_enum = StorySort(story_type.lower())
    except ValueError:
        raise ValueError(f"Invalid story_type: {story_type}. Valid options: {[t.value for t in StorySort]}")
    
    # Limit to reasonable range
    num_stories = max(1, min(100, num_stories))
    
    async with HackerNewsClient() as client:
        stories = await client.get_stories(story_type_enum, num_stories)
        return [story.dict() for story in stories]


@create_tool
async def mcp_hn_get_story_details(
    story_id: int, 
    comment_depth: int = 2
) -> Dict:
    """
    Get detailed information about a specific Hacker News story, including comments.
    
    Args:
        story_id: The ID of the story to retrieve
        comment_depth: How deep to fetch nested comments (0-3, where 0 means no comments)
        
    Returns:
        Story object with nested comments
    """
    # Validate and limit comment depth
    comment_depth = max(0, min(3, comment_depth))
    
    async with HackerNewsClient() as client:
        story = await client.get_story_with_comments(story_id, comment_depth)
        if not story:
            raise ValueError(f"Story with ID {story_id} not found or is not a story")
        return story.dict()


@create_tool
async def mcp_hn_get_user_info(
    username: str, 
    num_stories: int = 10
) -> Dict:
    """
    Get information about a Hacker News user and their recent submissions.
    
    Args:
        username: The username to look up
        num_stories: Number of user's stories to retrieve (max 50)
        
    Returns:
        User information including profile data and recent submissions
    """
    # Limit to reasonable range
    num_stories = max(1, min(50, num_stories))
    
    async with HackerNewsClient() as client:
        user_info = await client.get_user_stories(username, num_stories)
        return user_info.dict()


@create_tool
async def mcp_hn_search_stories(
    query: str, 
    search_by_date: bool = False, 
    num_results: int = 20,
    filter_tags: Optional[List[str]] = None
) -> Dict:
    """
    Search for Hacker News stories using keywords.
    
    Args:
        query: Search query string
        search_by_date: Sort results by date (newest first) if True
        num_results: Number of results to return (max 100)
        filter_tags: Optional list of tags to filter results (e.g., ['story', 'show_hn', 'ask_hn'])
        
    Returns:
        Search results with stories matching the query
    """
    # Limit to reasonable range
    num_results = max(1, min(100, num_results))
    
    async with HackerNewsClient() as client:
        search_results = await client.search(
            query, 
            sort_by_date=search_by_date, 
            limit=num_results,
            tags=filter_tags
        )
        return search_results.dict()


async def main() -> None:
    """Test function demonstrating HackerNewsClient usage."""
    logging.basicConfig(level=logging.INFO)
    
    try:
        async with HackerNewsClient() as client:
            print("=== Testing get_stories ===")
            stories = await client.get_stories(StorySort.top, 5)
            print(f"Fetched {len(stories)} top stories")
            for s in stories:
                print(f"- {s.title} ({s.score} points)")
            
            print("\n=== Testing get_story_with_comments ===")
            if stories:
                story = await client.get_story_with_comments(stories[0].id, 1)
                print(f"Story: {story.title}")
                if story.comments:
                    print(f"Comments: {len(story.comments)}")
            
            print("\n=== Testing search ===")
            search_results = await client.search("python", limit=3)
            print(f"Found {search_results.total_hits} results for 'python'")
            for hit in search_results.hits:
                print(f"- {hit.title}")
            
    except Exception as e:
        print(f"Error in test: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())