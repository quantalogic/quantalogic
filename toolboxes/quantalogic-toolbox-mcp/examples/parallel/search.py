"""Search and fetch anonymously through the toolbox's discovered Parallel tools."""

import asyncio
import json
from typing import Any, Dict
from uuid import uuid4

from quantalogic_toolbox_mcp import get_tools


async def main(tools: Dict[str, Any]) -> None:
    """Call the discovered wrappers with one shared conversation identifier."""
    session_id = str(uuid4())
    search = await tools["parallel_web_search"](
        objective="Find the official Python asyncio documentation.",
        search_queries=["Python asyncio official documentation"],
        session_id=session_id,
    )
    print("Search:", json.dumps(search, indent=2))
    fetch = await tools["parallel_web_fetch"](
        urls=["https://docs.python.org/3/library/asyncio.html"],
        objective="What is asyncio used for?",
        session_id=session_id,
    )
    print("Fetch:", json.dumps(fetch, indent=2))


if __name__ == "__main__":
    tools = {tool.name: tool for tool in get_tools() if getattr(tool, "server_name", None) == "parallel"}
    asyncio.run(main(tools))
