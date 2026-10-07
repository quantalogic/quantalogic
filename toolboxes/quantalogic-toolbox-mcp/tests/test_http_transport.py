"""Exercise remote configuration through discovery, caching and dynamic execution."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest
from mcp import StdioServerParameters


def write_config(tmp_path, http_server, extra=None):
    config = {"transport": "streamable_http", "url": http_server, **(extra or {})}
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {"remote": config}}))


def test_loader_cache_and_dynamic_execution(toolbox, tmp_path, http_server, monkeypatch):
    write_config(tmp_path, http_server)
    requests = []
    send = httpx.AsyncClient.send

    async def capture(client, request, *args, **kwargs):
        requests.append(request)
        return await send(client, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", capture)
    toolbox.load_configs(str(tmp_path))
    exercise_tools(toolbox)
    requests.clear()
    toolbox.load_configs(str(tmp_path))
    toolbox._tools_cache = None
    assert requests == [], "Cache reload should not contact the server"
    exercise_tools(toolbox)
    assert all(request.headers["user-agent"] == "quantalogic-toolbox-mcp/0.13.0" for request in requests)
    assert all("authorization" not in request.headers for request in requests)


def exercise_tools(toolbox):
    dynamic = {tool.name: tool for tool in toolbox.get_tools() if hasattr(tool, "server_name")}
    assert {arg["name"] for arg in dynamic["remote_web_search"].arguments if arg["required"]} == {
        "objective", "search_queries",
    }
    search = asyncio.run(dynamic["remote_web_search"](objective="Find docs", search_queries=["docs"]))
    fetch = asyncio.run(dynamic["remote_web_fetch"](urls=["https://example.com"]))
    assert search[0]["results"][0]["excerpts"] == ["Find docs"]
    assert fetch[0]["results"][0]["excerpts"] == ["Fetched page content"]


def test_headers_and_timeouts_round_trip(toolbox, tmp_path, http_server, monkeypatch):
    monkeypatch.setenv("TEST_MCP_HEADER", "test-value")
    write_config(tmp_path, http_server, {
        "headers": {"user-agent": "custom-client", "X-Test": "{{ env.TEST_MCP_HEADER }}"},
        "timeout": 2, "sse_read_timeout": 3,
    })
    requests = []
    send = httpx.AsyncClient.send

    async def capture(client, request, *args, **kwargs):
        requests.append(request)
        return await send(client, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", capture)
    toolbox.load_configs(str(tmp_path))
    toolbox.load_configs(str(tmp_path))
    assert toolbox.servers["remote"].timeout == 2
    assert toolbox.servers["remote"].sse_read_timeout == 3
    assert all(r.extensions["timeout"]["read"] == 3 and r.extensions["timeout"]["connect"] == 2 for r in requests)
    assert all(r.headers["user-agent"] == "custom-client" and r.headers["x-test"] == "test-value" for r in requests)


def test_tool_error_and_cancellation(toolbox, tmp_path, http_server):
    write_config(tmp_path, http_server)
    toolbox.load_configs(str(tmp_path))
    with pytest.raises(Exception) as error:
        asyncio.run(toolbox.mcp_call_tool("remote", "failure", {}))
    assert "fixture tool failed" in exception_messages(error.value)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(asyncio.wait_for(toolbox.mcp_call_tool("remote", "slow", {}), timeout=0.2))
    result = asyncio.run(toolbox.mcp_call_tool("remote", "web_fetch", {"urls": ["https://example.com"]}))
    assert result[0]["results"][0]["url"] == "https://example.com"


def test_stdio_configuration_and_execution(toolbox, tmp_path):
    fixture = Path(__file__).with_name("fixture_server.py")
    config = {"command": sys.executable, "args": [str(fixture)], "cwd": str(tmp_path), "env": {"MCP_TEST": "yes"}}
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {"remote": config}}))
    toolbox.load_configs(str(tmp_path))
    assert isinstance(toolbox.servers["remote"], StdioServerParameters)
    assert toolbox.servers["remote"].cwd == str(tmp_path)
    assert toolbox.servers["remote"].env == {"MCP_TEST": "yes"}
    exercise_tools(toolbox)
    toolbox.load_configs(str(tmp_path))
    assert isinstance(toolbox.servers["remote"], StdioServerParameters)
    assert toolbox.servers["remote"].cwd == str(tmp_path)
    assert toolbox.servers["remote"].env == {"MCP_TEST": "yes"}


@pytest.mark.parametrize("config", [
    {"transport": "sse", "url": "https://example.com"},
    {"transport": "streamable_http", "url": "file:///tmp/server"},
    {"transport": "streamable_http", "url": "https://example.com", "timeout": 0},
])
def test_invalid_configuration_is_not_registered(toolbox, tmp_path, config):
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {"invalid": config}}))
    toolbox.load_configs(str(tmp_path))
    assert "invalid" not in toolbox.servers


def exception_messages(error):
    children = getattr(error, "exceptions", [])
    return " ".join(exception_messages(child) for child in children) if children else str(error)
