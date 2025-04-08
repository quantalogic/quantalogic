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
    Fetch popular stories from Hacker News to monitor tech trends and industry discussions.

    Args:
        story_type: Type of stories to fetch - one of 'top', 'new', 'best', 'ask_hn', 'show_hn', or 'job'
        num_stories: Number of stories to retrieve (1-100)

    Returns:
        List of HNStory objects with title, url, score, and other metadata

    Examples:
        >>> # Get top trending stories on Hacker News
        >>> top_stories = mcp_hn_get_stories("top", 10)
        >>> 
        >>> # Get latest job postings
        >>> job_posts = mcp_hn_get_stories("job", 20)

    Business Use Cases:
        - Daily tech briefing: Monitor trending topics in technology
        - Recruitment: Track job postings and hiring trends
        - Product feedback: Find discussions about your product or similar products
        - Market intelligence: Identify emerging technologies and tools

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
    Get detailed information about a Hacker News story with its comments for in-depth analysis.

    Args:
        story_id: The ID of the story to retrieve
        comment_depth: How deep to fetch nested comments (0-3, where 0 means no comments)
        clean_text: If True, clean HTML from comment texts for better readability

    Returns:
        Story object with nested comments including title, url, author, and comment tree

    Examples:
        >>> # Get a story with its comments
        >>> story_details = mcp_hn_get_story_info(36123456)
        >>> 
        >>> # Get only the story without comments
        >>> story_only = mcp_hn_get_story_info(36123456, comment_depth=0)

    Business Use Cases:
        - Customer feedback: Analyze comments on stories about your product
        - Sentiment analysis: Gauge community reaction to industry news
        - Competitive analysis: Study discussions about competitors
        - Expert insights: Identify domain experts and their perspectives

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
    Get information about a Hacker News user and their recent submissions for talent scouting or expert identification.

    Args:
        username: The username to look up (case-sensitive)
        num_stories: Number of user's stories to retrieve (1-50)

    Returns:
        User information including karma, creation date, about text, and recent submissions

    Examples:
        >>> # Look up a specific user's profile and recent submissions
        >>> user_info = mcp_hn_get_user_info("patio11", num_stories=15)

    Business Use Cases:
        - Talent scouting: Identify potential hires based on expertise and contributions
        - Expert identification: Find thought leaders in specific domains
        - Influencer research: Discover influential voices in the tech community
        - Content curation: Find quality content from specific authors

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
    Search for Hacker News stories using keywords to discover industry trends, competitor news, or market insights.

    Args:
        query: Search query string (e.g., "AI startups", "blockchain finance", "remote work")
        search_by_date: When True, sort by newest first; when False, sort by relevance
        num_results: Number of results to return (1-100)
        content_type: Filter by content type: 'all', 'story', 'comment', 'ask_hn', 'show_hn', 'poll'

    Returns:
        List of search results with stories matching the query, including relevance scores

    Examples:
        >>> # Find recent discussions about AI startups
        >>> results = mcp_hn_search_stories("AI startups", search_by_date=True)
        >>> 
        >>> # Find most relevant discussions about remote work
        >>> results = mcp_hn_search_stories("remote work productivity", content_type="story")

    Business Use Cases:
        - Competitive intelligence: Track mentions of competitors or industry trends
        - Market research: Identify emerging technologies or business models
        - Content inspiration: Find popular topics for blog posts or newsletters
        - Recruitment insights: Discover what developers are discussing about workplace trends

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


# New business-focused tools

class TrendAnalysisResult(BaseModel):
    """Results of a trend analysis on Hacker News stories."""
    query: str
    total_stories: int
    time_period: str
    top_keywords: List[Dict[str, Any]]
    sentiment_summary: Dict[str, float]
    popularity_trend: Dict[str, int]
    related_topics: List[str]


class ExpertResult(BaseModel):
    """Information about an expert identified on Hacker News."""
    username: str
    karma: int
    expertise_areas: List[str]
    notable_contributions: List[Dict[str, Any]]
    engagement_metrics: Dict[str, float]


