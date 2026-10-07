"""Streamable HTTP configuration and sessions for remote MCP servers."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Literal, Union

from mcp import ClientSession, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client
from pydantic import AnyHttpUrl, BaseModel, Field, PositiveFloat


class HttpServerParameters(BaseModel):
    """Remote server settings using the MCP SDK's timeout defaults."""

    transport: Literal["streamable_http"] = "streamable_http"
    url: AnyHttpUrl
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout: PositiveFloat = 30
    sse_read_timeout: PositiveFloat = 300


def server_parameters(config: Dict[str, Any]) -> Union[StdioServerParameters, HttpServerParameters]:
    """Choose the configured transport, preserving stdio as the default."""
    transport = config.get("transport", "stdio")
    if transport == "streamable_http":
        return HttpServerParameters(**config)
    if transport == "stdio":
        return StdioServerParameters(**config)
    raise ValueError(f"Unsupported MCP transport: {transport}")


@asynccontextmanager
async def http_session_context(params: HttpServerParameters) -> AsyncIterator[ClientSession]:
    """Initialize one HTTP session and let the SDK clean up on errors or cancellation."""
    headers = dict(params.headers)
    if not any(name.lower() == "user-agent" for name in headers):
        headers["User-Agent"] = "quantalogic-toolbox-mcp/0.13.0"
    async with streamablehttp_client(
        str(params.url), headers=headers, timeout=params.timeout, sse_read_timeout=params.sse_read_timeout
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
