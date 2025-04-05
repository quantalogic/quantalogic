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
from typing import Any, AsyncIterator, Dict, List

from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from quantalogic.tools import ToolArgument, create_tool
from quantalogic.codeact.tools_manager import ToolRegistry

# **Configure Logging**
logger.remove()
logger.add(
    sink=sys.stderr,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    colorize=True,
    backtrace=True,
    diagnose=True
)

# **Global Variables**
servers: Dict[str, StdioServerParameters] = {}

toolbox: Dict[str, Any] = {
    "tools": {},  # Dictionary for tool instances
    "state": {}   # Dictionary for tool states
}

# **Configuration Loading Functions**
def load_mcp_config(config_path: str) -> Dict[str, Any]:
    """Load MCP configuration from a JSON file."""
    logger.debug(f"Loading configuration from {config_path}")
    try:
        with open(config_path) as f:
            config = json.load(f)
        logger.info(f"Successfully loaded config from {config_path}: {config}")
        return config
    except FileNotFoundError as e:
        logger.error(f"Config file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {config_path}")
        raise

def load_configs(config_dir: str = "./config") -> None:
    """Load all JSON config files from the specified directory into the servers dictionary."""
    logger.debug(f"Checking config directory: {config_dir}")
    if not os.path.exists(config_dir):
        logger.warning(f"Config directory {config_dir} does not exist, creating it")
        os.makedirs(config_dir)
    for filename in os.listdir(config_dir):
        if filename.endswith(".json"):
            config_path = os.path.join(config_dir, filename)
            logger.debug(f"Processing config file: {config_path}")
            try:
                config = load_mcp_config(config_path)
                server_configs = config.get("mcpServers", config.get("mcp_servers", {config.get("server_name", filename[:-5]): config}))
                logger.debug(f"Server configs extracted: {server_configs}")
                for server_name, server_data in server_configs.items():
                    server_params = StdioServerParameters(
                        command=server_data["command"],
                        args=server_data["args"]
                    )
                    servers[server_name] = server_params
                    logger.info(f"Registered server: {server_name} with params: {server_params}")
            except Exception as e:
                logger.error(f"Failed to load config {config_path}: {str(e)}")

# **MCP Session Management**
@asynccontextmanager
async def mcp_session_context(server_params: StdioServerParameters) -> AsyncIterator[ClientSession]:
    """Async context manager for MCP sessions with improved Docker handling."""
    logger.debug(f"Starting session with params: {server_params}")
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        logger.debug(f"Docker version check: returncode={proc.returncode}, stdout={stdout.decode()}, stderr={stderr.decode()}")
        if proc.returncode != 0:
            raise RuntimeError("Docker is not available or not running")
            
        async with stdio_client(server_params) as (read, write):
            logger.debug("STDIO client established")
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
    logger.debug(f"Checking Docker readiness for params: {server_params}")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            proc = await asyncio.create_subprocess_exec(
                *[server_params.command] + server_params.args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            logger.debug(f"Docker readiness check: returncode={proc.returncode}, stdout={stdout.decode()}, stderr={stderr.decode()}")
            if proc.returncode == 0:
                return True
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"Docker check failed: {str(e)}")
            await asyncio.sleep(1)
    logger.warning(f"Docker not ready within {timeout} seconds")
    return False

# **Core Generic Tools**
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
        logger.warning(f"Server '{server_name}' not found in servers: {servers.keys()}")
        return [f"Error: Server '{server_name}' not found"]
    async with mcp_session_context(server_params) as session:
        resources = await session.list_resources()
        logger.debug(f"Resources retrieved: {resources}")
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
        logger.warning(f"Server '{server_name}' not found in servers: {servers.keys()}")
        return [f"Error: Server '{server_name}' not found"]
    try:
        async with mcp_session_context(server_params) as session:
            tools_result = await session.list_tools()
            logger.debug(f"Raw tools result from server: {tools_result}")
            tool_names = [tool.name for tool in tools_result.tools]
            logger.debug(f"Tool names extracted: {tool_names}")
            return tool_names
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
        logger.warning(f"Server '{server_name}' not found in servers: {servers.keys()}")
        return {"error": f"Server '{server_name}' not found"}
    async with mcp_session_context(server_params) as session:
        result = await session.call_tool(tool_name, arguments)
        logger.debug(f"Tool call result: meta={result.meta}, content={result.content}, isError={result.isError}")
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
    server_list = list(servers.keys())
    logger.debug(f"Server list: {server_list}")
    return server_list

