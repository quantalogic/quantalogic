import asyncio
import json

import aiohttp

from quantalogic.tools import create_tool


@create_tool
async def mcp_hn_get_stories(story_type: str, num_stories: int) -> str:
    """Get stories from Hacker News. The options are `top`, `new`, `ask_hn`, `show_hn` for types of stories. This doesn't include the comments. Use `get_story_info` to get the comments."""
    # Map story_type to API endpoints (adjusted to match query options)
    story_type_endpoints = {
        'top': 'topstories',
        'new': 'newstories',
        'ask_hn': 'askstories',
        'show_hn': 'showstories',
    }
    if story_type not in story_type_endpoints:
        return json.dumps({"error": f"Invalid story_type: {story_type}. Valid options are {list(story_type_endpoints.keys())}"})
    
    async with aiohttp.ClientSession() as session:
        # Fetch the list of story IDs
        url = f"https://hacker-news.firebaseio.com/v0/{story_type_endpoints[story_type]}.json"
        async with session.get(url) as response:
            if response.status != 200:
                return json.dumps({"error": "Failed to fetch story IDs"})
            story_ids = await response.json()
        
        # Limit to num_stories
        story_ids = story_ids[:num_stories]
        
        # Fetch story details concurrently
        async def fetch_story(story_id):
            url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        
        stories = await asyncio.gather(*[fetch_story(id) for id in story_ids])
        stories = [story for story in stories if story is not None]
        
        return json.dumps({"stories": stories})

async def fetch_item(session, item_id):
    """Helper function to fetch an item by ID."""
    url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    async with session.get(url) as response:
        if response.status == 200:
            return await response.json()
        return None

async def fetch_comments(session, item):
    """Recursively fetch all comments for an item."""
    if 'kids' in item:
        comment_ids = item['kids']
        comments = await asyncio.gather(*[fetch_item(session, cid) for cid in comment_ids])
        comments = [c for c in comments if c is not None]
        for comment in comments:
            await fetch_comments(session, comment)
        item['comments'] = comments
    else:
        item['comments'] = []

@create_tool
async def mcp_hn_get_story_info(story_id: int) -> str:
    """Get detailed story info from Hacker News, including the comments."""
    async with aiohttp.ClientSession() as session:
        story = await fetch_item(session, story_id)
        if story is None:
            return json.dumps({"error": f"Story with ID {story_id} not found"})
        await fetch_comments(session, story)
        return json.dumps(story)

@create_tool
async def mcp_hn_get_user_info(user_name: str, num_stories: int) -> str:
    """Get user info from Hacker News, including the stories they've submitted."""
    async with aiohttp.ClientSession() as session:
        # Fetch user data
        url = f"https://hacker-news.firebaseio.com/v0/user/{user_name}.json"
        async with session.get(url) as response:
            if response.status != 200:
                return json.dumps({"error": f"User '{user_name}' not found"})
            user_data = await response.json()
        
        if 'submitted' not in user_data:
            return json.dumps({"user": user_data, "submitted_stories": []})
        
        submitted_ids = user_data['submitted']
        stories = []
        # Fetch items until we have num_stories stories
        for item_id in submitted_ids:
            if len(stories) >= num_stories:
                break
            item = await fetch_item(session, item_id)
            if item and item.get('type') == 'story':
                stories.append(item)
        
        return json.dumps({"user": user_data, "submitted_stories": stories})

@create_tool
async def mcp_hn_search_stories(query: str, search_by_date: bool, num_results: int) -> str:
    """Search stories from Hacker News. It is generally recommended to use simpler queries to get a broader set of results (less than 5 words). Very targeted queries may not return any results."""
    # Choose Algolia API endpoint based on search_by_date
    url = "https://hn.algolia.com/api/v1/search_by_date" if search_by_date else "https://hn.algolia.com/api/v1/search"
    
    params = {
        "query": query,
        "hitsPerPage": num_results,
        "tags": "story",  # Ensure only stories are returned
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return json.dumps({"error": "Search request failed"})
            data = await response.json()
            hits = data.get("hits", [])
            return json.dumps({"search_results": hits})

async def main():
    """Test all Hacker News API functions."""
    print("Testing mcp_hn_get_stories (top stories):")
    top_stories = await mcp_hn_get_stories(story_type="top", num_stories=5)
    print(json.loads(top_stories)["stories"][0]["title"])
    
    print("\nTesting mcp_hn_get_story_info:")
    story_id = json.loads(top_stories)["stories"][0]["id"]
    story_info = await mcp_hn_get_story_info(story_id=story_id)
    print(json.loads(story_info)["title"])
    
    print("\nTesting mcp_hn_get_user_info:")
    user_name = json.loads(story_info)["by"]
    user_info = await mcp_hn_get_user_info(user_name=user_name, num_stories=2)
    print(json.loads(user_info)["user"]["id"])
    
    print("\nTesting mcp_hn_search_stories:")
    search_results = await mcp_hn_search_stories(query="python", search_by_date=False, num_results=3)
    print(json.loads(search_results)["search_results"][0]["title"])

if __name__ == "__main__":
    asyncio.run(main())