@create_tool
async def mcp_hn_analyze_trends(
    query: str,
    time_period: str = "month",
    min_points: int = 10,
    max_results: int = 50
) -> TrendAnalysisResult:
    """
    Analyze trends on Hacker News related to a specific topic or industry.
    
    Args:
        query: Topic to analyze (e.g., "AI", "remote work", "fintech")
        time_period: Time period for analysis ("week", "month", "quarter", "year")
        min_points: Minimum points for stories to include in analysis
        max_results: Maximum number of stories to analyze
        
    Returns:
        Trend analysis results including popularity trends, sentiment, and related topics
        
    Examples:
        >>> # Analyze AI trends over the past month
        >>> ai_trends = mcp_hn_analyze_trends("artificial intelligence", time_period="month")
        >>> 
        >>> # Analyze remote work discussions with higher relevance threshold
        >>> remote_work = mcp_hn_analyze_trends("remote work", min_points=30)
        
    Business Use Cases:
        - Market research: Track emerging trends in your industry
        - Product planning: Identify pain points and opportunities
        - Content strategy: Discover trending topics for content creation
        - Competitive intelligence: Monitor discussions about competitors
    """
    # This is a placeholder implementation
    # In a real implementation, this would analyze trends by:
    # 1. Searching for stories matching the query
    # 2. Analyzing comment sentiment
    # 3. Extracting keywords and topics
    # 4. Tracking popularity over time
    
    try:
        # Use the existing search functionality as a starting point
        async with HackerNewsClient() as client:
            # Convert time period to search parameters
            sort_by_date = True  # For trend analysis, recent stories are more relevant
            
            # Search for stories related to the query
            search_results = await client.search(query, sort_by_date=sort_by_date, limit=max_results)
            
            # This is where you would implement the actual trend analysis
            # For now, return a placeholder result
            return TrendAnalysisResult(
                query=query,
                total_stories=len(search_results.hits) if hasattr(search_results, 'hits') else 0,
                time_period=time_period,
                top_keywords=[{"keyword": "example", "frequency": 10}],
                sentiment_summary={"positive": 0.6, "neutral": 0.3, "negative": 0.1},
                popularity_trend={"week1": 10, "week2": 15, "week3": 20, "week4": 25},
                related_topics=["related_topic_1", "related_topic_2"]
            )
    except Exception as e:
        logger.error(f"Error analyzing trends: {str(e)}")
        raise ValueError(f"Failed to analyze trends: {str(e)}") from e


@create_tool
async def mcp_hn_find_experts(
    topic: str,
    min_karma: int = 500,
    max_experts: int = 10
) -> List[ExpertResult]:
    """
    Find domain experts on Hacker News based on their contributions to specific topics.
    
    Args:
        topic: Area of expertise to search for (e.g., "machine learning", "startup", "cybersecurity")
        min_karma: Minimum karma threshold for experts
        max_experts: Maximum number of experts to return
        
    Returns:
        List of experts with their karma, expertise areas, and notable contributions
        
    Examples:
        >>> # Find machine learning experts
        >>> ml_experts = mcp_hn_find_experts("machine learning", min_karma=1000)
        >>> 
        >>> # Find startup experts with lower karma threshold
        >>> startup_experts = mcp_hn_find_experts("startup", min_karma=200)
        
    Business Use Cases:
        - Recruitment: Identify potential technical hires
        - Advisory: Find domain experts for consulting
        - Networking: Connect with thought leaders in your industry
        - Research: Identify experts for interviews or collaborations
    """
    # This is a placeholder implementation
    # In a real implementation, this would:
    # 1. Search for stories and comments related to the topic
    # 2. Identify users who contribute high-quality content
    # 3. Analyze their karma, posting history, and expertise
    # 4. Rank experts based on relevance and influence
    
    try:
        # In a real implementation, we would use HackerNewsClient to search for experts
        # But for now, we'll just return a placeholder result to avoid unused variables
        
        # This is where you would implement the actual expert finding logic using the client
        return [
            ExpertResult(
                username="expert_user_1",
                karma=1500,
                expertise_areas=[topic, "related_area_1"],
                notable_contributions=[{"title": "Example Contribution", "points": 100}],
                engagement_metrics={"avg_comments": 10.5, "quality_score": 0.85}
            )
        ]
    except Exception as e:
        logger.error(f"Error finding experts: {str(e)}")
        raise ValueError(f"Failed to find experts: {str(e)}") from e