# **Dynamic Tool Creation**
async def fetch_tool_details(server_name: str, tool_name: str, server_params: StdioServerParameters) -> Dict[str, Any]:
    """Fetch detailed tool information from MCP server dynamically with extensive logging.

    Args:
        server_name: Name of the server.
        tool_name: Name of the tool to fetch details for.
        server_params: Server parameters for establishing the session.

    Returns:
        Dict containing tool details (name, description, arguments, return_type, return_description).
    """
    logger.debug(f"Fetching details for tool '{tool_name}' on server '{server_name}'")
    async with mcp_session_context(server_params) as session:
        try:
            tools_result = await session.list_tools()
            logger.debug(f"Raw tools_result from MCP server: {tools_result}")
            logger.debug(f"Number of tools returned: {len(tools_result.tools)}")
            for tool in tools_result.tools:
                logger.debug(f"Examining tool: {tool.name}, full object: {vars(tool) if hasattr(tool, '__dict__') else str(tool)}")
                if tool.name == tool_name:
                    args = []
                    # Check for inputSchema (capital 'S' as per MCP server response)
                    arg_list = None
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        arg_list = tool.inputSchema.get('properties', {})
                        logger.debug(f"Found 'inputSchema' attribute: {tool.inputSchema}")
                    elif hasattr(tool, 'arguments') and tool.arguments:
                        arg_list = tool.arguments
                        logger.debug(f"Found 'arguments' attribute: {arg_list}")
                    elif hasattr(tool, 'params') and tool.params:
                        arg_list = tool.params
                        logger.debug(f"Found 'params' attribute: {arg_list}")
                    elif hasattr(tool, 'input_schema') and tool.input_schema:
                        arg_list = tool.input_schema
                        logger.debug(f"Found 'input_schema' attribute: {arg_list}")

                    if arg_list:
                        required_args = getattr(tool.inputSchema, 'required', []) if hasattr(tool, 'inputSchema') else []
                        logger.debug(f"Required arguments from inputSchema: {required_args}")
                        logger.debug(f"Processing {len(arg_list)} arguments for tool '{tool_name}'")
                        for arg_name, arg_details in arg_list.items() if isinstance(arg_list, dict) else enumerate(arg_list):
                            logger.debug(f"Argument '{arg_name}' raw data: {arg_details}")
                            try:
                                if isinstance(arg_list, dict):
                                    # Dictionary format from inputSchema 'properties'
                                    name = arg_name
                                    arg_type = arg_details.get('type', 'str')
                                    description = arg_details.get('description', f"Argument for {tool_name}")
                                    required = name in required_args
                                    default = arg_details.get('default', None)
                                    example = arg_details.get('example', None)
                                    logger.debug(f"Parsed dict arg: name={name}, type={arg_type}, desc={description}, req={required}, def={default}, ex={example}")
                                else:
                                    # List format (assuming objects)
                                    name = getattr(arg_details, 'name', f"arg_{len(args) + 1}")
                                    arg_type = getattr(arg_details, 'type', 'str')
                                    description = getattr(arg_details, 'description', f"Argument for {tool_name}")
                                    required = getattr(arg_details, 'required', True)
                                    default = getattr(arg_details, 'default', None)
                                    example = getattr(arg_details, 'example', None)
                                    logger.debug(f"Parsed object arg: name={name}, type={arg_type}, desc={description}, req={required}, def={default}, ex={example}")
                                
                                args.append(ToolArgument(
                                    name=name,
                                    arg_type=arg_type,
                                    description=description,
                                    required=required,
                                    default=default,
                                    example=example
                                ))
                                logger.debug(f"Added argument: {name} to tool '{tool_name}'")
                            except Exception as e:
                                logger.warning(f"Failed to parse argument '{arg_name}' for '{tool_name}': {str(e)}")
                                args.append(ToolArgument(
                                    name=f"arg_{len(args) + 1}",
                                    arg_type="str",
                                    description=f"Unknown argument for {tool_name}",
                                    required=True
                                ))
                                logger.debug(f"Added default argument due to parsing error")
                    else:
                        logger.debug(f"No argument attributes found for tool '{tool_name}' in server response")

                    tool_details = {
                        'name': tool.name,
                        'description': getattr(tool, 'description', f'Tool {tool_name} from {server_name}'),
                        'arguments': args,
                        'return_type': getattr(tool, 'return_type', 'Dict[str, Any]'),
                        'return_description': getattr(tool, 'return_description', 'Tool execution result')
                    }
                    logger.debug(f"Tool details constructed for '{tool_name}': {tool_details}")
                    return tool_details

            logger.warning(f"Tool '{tool_name}' not found in server response")
            return {}
        except Exception as e:
            logger.error(f"Failed to fetch tool details for '{tool_name}' on '{server_name}': {str(e)}")
            return {}

