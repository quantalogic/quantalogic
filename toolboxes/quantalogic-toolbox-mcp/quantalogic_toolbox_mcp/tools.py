"""Toolbox for interacting with MCP servers with JSON-based configuration.

This module provides a generic adapter for interacting with multiple MCP servers,
configured via JSON files in the ./config directory. Each server has its own tools,
and core tools are provided to interact with any server by specifying its name.
Tools are automatically queried from servers during initialization.
"""

import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from quantalogic.tools import ToolArgument, create_tool

# Configure logging
logger.remove()
logger.add(
    sink=sys.stderr,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    colorize=True,
    backtrace=True,
    diagnose=True
)

# Global dictionary to store server parameters
servers: Dict[str, StdioServerParameters] = {}

# Define toolbox at module level to avoid undefined name errors
toolbox: Dict[str, Dict[str, Any]] = {"tools": {}}

# Helper function to load JSON configuration
def load_mcp_config(config_path: str) -> Dict[str, Any]:
    """Load MCP configuration from a JSON file."""
    logger.debug(f"Loading configuration from {config_path}")
    try:
        with open(config_path) as f:
            config = json.load(f)
        logger.info(f"Successfully loaded config from {config_path}")
        return config
    except FileNotFoundError as e:
        logger.error(f"Config file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {config_path}")
        raise

# Load all configurations from ./config directory
def load_configs(config_dir: str = "./config") -> None:
    """Load all JSON config files from the specified directory into the servers dictionary."""
    if not os.path.exists(config_dir):
        logger.warning(f"Config directory {config_dir} does not exist, creating it")
        os.makedirs(config_dir)
    for filename in os.listdir(config_dir):
        if filename.endswith(".json"):
            config_path = os.path.join(config_dir, filename)
            try:
                config = load_mcp_config(config_path)
                # Handle both "mcpServers" and "mcp_servers" keys for compatibility
                server_configs = config.get("mcpServers", config.get("mcp_servers", {config.get("server_name", filename[:-5]): config}))
                for server_name, server_data in server_configs.items():
                    server_params = StdioServerParameters(
                        command=server_data["command"],
                        args=server_data["args"]
                    )
                    servers[server_name] = server_params
                    logger.info(f"Registered server: {server_name}")
            except Exception as e:
                logger.error(f"Failed to load config {config_path}: {str(e)}")

