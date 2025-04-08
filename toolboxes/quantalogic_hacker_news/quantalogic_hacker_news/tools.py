import asyncio

# New imports for HTML cleaning and flattening
import html
import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

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


# Pydantic Models with simplified types (no enums)
class Item(BaseModel):
    id: int
    by: str = Field(description="Username of the item's author")
    time: int = Field(description="Creation timestamp (Unix time)")
    kids: Optional[List[int]] = Field(default=None, description="List of comment IDs")
    type: str  # Replaced ItemType enum with plain string
    deleted: Optional[bool] = Field(default=None, description="True if the item is deleted")
    comments: Optional[List["Comment"]] = None  # Forward reference for recursive comments
    dead: Optional[bool] = Field(default=None, description="True if the item is dead")

    class Config:
        extra = "ignore"
        json_schema_extra = {"example": {"id": 123456, "by": "username", "time": 1617183600, "type": "story"}}


class Story(Item):
    type: str = "story"  # Default to "story" instead of ItemType.story
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
                "type": "story",
            }
        }


class Comment(Item):
    type: str = "comment"  # Default to "comment" instead of ItemType.comment
    text: str = Field(description="Comment text in HTML")
    parent: Optional[int] = Field(default=None, description="Parent story or comment ID")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123456,
                "by": "username",
                "time": 1617183600,
                "text": "This is a comment",
                "type": "comment",
            }
        }


class User(BaseModel):
    id: str = Field(description="Username")
    created: int = Field(description="Creation timestamp (Unix time)")
    karma: int = Field(description="User's karma points")
    about: Optional[str] = Field(default=None, description="User's about text in HTML")
    submitted: List[int] = Field(description="IDs of user's submissions")

    class Config:
        extra = "ignore"


class UserInfo(BaseModel):
    user: User
    submitted_stories: List[Story] = Field(description="User's submitted stories")


class SearchResults(BaseModel):
    hits: List[Story] = Field(description="Matching stories")
    page: int = Field(description="Current page number")
    total_hits: int = Field(description="Total number of matches")
    processing_time_ms: int = Field(description="Search processing time in milliseconds")


class HNStory(BaseModel):
    id: int
    title: str
    url: str | None
    score: int
    by: str
    time: int
    descendants: int | None
    kids: List[int] | None
    text: str | None
    type: str


class HNComment(BaseModel):
    id: int
    by: str
    text: str | None
    time: int
    kids: List[int] | None
    parent: int
    type: str = "comment"


class HNStoryDetails(HNStory):
    comments: List[HNComment] | None = None


class HNUserStory(BaseModel):
    id: int
    title: str
    url: str | None
    score: int
    time: int
    descendants: int | None
    type: str


class HNUser(BaseModel):
    id: str
    created: int
    karma: int
    about: str | None
    submitted: List[int] | None
    stories: List[HNUserStory] | None = None


class HNSearchResult(BaseModel):
    story: HNStory
    relevance_score: float | None
    search_metadata: Dict[str, Any]


async def fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    backoff_factor: float = 0.5,
) -> dict:
    """Fetch data from URL with exponential backoff retries for transient errors."""
    retries = 0
    while retries < max_retries:
        try:
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

        delay = backoff_factor * (2**retries) * (0.5 + 0.5 * asyncio.get_event_loop().time() % 1)
        await asyncio.sleep(delay)
        retries += 1

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} retries")