async def create_dynamic_tool(server_name: str, tool_name: str, server_params: StdioServerParameters):
    """Create a dynamic tool based on MCP server tool definition."""
    logger.debug(f"Creating dynamic tool '{server_name}_{tool_name}'")
    tool_details = await fetch_tool_details(server_name, tool_name, server_params)
    
    if not tool_details:
        logger.warning(f"No details found for tool '{tool_name}' on server '{server_name}'")
        return None

    async def tool_func(**kwargs):
        logger.debug(f"Executing tool '{tool_name}' on '{server_name}' with kwargs: {kwargs}")
        async with mcp_session_context(server_params) as session:
            result = await session.call_tool(tool_name, kwargs)
            logger.debug(f"Tool execution result: meta={result.meta}, content={result.content}, isError={result.isError}")
            return {
                "meta": str(result.meta) if result.meta else None,
                "content": str(result.content),
                "isError": result.isError
            }

    tool = create_tool(tool_func)
    tool.name = f"{server_name}_{tool_name}"
    tool.description = tool_details.get('description', f"Dynamic tool {tool_name} from {server_name}")
    tool.arguments = tool_details.get('arguments', [])
    tool.return_type = tool_details.get('return_type', 'Dict[str, Any]')
    tool.return_description = tool_details.get('return_description', 'Tool execution result')
    tool.toolbox_name = f"dynamic_{server_name}"
    logger.debug(f"Dynamic tool created: name={tool.name}, args={tool.arguments}, toolbox={tool.toolbox_name}")
    return tool