@create_tool
async def mcp_hn_monitor_competitors(
    company_names: List[str],
    include_related: bool = True,
    days_back: int = 30,
    min_points: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Monitor mentions and discussions about competitors on Hacker News.
    
    Args:
        company_names: List of competitor company names to monitor
        include_related: Whether to include related products and technologies
        days_back: Number of days to look back for mentions
        min_points: Minimum points threshold for stories to include
        
    Returns:
        Dictionary mapping each competitor to a list of relevant stories and discussions
        
    Examples:
        >>> # Monitor mentions of major cloud providers
        >>> cloud_mentions = mcp_hn_monitor_competitors(["AWS", "Google Cloud", "Azure"])
        >>> 
        >>> # Monitor database companies with lower threshold
        >>> db_mentions = mcp_hn_monitor_competitors(["MongoDB", "PostgreSQL"], min_points=2)
        
    Business Use Cases:
        - Competitive intelligence: Track how competitors are perceived
        - Product comparison: Identify strengths and weaknesses vs competitors
        - Market positioning: Understand how your market space is discussed
        - Crisis monitoring: Detect negative publicity about competitors
    """
    # This is a placeholder implementation
    # In a real implementation, this would:
    # 1. Search for stories mentioning each competitor
    # 2. Analyze sentiment and context of mentions
    # 3. Track changes in perception over time
    # 4. Identify related products and technologies
    
    try:
        results = {}
        async with HackerNewsClient() as client:
            for company in company_names:
                # Search for stories mentioning this company
                search_results = await client.search(company, sort_by_date=True, limit=20)
                
                # Process and filter results
                company_mentions = []
                for hit in search_results.hits if hasattr(search_results, 'hits') else []:
                    if hit.score >= min_points:
                        company_mentions.append({
                            "id": hit.id,
                            "title": hit.title,
                            "url": hit.url,
                            "points": hit.score,
                            "comments": hit.descendants if hasattr(hit, 'descendants') else 0,
                        })
                
                results[company] = company_mentions
            
            return results
    except Exception as e:
        logger.error(f"Error monitoring competitors: {str(e)}")
        raise ValueError(f"Failed to monitor competitors: {str(e)}") from e


class ContentInspirationResult(BaseModel):
    """Results of content inspiration analysis from Hacker News."""
    topic: str
    popular_stories: List[Dict[str, Any]]
    discussion_themes: List[str]
    content_gaps: List[str]
    audience_interests: Dict[str, float]
    recommended_angles: List[str]


@create_tool
async def mcp_hn_content_inspiration(
    industry: str,
    content_type: str = "blog",
    audience_level: str = "technical",
    max_results: int = 20
) -> ContentInspirationResult:
    """
    Generate content ideas and inspiration based on popular Hacker News discussions.
    
    Args:
        industry: Industry or topic area (e.g., "fintech", "cybersecurity", "remote work")
        content_type: Type of content to generate ideas for ("blog", "newsletter", "social", "whitepaper")
        audience_level: Target audience technical level ("technical", "business", "general")
        max_results: Maximum number of stories to analyze
        
    Returns:
        Content inspiration results including popular stories, themes, and recommended angles
        
    Examples:
        >>> # Get content ideas for a technical blog on AI
        >>> ai_content = mcp_hn_content_inspiration("artificial intelligence", "blog", "technical")
        >>> 
        >>> # Get newsletter content ideas for business audience in fintech
        >>> fintech_content = mcp_hn_content_inspiration("fintech", "newsletter", "business")
        
    Business Use Cases:
        - Content marketing: Generate ideas for blog posts, newsletters, and social media
        - Thought leadership: Identify trending topics to establish expertise
        - SEO strategy: Discover high-interest topics for content creation
        - Audience engagement: Align content with audience interests
    """
    # This is a placeholder implementation
    # In a real implementation, this would:
    # 1. Search for popular stories in the industry
    # 2. Analyze common themes and discussion points
    # 3. Identify content gaps and opportunities
    # 4. Generate content recommendations based on audience level
    
    try:
        async with HackerNewsClient() as client:
            # Search for stories related to the industry
            search_results = await client.search(industry, limit=max_results)
            
            # Process stories to extract themes and content ideas
            popular_stories = []
            if hasattr(search_results, 'hits'):
                for hit in search_results.hits[:5]:  # Just use top 5 for the example
                    popular_stories.append({
                        "title": hit.title,
                        "url": hit.url,
                        "points": hit.score,
                        "comments": hit.descendants if hasattr(hit, 'descendants') else 0,
                    })
            
            # Generate placeholder content inspiration
            # In a real implementation, this would analyze the content and discussions
            return ContentInspirationResult(
                topic=industry,
                popular_stories=popular_stories,
                discussion_themes=[f"{industry} trend 1", f"{industry} trend 2"],
                content_gaps=[f"Gap in {industry} coverage", "Underserved audience need"],
                audience_interests={
                    "primary_interest": 0.8,
                    "secondary_interest": 0.5,
                    "tertiary_interest": 0.3
                },
                recommended_angles=[
                    f"How {industry} is changing in 2025",
                    f"Top 5 {industry} tools for {audience_level} users",
                    f"The future of {industry}: trends and predictions"
                ]
            )
    except Exception as e:
        logger.error(f"Error generating content inspiration: {str(e)}")
        raise ValueError(f"Failed to generate content inspiration: {str(e)}") from e


# Helper functions for common business use cases

async def analyze_tech_landscape(keywords: List[str], min_points: int = 10) -> Dict[str, Any]:
    """
    Analyze the technology landscape by combining multiple Hacker News tools.
    
    This helper function demonstrates how to combine multiple tools for a comprehensive analysis.
    
    Args:
        keywords: List of technology keywords to analyze
        min_points: Minimum points threshold for stories to include
        
    Returns:
        Comprehensive analysis of the technology landscape
    """
    results = {}
    
    # Get trending stories for each keyword
    for keyword in keywords:
        try:
            # Get trending stories
            stories = await mcp_hn_search_stories(keyword, num_results=10)
            
            # Get trend analysis
            trends = await mcp_hn_analyze_trends(keyword, min_points=min_points)
            
            # Get content inspiration
            content_ideas = await mcp_hn_content_inspiration(keyword)
            
            # Combine results
            results[keyword] = {
                "top_stories": stories[:3] if stories else [],
                "trend_analysis": trends,
                "content_ideas": content_ideas.recommended_angles[:3] if content_ideas else []
            }
        except Exception as e:
            logger.error(f"Error analyzing {keyword}: {str(e)}")
            results[keyword] = {"error": str(e)}
    
    return results


async def find_business_opportunities(industry: str, competitors: List[str]) -> Dict[str, Any]:
    """
    Find business opportunities by analyzing an industry and its competitors.
    
    This helper function demonstrates how to use multiple tools together for business intelligence.
    
    Args:
        industry: Industry to analyze
        competitors: List of competitors to monitor
        
    Returns:
        Business opportunities analysis
    """
    try:
        # Analyze industry trends
        trends = await mcp_hn_analyze_trends(industry)
        
        # Monitor competitors
        competitor_mentions = await mcp_hn_monitor_competitors(competitors)
        
        # Generate content ideas
        content_ideas = await mcp_hn_content_inspiration(industry, audience_level="business")
        
        # Combine results into a business opportunities report
        return {
            "industry_trends": {
                "top_keywords": trends.top_keywords if trends else [],
                "popularity_trend": trends.popularity_trend if trends else {},
                "sentiment": trends.sentiment_summary if trends else {}
            },
            "competitor_analysis": competitor_mentions,
            "content_opportunities": {
                "gaps": content_ideas.content_gaps if content_ideas else [],
                "recommended_angles": content_ideas.recommended_angles if content_ideas else []
            },
            "potential_opportunities": [
                f"Gap in {industry} market based on discussion trends",
                f"Underserved audience needs in {industry}",
                f"Emerging technology application in {industry}"
            ]
        }
    except Exception as e:
        logger.error(f"Error finding business opportunities: {str(e)}")
        return {"error": str(e)}


# Batch versions of tool methods with pagination

class PaginatedResult(BaseModel):
    """Base class for paginated results."""
    items: List[Any]
    page: int
    total_pages: int
    total_items: int
    has_next: bool
    has_prev: bool


class BatchConfig(BaseModel):
    """Configuration for batch operations."""
    batch_size: int = Field(default=10, description="Number of items per batch")
    max_batches: int = Field(default=10, description="Maximum number of batches to process")
    parallel_requests: int = Field(default=5, description="Number of parallel requests")


@create_tool
async def mcp_hn_batch_search_stories(
    queries: List[str],
    search_by_date: bool = False,
    items_per_page: int = 20,
    page: int = 0,
    content_type: str = "all",
    batch_config: Optional[BatchConfig] = None
) -> Dict[str, List[HNSearchResult]]:
    """
    Search for multiple queries on Hacker News with pagination support.
    
    Args:
        queries: List of search queries to process in batch
        search_by_date: When True, sort by newest first; when False, sort by relevance
        items_per_page: Number of items per page
        page: Page number to retrieve (0-indexed)
        content_type: Filter by content type: 'all', 'story', 'comment', 'ask_hn', 'show_hn', 'poll'
        batch_config: Optional batch processing configuration
        
    Returns:
        Dictionary mapping each query to its search results
        
    Examples:
        >>> # Search for multiple technology topics
        >>> results = mcp_hn_batch_search_stories(["AI", "blockchain", "quantum computing"])
        >>> 
        >>> # Get page 2 of results with custom page size
        >>> page2 = mcp_hn_batch_search_stories(["remote work", "fintech"], page=1, items_per_page=15)
        
    Business Use Cases:
        - Competitive analysis: Compare mentions of multiple competitors
        - Market research: Track multiple industry trends simultaneously
        - Content planning: Research multiple topics for content creation
        - Investment research: Track multiple technology sectors
    """
    # Set up batch configuration
    if batch_config is None:
        batch_config = BatchConfig()
    
    # Validate inputs
    if not queries:
        raise ValueError("Must provide at least one query")
    
    # Constrain items_per_page to valid range
    items_per_page = max(1, min(100, items_per_page))
    
    # Process queries in parallel with rate limiting
    results = {}
    semaphore = asyncio.Semaphore(batch_config.parallel_requests)
    
    async def process_query(query):
        async with semaphore:
            try:
                return query, await mcp_hn_search_stories(
                    query=query,
                    search_by_date=search_by_date,
                    num_results=items_per_page,
                    content_type=content_type
                )
            except Exception as e:
                logger.error(f"Error processing query '{query}': {str(e)}")
                return query, []
    
    # Create tasks for all queries
    tasks = [process_query(query) for query in queries]
    
    # Wait for all tasks to complete
    for task in asyncio.as_completed(tasks):
        query, query_results = await task
        results[query] = query_results
    
    return results


@create_tool
async def mcp_hn_get_stories_paginated(
    story_type: str = "top",
    items_per_page: int = 10,
    page: int = 0,
    include_comments: bool = False,
    comment_depth: int = 1
) -> PaginatedResult:
    """
    Fetch popular stories from Hacker News with pagination support.
    
    Args:
        story_type: Type of stories to fetch - one of 'top', 'new', 'best', 'ask_hn', 'show_hn', or 'job'
        items_per_page: Number of items per page
        page: Page number to retrieve (0-indexed)
        include_comments: Whether to include comments with stories
        comment_depth: How deep to fetch nested comments if include_comments is True
        
    Returns:
        Paginated result with stories and pagination metadata
        
    Examples:
        >>> # Get first page of top stories
        >>> page1 = mcp_hn_get_stories_paginated("top", items_per_page=10, page=0)
        >>> 
        >>> # Get second page of job postings
        >>> page2 = mcp_hn_get_stories_paginated("job", items_per_page=5, page=1)
        
    Business Use Cases:
        - Daily briefing: Review top tech news in manageable batches
        - Content curation: Select relevant stories for newsletters or digests
        - Trend monitoring: Track emerging topics across multiple pages
        - Recruitment: Browse job postings efficiently
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

    # Validate and constrain parameters
    items_per_page = max(1, min(100, items_per_page))
    page = max(0, page)

    try:
        async with HackerNewsClient() as client:
            # Get all story IDs first
            all_stories = await client.get_stories(story_type_map[story_type], 500)  # Get a large batch
            
            # Calculate pagination
            total_items = len(all_stories)
            total_pages = (total_items + items_per_page - 1) // items_per_page
            
            # Get the requested page
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            
            # Slice the stories for the current page
            page_stories = all_stories[start_idx:end_idx]
            
            # Process the stories for this page
            processed_stories = []
            for story in page_stories:
                story_obj = HNStory(**story.dict())
                
                # Fetch comments if requested
                if include_comments and comment_depth > 0:
                    try:
                        story_with_comments = await client.get_story_with_comments(
                            story.id, comment_depth=comment_depth
                        )
                        if story_with_comments and story_with_comments.comments:
                            story_obj.comments = [
                                HNComment(**comment.dict()) 
                                for comment in story_with_comments.comments
                            ]
                    except Exception as e:
                        logger.debug(f"Error fetching comments for story {story.id}: {str(e)}")
                
                processed_stories.append(story_obj)
            
            # Create the paginated result
            return PaginatedResult(
                items=processed_stories,
                page=page,
                total_pages=total_pages,
                total_items=total_items,
                has_next=(page < total_pages - 1),
                has_prev=(page > 0)
            )
    except Exception as e:
        logger.error(f"Error fetching paginated stories: {str(e)}")
        raise ValueError(f"Failed to fetch paginated stories: {str(e)}") from e


@create_tool
async def mcp_hn_batch_monitor_competitors(
    company_groups: Dict[str, List[str]],
    days_back: int = 30,
    min_points: int = 5,
    items_per_page: int = 10,
    page: int = 0
) -> Dict[str, PaginatedResult]:
    """
    Monitor mentions of multiple competitor groups on Hacker News with pagination.
    
    Args:
        company_groups: Dictionary mapping group names to lists of company names
        days_back: Number of days to look back for mentions
        min_points: Minimum points threshold for stories to include
        items_per_page: Number of items per page
        page: Page number to retrieve (0-indexed)
        
    Returns:
        Dictionary mapping each group to paginated results
        
    Examples:
        >>> # Monitor cloud providers and database companies
        >>> groups = {
        >>>     "cloud": ["AWS", "Google Cloud", "Azure"],
        >>>     "database": ["MongoDB", "PostgreSQL", "MySQL"]
        >>> }
        >>> results = mcp_hn_batch_monitor_competitors(groups)
        
    Business Use Cases:
        - Competitive intelligence: Track multiple competitor groups
        - Market analysis: Compare different market segments
        - Strategic planning: Monitor multiple business areas
        - Investment research: Track multiple sectors
    """
    # Validate inputs
    if not company_groups:
        raise ValueError("Must provide at least one company group")
    
    # Constrain parameters
    items_per_page = max(1, min(100, items_per_page))
    page = max(0, page)
    
    results = {}
    for group_name, companies in company_groups.items():
        try:
            # Get mentions for each company in the group
            group_mentions = []
            async with HackerNewsClient() as client:
                for company in companies:
                    # Search for stories mentioning this company
                    search_results = await client.search(company, sort_by_date=True, limit=100)
                    
                    # Process and filter results
                    if hasattr(search_results, 'hits'):
                        for hit in search_results.hits:
                            if hit.score >= min_points:
                                group_mentions.append({
                                    "company": company,
                                    "id": hit.id,
                                    "title": hit.title,
                                    "url": hit.url,
                                    "points": hit.score,
                                    "comments": hit.descendants if hasattr(hit, 'descendants') else 0,
                                })
            
            # Sort by points (descending)
            group_mentions.sort(key=lambda x: x["points"], reverse=True)
            
            # Calculate pagination
            total_items = len(group_mentions)
            total_pages = (total_items + items_per_page - 1) // items_per_page
            
            # Get the requested page
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            
            # Create paginated result
            results[group_name] = PaginatedResult(
                items=group_mentions[start_idx:end_idx],
                page=page,
                total_pages=total_pages,
                total_items=total_items,
                has_next=(page < total_pages - 1),
                has_prev=(page > 0)
            )
        except Exception as e:
            logger.error(f"Error monitoring group '{group_name}': {str(e)}")
            results[group_name] = PaginatedResult(
                items=[],
                page=page,
                total_pages=0,
                total_items=0,
                has_next=False,
                has_prev=False
            )
    
    return results


@create_tool
async def mcp_hn_batch_analyze_trends(
    topics: List[str],
    time_period: str = "month",
    min_points: int = 10,
    batch_config: Optional[BatchConfig] = None
) -> Dict[str, TrendAnalysisResult]:
    """
    Analyze trends for multiple topics on Hacker News in batch.
    
    Args:
        topics: List of topics to analyze in batch
        time_period: Time period for analysis ("week", "month", "quarter", "year")
        min_points: Minimum points for stories to include in analysis
        batch_config: Optional batch processing configuration
        
    Returns:
        Dictionary mapping each topic to its trend analysis results
        
    Examples:
        >>> # Analyze trends for multiple technology areas
        >>> trends = mcp_hn_batch_analyze_trends(["AI", "blockchain", "quantum computing"])
        >>> 
        >>> # Analyze with custom batch configuration
        >>> config = BatchConfig(batch_size=5, parallel_requests=3)
        >>> trends = mcp_hn_batch_analyze_trends(["remote work", "fintech"], batch_config=config)
        
    Business Use Cases:
        - Market research: Compare trends across multiple sectors
        - Strategic planning: Identify fastest growing technology areas
        - Content strategy: Plan content across multiple topics
        - Investment research: Compare momentum across sectors
    """
    # Set up batch configuration
    if batch_config is None:
        batch_config = BatchConfig()
    
    # Validate inputs
    if not topics:
        raise ValueError("Must provide at least one topic")
    
    # Process topics in parallel with rate limiting
    results = {}
    semaphore = asyncio.Semaphore(batch_config.parallel_requests)
    
    async def process_topic(topic):
        async with semaphore:
            try:
                return topic, await mcp_hn_analyze_trends(
                    query=topic,
                    time_period=time_period,
                    min_points=min_points
                )
            except Exception as e:
                logger.error(f"Error analyzing topic '{topic}': {str(e)}")
                # Return a placeholder result for failed topics
                return topic, TrendAnalysisResult(
                    query=topic,
                    total_stories=0,
                    time_period=time_period,
                    top_keywords=[],
                    sentiment_summary={"error": 1.0},
                    popularity_trend={},
                    related_topics=[]
                )
    
    # Create tasks for all topics
    tasks = [process_topic(topic) for topic in topics]
    
    # Wait for all tasks to complete
    for task in asyncio.as_completed(tasks):
        topic, topic_results = await task
        results[topic] = topic_results
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