async def fetch_and_parse_item(session: aiohttp.ClientSession, item_id: int) -> Optional[Union[Item, Story, Comment]]:
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

    if data.get("deleted", False) or data.get("dead", False):
        logger.debug(f"Skipping deleted or dead item {item_id}")
        return None

    try:
        item_type = data.get("type")
        if item_type == "story":
            return Story(**data)
        elif item_type == "comment":
            if not data.get("by") or not data.get("text"):
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
    session: aiohttp.ClientSession, item_ids: List[int], batch_size: int = 10
) -> List[Optional[Union[Item, Story, Comment]]]:
    """Batch fetch items with improved concurrency control and error handling."""
    if not item_ids:
        return []

    results = []
    for i in range(0, len(item_ids), batch_size):
        batch = item_ids[i : i + batch_size]
        tasks = [fetch_and_parse_item(session, item_id) for item_id in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_items = []
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Error processing item: {str(result)}")
            elif result is not None:
                valid_items.append(result)

        results.extend(valid_items)

    return results


async def fetch_comments(
    session: aiohttp.ClientSession, item: Union[Story, Comment], max_depth: int = 3, current_depth: int = 0
) -> None:
    """Recursively fetch comments with depth control to prevent excessive API calls."""
    if current_depth >= max_depth:
        if item.kids and not item.comments:
            item.comments = []
        return

    if item.kids:
        comments = await fetch_items_batch(session, item.kids)
        valid_comments = [c for c in comments if isinstance(c, Comment)]

        if current_depth < max_depth - 1:
            await asyncio.gather(
                *[fetch_comments(session, comment, max_depth, current_depth + 1) for comment in valid_comments]
            )

        item.comments = valid_comments
    else:
        item.comments = []


def clean_html(text: str) -> str:
    """
    Clean HTML content by unescaping entities, handling paragraphs, and removing tags.

    Args:
        text: HTML text to clean

    Returns:
        Plain text with HTML removed
    """
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace("<p>", "\n").replace("</p>", "")
    text = re.sub(r"<a\s+href=[^>]*>(.*?)</a>", r"\1", text)
    text = re.sub(r"<[^>]*>", "", text)
    return text.strip()


def flatten_comments(item: Union[Story, Comment], path: str = "", result: List[str] = None) -> List[str]:
    """
    Flatten a story or comment's comment hierarchy into thread path notation.

    Args:
        item: Story or Comment object to process
        path: Current thread path (e.g., "1", "1.1")
        result: Accumulator for formatted comments

    Returns:
        List of strings in thread path notation (e.g., "[1] author: text")
    """
    if result is None:
        result = []

    if path:
        text = clean_html(item.text) if isinstance(item, Comment) else item.title
        result.append(f"[{path}] {item.by}: {text}")

    for i, child in enumerate(item.comments or [], 1):
        child_path = f"{path}.{i}" if path else str(i)
        flatten_comments(child, child_path, result)

    return result


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

    async def get_stories(self, story_type: str = "top", limit: int = 30) -> List[Story]:
        """Fetch stories by type with improved error handling."""
        ENDPOINTS = {
            "top": "topstories",
            "new": "newstories",
            "best": "beststories",
            "ask": "askstories",
            "show": "showstories",
            "job": "jobstories",
        }

        if story_type not in ENDPOINTS:
            raise ValueError(f"Invalid story_type: {story_type}. Valid options: {list(ENDPOINTS.keys())}")

        try:
            story_ids = await fetch_with_retry(self.session, f"{HNConfig.BASE_URL}/{ENDPOINTS[story_type]}.json")
            items = await fetch_items_batch(self.session, story_ids[:limit])
            return [item for item in items if isinstance(item, Story)]
        except Exception as e:
            logger.error(f"Failed to fetch {story_type} stories: {str(e)}")
            raise

    async def get_story(self, story_id: int) -> Optional[Story]:
        """Fetch a single story."""
        story = await fetch_and_parse_item(self.session, story_id)
        if not isinstance(story, Story):
            return None
        return story

    async def get_comments(self, story_id: int, comment_depth: int = 2) -> List[Comment]:
        """Fetch comments for a story."""
        story = await self.get_story(story_id)
        if not story:
            return []

        await fetch_comments(self.session, story, max_depth=comment_depth)

        return story.comments or []

    async def get_story_with_comments(
        self, story_id: int, comment_depth: int = 2, clean_text: bool = False
    ) -> Optional[Story]:
        """
        Fetch a single story with nested comments.

        Args:
            story_id: ID of the story to fetch
            comment_depth: Maximum depth of nested comments (0-3)
            clean_text: If True, clean HTML from comment texts

        Returns:
            Story object with comments, or None if not found
        """
        story = await self.get_story(story_id)
        if not story:
            return None

        await fetch_comments(self.session, story, max_depth=comment_depth)

        if clean_text:

            def clean_comments(item):
                if isinstance(item, Comment):
                    item.text = clean_html(item.text)
                for comment in item.comments or []:
                    clean_comments(comment)

            clean_comments(story)

        return story

    async def get_user(self, username: str) -> Optional[User]:
        """Fetch user information."""
        try:
            user_data = await fetch_with_retry(self.session, f"{HNConfig.BASE_URL}/user/{username}.json")
            if not user_data:
                return None
            return User(**user_data)
        except Exception as e:
            logger.error(f"Failed to fetch user {username}: {str(e)}")
            return None

    async def get_user_stories(self, username: str, limit: int = 10) -> UserInfo:
        """Fetch user data with their submitted stories."""
        user = await self.get_user(username)
        if not user:
            raise ValueError(f"User {username} not found")

        story_ids = [id for id in user.submitted[: limit * 3]]
        items = await fetch_items_batch(self.session, story_ids)
        stories = [item for item in items if isinstance(item, Story)][:limit]

        return UserInfo(user=user, submitted_stories=stories)

    async def search(
        self, query: str, sort_by_date: bool = False, limit: int = 20, tags: Optional[List[str]] = None
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
                    type="story",
                )
                for hit in result.get("hits", [])
                if "objectID" in hit and "title" in hit
            ]

            return SearchResults(
                hits=stories,
                page=result.get("page", 0),
                total_hits=result.get("nbHits", 0),
                processing_time_ms=result.get("processingTimeMS", 0),
            )
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            raise


