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
        comments = await asyncio.gather(*[fetch_and_parse_item(session, cid) for cid in comment_ids])
        comments = [c for c in comments if c is not None]
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
        
        async def fetch_story(story_id):
            return await fetch_and_parse_item(session, story_id)
        
        stories = await asyncio.gather(*[fetch_story(id) for id in story_ids])
        return [story for story in stories if isinstance(story, Story)]


@create_tool
async def mcp_hn_get_story_info(story_id: int) -> Story:
    """Fetch detailed information about a Hacker News story including comments.
    
    Args:
        story_id: ID of the story to fetch
        
    Returns:
        Story object with populated comments
        
    Raises:
        ValueError: If story not found or invalid
        RuntimeError: If HTTP request fails
    """
    async with aiohttp.ClientSession() as session:
        story = await fetch_and_parse_item(session, story_id)
        if not isinstance(story, Story):
            raise ValueError(f"Story with ID {story_id} not found or not a story")
        await fetch_comments(session, story)
        return story


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
        stories = []
        for item_id in submitted_ids:
            if len(stories) >= num_stories:
                break
            item = await fetch_and_parse_item(session, item_id)
            if item and isinstance(item, Story):
                stories.append(item)
        
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
    """Test all Hacker News API functions.
    
    Prints sample output from each API function for verification.
    """
    print("Testing mcp_hn_get_stories (top stories):")
    top_stories = await mcp_hn_get_stories(story_type="top", num_stories=5)
    print(top_stories[0].title)
    
    print("\nTesting mcp_hn_get_story_info:")
    story_id = top_stories[0].id
    story_info = await mcp_hn_get_story_info(story_id=story_id)
    print(story_info.title)
    
    print("\nTesting mcp_hn_get_user_info:")
    user_name = story_info.by
    user_info = await mcp_hn_get_user_info(user_name=user_name, num_stories=2)
    print(user_info.user.id)
    
    print("\nTesting mcp_hn_search_stories:")
    search_results = await mcp_hn_search_stories(query="python", search_by_date=False, num_results=3)
    print(search_results[0].title)

if __name__ == "__main__":
    asyncio.run(main())