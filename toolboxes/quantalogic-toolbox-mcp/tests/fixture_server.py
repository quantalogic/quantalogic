"""Local MCP fixture supporting both stdio and Streamable HTTP."""

import asyncio
import sys
from typing import Dict, List

from mcp.server.fastmcp import FastMCP

server = FastMCP("toolbox-test", host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)


@server.tool()
def web_search(objective: str, search_queries: List[str]) -> Dict:
    return {"results": [{"url": "https://example.com", "excerpts": [objective], "queries": search_queries}]}


@server.tool()
def web_fetch(urls: List[str]) -> Dict:
    return {"results": [{"url": urls[0], "excerpts": ["Fetched page content"]}]}


@server.tool()
def failure() -> str:
    raise ValueError("fixture tool failed")


@server.tool()
async def slow() -> str:
    await asyncio.sleep(30)
    return "finished"


if __name__ == "__main__":
    server.run(transport="streamable-http" if len(sys.argv) > 1 else "stdio")