@create_tool
async def mcp_hn_get_stories(story_type: str = "top", num_stories: int = 30) -> List[HNStory]:
    """
    Fetch popular stories from Hacker News.

    Args:
        story_type: Type of stories to fetch - one of 'top', 'new', 'best', 'ask_hn', 'show_hn', or 'job'
        num_stories: Number of stories to retrieve (1-100)

    Returns:
        List of HNStory objects with title, url, score, and other metadata

    Raises:
        ValueError: If story_type is invalid or num_stories is out of range
    """
    # Map user-friendly names to API endpoints
    story_type_map = {
        "top": "top",
        "new": "new",
        "best": "best", 
        "ask_hn": "ask",
        "show_hn": "show",
        "job": "job"
    }
    
    if story_type not in story_type_map:
        raise ValueError(
            f"Invalid story_type: '{story_type}'. "
            f"Valid options: {', '.join(story_type_map.keys())}"
        )

    # Validate and constrain num_stories
    if not isinstance(num_stories, int):
        raise ValueError("num_stories must be an integer")
        
    num_stories = max(1, min(100, num_stories))

    try:
        async with HackerNewsClient() as client:
            stories = await client.get_stories(story_type_map[story_type], num_stories)
            return [HNStory(**story.dict()) for story in stories]
    except Exception as e:
        logger.error(f"Error fetching stories: {str(e)}")
        raise ValueError(f"Failed to fetch stories: {str(e)}") from e


@create_tool
async def mcp_hn_get_story_info(
    story_id: int, comment_depth: int = 2, clean_text: bool = True
) -> HNStoryDetails:
    """
    Get detailed information about a Hacker News story with its comments.

    Args:
        story_id: The ID of the story to retrieve
        comment_depth: How deep to fetch nested comments (0-3, where 0 means no comments)
        clean_text: If True, clean HTML from comment texts for better readability

    Returns:
        Story object with nested comments including title, url, author, and comment tree

    Raises:
        ValueError: If story_id is invalid or story cannot be found
    """
    # Validate inputs
    if not isinstance(story_id, int) or story_id <= 0:
        raise ValueError(f"Invalid story_id: {story_id}. Must be a positive integer.")
        
    # Constrain comment_depth to valid range
    comment_depth = max(0, min(3, comment_depth))

    try:
        async with HackerNewsClient() as client:
            story = await client.get_story(story_id)
            if not story:
                raise ValueError(f"Story with id {story_id} not found")

            story_details = HNStoryDetails(**story.dict())
            if comment_depth > 0:
                comments = await client.get_comments(story_id, comment_depth)
                if clean_text:
                    for comment in comments:
                        if comment.text:  # Check if text exists before cleaning
                            comment.text = clean_html(comment.text)
                story_details.comments = [HNComment(**comment.dict()) for comment in comments]
            return story_details
    except Exception as e:
        logger.error(f"Error fetching story {story_id}: {str(e)}")
        raise ValueError(f"Failed to fetch story: {str(e)}") from e


@create_tool
async def mcp_hn_get_flattened_comments(story_id: int, comment_depth: int = 2, clean_text: bool = False) -> List[str]:
    """
    Get comments for a story in flattened thread path notation.

    Args:
        story_id: The ID of the story to retrieve comments for
        comment_depth: How deep to fetch nested comments (0-3, where 0 means no comments)
        clean_text: If True, clean HTML from comment texts

    Returns:
        List of flattened comment strings
    """
    comment_depth = max(0, min(3, comment_depth))

    async with HackerNewsClient() as client:
        comments = await client.get_comments(story_id, comment_depth)
        if clean_text:
            return [clean_html(comment.text) for comment in comments]
        return [comment.text for comment in comments]