# **Toolbox Initialization**
async def create_all_tools(registry: ToolRegistry) -> Dict[str, Any]:
    """Create all tools by querying MCP servers dynamically and track their state."""
    tools = {}
    logger.debug("Starting tool creation process")
    
    # Add core tools with state tracking
    core_tools = {
        "mcp_list_resources": mcp_list_resources,
        "mcp_list_tools": mcp_list_tools,
        "mcp_call_tool": mcp_call_tool,
        "list_servers": list_servers
    }
    for tool_name, tool in core_tools.items():
        tool.toolbox_name = "quantalogic_toolbox_mcp"
        key = (tool.toolbox_name, tool.name)
        if key not in registry.tools:
            registry.register(tool)
            logger.debug(f"Registered core tool: {tool_name} in toolbox {tool.toolbox_name}")
        tools[tool_name] = tool
        toolbox["state"][tool_name] = {
            "status": "success",
            "toolbox_name": "quantalogic_toolbox_mcp",
            "error": None
        }
    logger.debug("Added core tools to toolbox")

    # Add dynamic tools from each server
    for server_name, server_params in servers.items():
        logger.debug(f"Processing server: {server_name}")
        try:
            server_tools = await mcp_list_tools.async_execute(server_name=server_name)
            logger.debug(f"Tools listed for '{server_name}': {server_tools}")
            if f"Error: Server '{server_name}' not found" in server_tools:
                logger.error(f"Server '{server_name}' not found")
                continue

            for tool_name in server_tools:
                unique_tool_name = f"{server_name}_{tool_name}"
                logger.debug(f"Creating dynamic tool: {unique_tool_name}")
                
                tool = await create_dynamic_tool(server_name, tool_name, server_params)
                if tool:
                    key = (tool.toolbox_name, tool.name)
                    if key not in registry.tools:
                        registry.register(tool)
                        logger.debug(f"Registered dynamic tool: {unique_tool_name} with args: {tool.arguments}")
                    tools[unique_tool_name] = tool
                    toolbox["state"][unique_tool_name] = {
                        "status": "success",
                        "toolbox_name": tool.toolbox_name,
                        "error": None
                    }
                    logger.info(f"Registered dynamic tool: {unique_tool_name} with toolbox: {tool.toolbox_name}")
                else:
                    toolbox["state"][unique_tool_name] = {
                        "status": "failed",
                        "toolbox_name": f"dynamic_{server_name}",
                        "error": "Failed to fetch tool details or create tool"
                    }
                    logger.warning(f"Failed to create tool: {unique_tool_name}")

            # Handle config-defined tools
            config_path = os.path.join("./config", f"{server_name}.json")
            try:
                config = load_mcp_config(config_path)
                explicit_tools = config.get("tools", [])
                logger.debug(f"Config-defined tools for '{server_name}': {explicit_tools}")
                for tool_config in explicit_tools:
                    mcp_tool_name = tool_config["name"]
                    unique_tool_name = f"{server_name}_{mcp_tool_name}"
                    if unique_tool_name not in tools:
                        tool = await create_dynamic_tool(server_name, mcp_tool_name, server_params)
                        if tool:
                            tool.description = tool_config.get("description", tool.description)
                            tool.arguments = [
                                ToolArgument(**arg) for arg in tool_config.get("arguments", tool.arguments)
                            ]
                            tool.return_type = tool_config.get("return_type", tool.return_type)
                            tool.return_description = tool_config.get("return_description", tool.return_description)
                            key = (tool.toolbox_name, tool.name)
                            if key not in registry.tools:
                                registry.register(tool)
                                logger.debug(f"Registered config-defined tool: {unique_tool_name} with args: {tool.arguments}")
                            tools[unique_tool_name] = tool
                            toolbox["state"][unique_tool_name] = {
                                "status": "success",
                                "toolbox_name": tool.toolbox_name,
                                "error": None
                            }
                            logger.info(f"Added config-defined tool: {unique_tool_name} with toolbox: {tool.toolbox_name}")
                        else:
                            toolbox["state"][unique_tool_name] = {
                                "status": "failed",
                                "toolbox_name": f"dynamic_{server_name}",
                                "error": "Failed to create config-defined tool"
                            }
                            logger.warning(f"Failed to create config-defined tool: {unique_tool_name}")
            except Exception as e:
                logger.debug(f"No config tools processed for {server_name}: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to process tools for server {server_name}: {str(e)}")

    logger.debug(f"Tool creation completed. Total tools: {len(tools)}")
    return tools

async def initialize_toolbox(registry: ToolRegistry) -> None:
    """Initialize toolbox with proper async handling and log final state."""
    logger.debug("Initializing toolbox")
    load_configs()
    toolbox["tools"] = await create_all_tools(registry)
    logger.info("Toolbox initialization completed. Final tool states:")
    for tool_name, state in toolbox["state"].items():
        if state["status"] == "success":
            logger.info(f"Tool: {tool_name}, Status: {state['status']}, Toolbox: {state['toolbox_name']}")
        else:
            logger.warning(f"Tool: {tool_name}, Status: {state['status']}, Toolbox: {state['toolbox_name']}, Error: {state['error']}")

# **Main Execution**
if __name__ == "__main__" or __package__:
    from quantalogic.codeact.plugin_manager import PluginManager
    plugin_manager = PluginManager()
    plugin_manager.load_plugins()
    asyncio.run(initialize_toolbox(plugin_manager.tools))

if __name__ == "__main__":
    logger.info("Starting MCP toolbox test suite")
    async def test_toolbox():
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

        dynamic_tool_name = f"{test_server}_read_query"
        if dynamic_tool_name in toolbox["tools"]:
            dynamic_result = await toolbox["tools"][dynamic_tool_name].async_execute(query="SELECT sqlite_version();")
            logger.info(f"SQLite version via dynamic tool: {dynamic_result}")

    asyncio.run(test_toolbox())
    logger.info("Test suite completed")