# Context manager for MCP session
@asynccontextmanager
async def mcp_session_context(server_params: StdioServerParameters) -> AsyncIterator[ClientSession]:
    """Async context manager for MCP sessions with improved Docker handling."""
    try:
        logger.debug(f"Starting session with: {server_params}")
        
        # Verify Docker is available
        proc = await asyncio.create_subprocess_exec(
            "docker", "version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError("Docker is not available or not running")
            
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                try:
                    await session.initialize()
                    logger.debug("Session initialized successfully")
                    yield session
                except Exception as e:
                    logger.error(f"Session initialization failed: {str(e)}")
                    raise
    except Exception as e:
        logger.error(f"Failed to create Docker session: {str(e)}")
        raise

async def check_docker_ready(server_params: StdioServerParameters, timeout: int = 30) -> bool:
    """Check if Docker container is ready to accept connections."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            proc = await asyncio.create_subprocess_exec(
                *[server_params.command] + server_params.args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return True
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"Docker check failed: {str(e)}")
            await asyncio.sleep(1)
    return False

# Core generic tools
@create_tool
async def mcp_list_resources(server_name: str) -> List[str]:
    """List available resources on the specified MCP server.

    Args:
        server_name: The name of the server to list resources from.

    Returns:
        A list of resource names or an error message if the server is not found.
    """
    logger.debug(f"Listing resources for server: {server_name}")
    server_params = servers.get(server_name)
    if not server_params:
        return [f"Error: Server '{server_name}' not found"]
    async with mcp_session_context(server_params) as session:
        resources = await session.list_resources()
        return [str(resource) for resource in resources]

@create_tool
async def mcp_list_tools(server_name: str) -> List[str]:
    """List available tools on the specified MCP server.

    Args:
        server_name: The name of the server to list tools from.

    Returns:
        A list of tool names or an error message if the server is not found.
    """
    logger.debug(f"Listing tools for server: {server_name}")
    server_params = servers.get(server_name)
    if not server_params:
        return [f"Error: Server '{server_name}' not found"]
    try:
        async with mcp_session_context(server_params) as session:
            tools_result = await session.list_tools()
            return [tool.name for tool in tools_result.tools]
    except Exception as e:
        logger.error(f"Failed to list tools for {server_name}: {str(e)}")
        return [f"Error: Could not connect to server '{server_name}' - {str(e)}"]

@create_tool
async def mcp_call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call a specific tool on the specified MCP server.

    Args:
        server_name: The name of the server to call the tool on.
        tool_name: The name of the tool to call.
        arguments: A dictionary of arguments to pass to the tool.

    Returns:
        A dictionary containing the tool's response or an error message.
    """
    logger.debug(f"Calling tool '{tool_name}' on server '{server_name}' with args: {arguments}")
    server_params = servers.get(server_name)
    if not server_params:
        return {"error": f"Server '{server_name}' not found"}
    async with mcp_session_context(server_params) as session:
        result = await session.call_tool(tool_name, arguments)
        return {
            "meta": str(result.meta) if result.meta else None,
            "content": str(result.content),
            "isError": result.isError
        }

@create_tool
def list_servers() -> List[str]:
    """List all configured MCP servers.

    Returns:
        A list of server names.
    """
    logger.debug("Listing all configured servers")
    return list(servers.keys())

# Fixed dynamic tool creation with proper closure
async def _create_dynamic_tool(server_name: str, tool_name: str, server_params: StdioServerParameters):
    """Create tool using correct API."""
    async def tool_func(**kwargs):
        async with mcp_session_context(server_params) as session:
            return await session.call_tool(tool_name, kwargs)
    
    # Create tool with just the function
    return create_tool(tool_func)

async def create_all_tools() -> Dict[str, Any]:
    """Create all tools with proper error handling."""
    tools = {}
    
    # Add core tools
    tools["mcp_list_resources"] = mcp_list_resources
    tools["mcp_list_tools"] = mcp_list_tools
    tools["mcp_call_tool"] = mcp_call_tool
    tools["list_servers"] = list_servers
    logger.debug("Added core tools to toolbox")

    # Add dynamic tools from each server
    for server_name, server_params in servers.items():
        config_path = os.path.join("./config", f"{server_name}.json")
        try:
            config = load_mcp_config(config_path)
            explicit_tools = config.get("tools", [])
        except Exception:
            explicit_tools = []
            logger.debug(f"No explicit tools found in config for {server_name}, will query server")

        # Query server for tools dynamically
        try:
            server_tools = await mcp_list_tools.async_execute(server_name=server_name)
            logger.info(f"Queried tools from {server_name}: {server_tools}")
        except Exception as e:
            server_tools = []
            logger.error(f"Failed to query tools from {server_name}: {str(e)}")

        # Add explicitly defined tools from config
        for tool_config in explicit_tools:
            mcp_tool_name = tool_config["name"]
            unique_tool_name = f"{server_name}_{mcp_tool_name}"
            logger.debug(f"Generating dynamic tool from config: {unique_tool_name}")

            async def tool_func(**kwargs):
                async with mcp_session_context(server_params) as session:
                    return await session.call_tool(mcp_tool_name, kwargs)

            tool = create_tool(tool_func)
            tool.name = unique_tool_name
            tool.description = tool_config.get("description", f"Tool {mcp_tool_name} on {server_name}")
            tool.arguments = [
                ToolArgument(
                    name=arg.get("name"),
                    arg_type=arg.get("arg_type", "str"),
                    description=arg.get("description", ""),
                    required=arg.get("required", False),
                    default=arg.get("default"),
                    example=arg.get("example")
                ) for arg in tool_config.get("arguments", [])
            ]
            tool.return_type = tool_config.get("return_type", "Dict[str, Any]")
            tool.return_description = tool_config.get("return_description", "Tool execution result")
            tools[unique_tool_name] = tool
            logger.info(f"Added dynamic tool from config: {unique_tool_name}")

        # Add dynamically queried tools from server
        for tool_name in server_tools:
            unique_tool_name = f"{server_name}_{tool_name}"
            if unique_tool_name not in tools:  # Avoid overwriting explicit tools
                logger.debug(f"Generating dynamic tool from server query: {unique_tool_name}")
                tool = await _create_dynamic_tool(server_name, tool_name, server_params)
                tools[unique_tool_name] = tool
                logger.info(f"Added dynamic tool from server query: {unique_tool_name}")

    return tools

async def initialize_toolbox() -> None:
    """Initialize toolbox with proper async handling."""
    load_configs()
    toolbox["tools"] = await create_all_tools()

# Run initialization at module load time
if __name__ == "__main__" or __package__:
    asyncio.run(initialize_toolbox())

# Test suite
if __name__ == "__main__":
    logger.info("Starting MCP toolbox test suite")
    async def test_toolbox():
        # Test core tools
        servers_list = toolbox["tools"]["list_servers"].execute()
        logger.info(f"Available servers: {servers_list}")
        if not servers_list:
            logger.error("No servers configured")
            return

        test_server = servers_list[0]
        resources = await toolbox["tools"]["mcp_list_resources"].async_execute(server_name=test_server)
        logger.info(f"Resources on {test_server}: {resources}")

        tools_list = await toolbox["tools"]["mcp_list_tools"].async_execute(server_name=test_server)
        logger.info(f"Tools on {test_server}: {tools_list}")

        version_result = await toolbox["tools"]["mcp_call_tool"].async_execute(
            server_name=test_server,
            tool_name="read_query",
            arguments={"query": "SELECT sqlite_version();"}
        )
        logger.info(f"SQLite version via mcp_call_tool: {version_result}")

        # Test dynamic tool
        dynamic_tool_name = f"{test_server}_read_query"
        if dynamic_tool_name in toolbox["tools"]:
            dynamic_result = await toolbox["tools"][dynamic_tool_name].async_execute(query="SELECT sqlite_version();")
            logger.info(f"SQLite version via dynamic tool: {dynamic_result}")

    asyncio.run(test_toolbox())
    logger.info("Test suite completed")