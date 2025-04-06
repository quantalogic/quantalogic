import asyncio
from typing import List, Optional, Union

import aiohttp
from pydantic import BaseModel, ValidationError

from quantalogic.tools import create_tool


# Pydantic Models for data validation and structure
class Item(BaseModel):
    id: int
    by: str
    time: int
    kids: Optional[List[int]] = None
    type: str
    comments: Optional[List['Comment']] = None  # Forward reference for recursive comments

class Story(Item):
    title: str
    url: Optional[str] = None
    score: int

class Comment(Item):
    text: str

class User(BaseModel):
    id: str  # username
    created: int
    karma: int
    about: Optional[str] = None
    submitted: List[int]

class UserInfo(BaseModel):
    user: User
    submitted_stories: List[Story]


# Helper function to fetch and parse an item
async def fetch_and_parse_item(session: aiohttp.ClientSession, item_id: int) -> Optional[Union[Item, Story, Comment]]:
    """Fetch and parse a Hacker News item from the API.
    
    Args:
        session: aiohttp ClientSession for making HTTP requests
        item_id: ID of the Hacker News item to fetch
        
    Returns:
        Parsed Item, Story, or Comment object, or None if comment is invalid/deleted
        
    Raises:
        RuntimeError: If HTTP request fails
        ValueError: If item data is invalid
    """
    url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    async with session.get(url) as response:
        if response.status != 200:
            raise RuntimeError(f"Failed to fetch item {item_id}")
        data = await response.json()
        try:
            if data.get('type') == 'story':
                return Story(**data)
            elif data.get('type') == 'comment':
                if data.get('deleted') or not data.get('by') or not data.get('text'):
                    return None  # Skip deleted or invalid comments
                return Comment(**data)
            return Item(**data)
        except ValidationError as e:
            raise ValueError(f"Invalid item data for ID {item_id}: {e}")


# Helper function to fetch multiple items in batch
async def fetch_items_batch(session: aiohttp.ClientSession, item_ids: List[int]) -> List[Optional[Union[Item, Story, Comment]]]:
    """Fetch multiple Hacker News items concurrently in a batch.
    
    Args:
        session: aiohttp ClientSession for making HTTP requests
        item_ids: List of item IDs to fetch
        
    Returns:
        List of parsed Item, Story, or Comment objects (or None for invalid items)
    """
    tasks = [fetch_and_parse_item(session, item_id) for item_id in item_ids]
    return await asyncio.gather(*tasks, return_exceptions=True)


# Helper function to recursively fetch comments
async def fetch_comments(session: aiohttp.ClientSession, item: Union[Story, Comment]) -> None:
    """Recursively fetch comments for a Hacker News item.
    
    Args:
        session: aiohttp ClientSession for making HTTP requests
        item: Story or Comment object to fetch comments for
        
    Modifies:
        The item object in-place by adding fetched comments to its 'comments' attribute
    """
    if item.kids:
        comment_ids = item.kids
        comments = await fetch_items_batch(session, comment_ids)
        comments = [c for c in comments if c is not None and not isinstance(c, Exception)]
        for comment in comments:
            await fetch_comments(session, comment)
        item.comments = comments
    else:
        item.comments = []


@create_tool
async def mcp_hn_get_stories(story_type: str, num_stories: int) -> List[Story]:
    """Fetch stories from Hacker News by type.
    
    Args:
        story_type: Type of stories to fetch ('top', 'new', 'ask_hn', 'show_hn')
        num_stories: Maximum number of stories to return
        
    Returns:
        List of Story objects
        
    Raises:
        ValueError: If story_type is invalid
        RuntimeError: If HTTP request fails
    """
    story_type_endpoints = {
        'top': 'topstories',
        'new': 'newstories',
        'ask_hn': 'askstories',
        'show_hn': 'showstories',
    }
    if story_type not in story_type_endpoints:
        raise ValueError(f"Invalid story_type: {story_type}. Valid options are {list(story_type_endpoints.keys())}")
    
    async with aiohttp.ClientSession() as session:
        url = f"https://hacker-news.firebaseio.com/v0/{story_type_endpoints[story_type]}.json"
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError("Failed to fetch story IDs")
            story_ids = await response.json()
        
        story_ids = story_ids[:num_stories]
        
        # Fetch stories in batch using the new helper function
        stories = await fetch_items_batch(session, story_ids)
        # Filter out exceptions and non-Story items
        return [story for story in stories if isinstance(story, Story) and not isinstance(story, Exception)]


@create_tool
async def mcp_hn_get_story_info(story_ids: List[int], page: int = 1, per_page: int = 10) -> List[Story]:
    """Fetch detailed information about multiple Hacker News stories including comments, with pagination.
    
    Args:
        story_ids: List of story IDs to fetch
        page: Page number to retrieve (1-based indexing)
        per_page: Number of stories per page
        
    Returns:
        List of Story objects with populated comments
        
    Raises:
        ValueError: If no valid stories are found in the requested page or if parameters are invalid
        RuntimeError: If HTTP request fails
    """
    if not story_ids:
        raise ValueError("story_ids list cannot be empty")
    if page < 1 or per_page < 1:
        raise ValueError("page and per_page must be positive integers")

    # Calculate pagination boundaries
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_ids = story_ids[start_idx:end_idx]

    if not paginated_ids:
        raise ValueError(f"No stories available for page {page} with {per_page} items per page")

    async with aiohttp.ClientSession() as session:
        # Fetch stories in batch
        items = await fetch_items_batch(session, paginated_ids)
        stories = [item for item in items if isinstance(item, Story) and not isinstance(item, Exception)]

        if not stories:
            raise ValueError(f"No valid stories found for the provided IDs on page {page}")

        # Fetch comments for all stories concurrently
        await asyncio.gather(*[fetch_comments(session, story) for story in stories])
        return stories