@create_tool
async def mcp_hn_get_user_info(username: str, num_stories: int = 10) -> HNUser:
    """
    Get information about a Hacker News user and their recent submissions.

    Args:
        username: The username to look up (case-sensitive)
        num_stories: Number of user's stories to retrieve (1-50)

    Returns:
        User information including karma, creation date, about text, and recent submissions

    Raises:
        ValueError: If username is invalid or user cannot be found
    """
    # Validate inputs
    if not username or not isinstance(username, str):
        raise ValueError("Username must be a non-empty string")
        
    # Constrain num_stories to valid range
    num_stories = max(1, min(50, num_stories))

    try:
        async with HackerNewsClient() as client:
            user_info = await client.get_user_stories(username, num_stories)
            if not user_info or not user_info.user:
                raise ValueError(f"User '{username}' not found")
            return HNUser(**user_info.dict())
    except Exception as e:
        logger.error(f"Error fetching user info for {username}: {str(e)}")
        raise ValueError(f"Failed to fetch user info: {str(e)}") from e


@create_tool
async def mcp_hn_search_stories(
    query: str, 
    search_by_date: bool = False, 
    num_results: int = 20, 
    content_type: str = "all"
) -> List[HNSearchResult]:
    """
    Search for Hacker News stories using keywords.

    Args:
        query: Search query string (use simple terms for better results)
        search_by_date: When True, sort by newest first; when False, sort by relevance
        num_results: Number of results to return (1-100)
        content_type: Filter by content type: 'all', 'story', 'comment', 'ask_hn', 'show_hn', 'poll'

    Returns:
        List of search results with stories matching the query, including relevance scores

    Raises:
        ValueError: If query is empty or invalid parameters are provided
    """
    # Validate inputs
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")
        
    # Constrain num_results to valid range
    num_results = max(1, min(100, num_results))
    
    # Map user-friendly content types to API tags
    content_type_map = {
        "all": None,
        "story": ["story"],
        "comment": ["comment"],
        "ask_hn": ["ask_hn"],
        "show_hn": ["show_hn"],
        "poll": ["poll"]
    }
    
    if content_type not in content_type_map:
        raise ValueError(
            f"Invalid content_type: '{content_type}'. "
            f"Valid options: {', '.join(content_type_map.keys())}"
        )
    
    filter_tags = content_type_map[content_type]

    try:
        async with HackerNewsClient() as client:
            search_results = await client.search(query, sort_by_date=search_by_date, limit=num_results, tags=filter_tags)
            
            processed_results = []
            for result in search_results:
                try:
                    # Handle string responses by attempting JSON parsing
                    if isinstance(result, str):
                        try:
                            result = json.loads(result)
                        except json.JSONDecodeError:
                            continue
                            
                    # Handle different response formats
                    if isinstance(result, dict):
                        story_data = result.get('story', {})
                        relevance = result.get('relevance_score')
                        metadata = result.get('metadata', {})
                    elif hasattr(result, 'story'):
                        story_data = result.story
                        relevance = getattr(result, 'relevance_score', None)
                        metadata = getattr(result, 'metadata', {})
                    elif isinstance(result, (tuple, list)) and len(result) > 0:
                        story_data = result[0] if len(result) > 0 else {}
                        relevance = result[1] if len(result) > 1 else None
                        metadata = result[2] if len(result) > 2 else {}
                    else:
                        continue
                        
                    # Ensure story_data is a dictionary or object with dict() method
                    if hasattr(story_data, 'dict'):
                        story_dict = story_data.dict()
                    elif isinstance(story_data, dict):
                        story_dict = story_data
                    else:
                        continue
                        
                    processed_results.append(
                        HNSearchResult(
                            story=HNStory(**story_dict),
                            relevance_score=relevance,
                            search_metadata=metadata,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Skipping malformed search result: {str(e)}")
                    continue
                    
            return processed_results
    except Exception as e:
        logger.error(f"Error searching stories: {str(e)}")
        raise ValueError(f"Failed to search stories: {str(e)}") from e


async def main() -> None:
    """Test function demonstrating HackerNewsClient usage."""
    logging.basicConfig(level=logging.INFO)

    try:
        async with HackerNewsClient() as client:
            print("=== Testing get_stories ===")
            stories = await client.get_stories("top", 5)
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