@create_tool
async def mcp_hn_get_user_info(user_name: str, num_stories: int) -> UserInfo:
    """Fetch information about a Hacker News user and their submitted stories.
    
    Args:
        user_name: Username to look up
        num_stories: Maximum number of stories to return
        
    Returns:
        UserInfo object containing user details and submitted stories
        
    Raises:
        ValueError: If user not found or data is invalid
        RuntimeError: If HTTP request fails
    """
    async with aiohttp.ClientSession() as session:
        url = f"https://hacker-news.firebaseio.com/v0/user/{user_name}.json"
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError(f"User '{user_name}' not found")
            user_data = await response.json()
            try:
                user = User(**user_data)
            except ValidationError as e:
                raise ValueError(f"Invalid user data for '{user_name}': {e}")
        
        submitted_ids = user.submitted if user.submitted else []
        submitted_ids = submitted_ids[:num_stories]  # Limit to requested number
        
        # Fetch submitted items in batch
        items = await fetch_items_batch(session, submitted_ids)
        # Filter for valid stories only
        stories = [item for item in items if isinstance(item, Story) and not isinstance(item, Exception)]
        
        return UserInfo(user=user, submitted_stories=stories)


@create_tool
async def mcp_hn_search_stories(query: str, search_by_date: bool, num_results: int) -> List[Story]:
    """Search Hacker News stories using Algolia API.
    
    Args:
        query: Search query string
        search_by_date: If True, sort by date; otherwise sort by relevance
        num_results: Maximum number of results to return
        
    Returns:
        List of Story objects matching the search query
        
    Raises:
        RuntimeError: If search request fails
    """
    url = "https://hn.algolia.com/api/v1/search_by_date" if search_by_date else "https://hn.algolia.com/api/v1/search"
    
    params = {
        "query": query,
        "hitsPerPage": num_results,
        "tags": "story",
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise RuntimeError("Search request failed")
            data = await response.json()
            hits = data.get("hits", [])
            stories = []
            for hit in hits:
                try:
                    # Map Algolia fields to Story model
                    story_data = {
                        "id": int(hit.get("objectID")),
                        "by": hit.get("author"),
                        "time": hit.get("created_at_i"),
                        "title": hit.get("title"),
                        "url": hit.get("url"),
                        "score": hit.get("points", 0),
                        "type": "story",
                        "kids": hit.get("children", [])
                    }
                    stories.append(Story(**story_data))
                except (ValidationError, ValueError) as e:
                    continue  # Skip invalid entries
            return stories


async def main() -> None:
    """Test all Hacker News API functions with detailed output.
    
    Prints comprehensive information from each API function for verification.
    """
    # Test mcp_hn_get_stories
    print("=== Testing mcp_hn_get_stories (top stories) ===")
    top_stories = await mcp_hn_get_stories(story_type="top", num_stories=5)
    print(f"Fetched {len(top_stories)} top stories:")
    for i, story in enumerate(top_stories[:2], 1):  # Show first 2 for brevity
        print(f"{i}. Title: {story.title}")
        print(f"   ID: {story.id}, Author: {story.by}, Score: {story.score}")
        print(f"   URL: {story.url or 'N/A'}")
        print()

    # Test mcp_hn_get_story_info
    print("=== Testing mcp_hn_get_story_info (batch with pagination) ===")
    story_ids = [s.id for s in top_stories]
    story_info_batch = await mcp_hn_get_story_info(story_ids=story_ids, page=1, per_page=2)
    print(f"Fetched {len(story_info_batch)} stories (page 1, 2 per page):")
    for i, story in enumerate(story_info_batch, 1):
        comment_count = len(story.comments) if story.comments else 0
        print(f"{i}. Title: {story.title}")
        print(f"   ID: {story.id}, Author: {story.by}, Score: {story.score}")
        print(f"   Comments: {comment_count}")
        if story.comments:
            print(f"   First Comment: {story.comments[0].text[:50]}..." if len(story.comments[0].text) > 50 else story.comments[0].text)
        print()

    # Test mcp_hn_get_user_info
    print("=== Testing mcp_hn_get_user_info ===")
    user_name = story_info_batch[0].by
    user_info = await mcp_hn_get_user_info(user_name=user_name, num_stories=2)
    print(f"User: {user_info.user.id}")
    print(f"  Karma: {user_info.user.karma}")
    print(f"  Created: {user_info.user.created} (Unix timestamp)")
    print(f"  Submitted Stories: {len(user_info.submitted_stories)}")
    for i, story in enumerate(user_info.submitted_stories, 1):
        print(f"  {i}. Title: {story.title}, Score: {story.score}")
    print()

    # Test mcp_hn_search_stories
    print("=== Testing mcp_hn_search_stories ===")
    search_results = await mcp_hn_search_stories(query="python", search_by_date=False, num_results=3)
    print(f"Fetched {len(search_results)} search results for 'python':")
    for i, story in enumerate(search_results, 1):
        print(f"{i}. Title: {story.title}")
        print(f"   ID: {story.id}, Author: {story.by}, Score: {story.score}")
        print(f"   URL: {story.url or 'N/A'}")
        print()

if __name__ == "__main__":
    asyncio.run(main())