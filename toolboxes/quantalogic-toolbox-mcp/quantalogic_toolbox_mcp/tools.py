"""Toolbox for interacting with MCP servers with JSON-based configuration.

This module provides a generic adapter for interacting with multiple MCP servers,
configured via JSON files in a configurable directory (default: ./config). Each server has its own tools,
and core tools are provided to interact with any server by specifying its name.
Tools are automatically queried from servers during initialization with caching and refresh options.
"""

import ast
import asyncio
import json
import keyword
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List

from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from quantalogic.codeact.tools_manager import ToolRegistry
from quantalogic.tools import ToolArgument, create_tool

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
tools_cache: Dict[str, Any] = {}  # Cache for storing tools_result per server
USE_DOCKER = os.getenv("MCP_USE_DOCKER", "true").lower() == "true"  # Configurable Docker usage

toolbox: Dict[str, Any] = {
    "tools": {},  # Dictionary for tool instances
    "state": {}   # Dictionary for tool states
}

_toolbox_initialized = False  # Flag to prevent redundant initialization

# **Utility Functions**
def parse_string_content(text: str) -> Any:
    """Parse a string into a Python object, trying JSON first, then AST, with enhanced error handling.

    Args:
        text: The string to parse.

    Returns:
        Parsed content as a Python type (e.g., list, dict, str).

    Raises:
        ValueError: If content cannot be parsed as JSON or Python literal.
    """
    if not text.strip():
        logger.warning("Empty content received, returning None")
        return None
    try:
        # Attempt to parse as JSON (expects double quotes, 'null')
        parsed = json.loads(text)
        if isinstance(parsed, (list, dict)):
            logger.debug(f"Parsed string as JSON: {parsed}")
            return parsed
        logger.debug(f"JSON-parsed content is not a list or dict, returning as-is: {parsed}")
        return parsed
    except json.JSONDecodeError as e:
        logger.debug(f"JSON parsing failed: {e}")
        try:
            # Fallback to parsing as a Python literal (handles single quotes, None)
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (list, dict)):
                logger.debug(f"Parsed string as Python literal: {parsed}")
                return parsed
            logger.debug(f"AST-parsed content is not a list or dict, returning as-is: {parsed}")
            return parsed
        except (ValueError, SyntaxError) as e:
            logger.warning(f"Failed to parse content as JSON or Python literal: {e}")
            raise ValueError(f"Unparsable content: {text[:50]}...") from e

def parse_text_content(content: Any) -> Any:
    """Parse MCP tool response content into a usable Python type.

    Args:
        content: The raw content from the server response.

    Returns:
        Parsed content as a Python type (e.g., list, dict, str).

    Raises:
        ValueError: Propagated from parse_string_content if parsing fails.
    """
    logger.debug(f"Parsing content: {str(content)[:50]}...")
    # Handle lists by recursively parsing each element
    if isinstance(content, list):
        return [parse_text_content(item) for item in content]
    # Handle objects with text attribute (e.g., TextContent)
    elif hasattr(content, 'text'):
        text_content = content.text
        return parse_string_content(text_content)
    # Handle plain strings
    elif isinstance(content, str):
        return parse_string_content(content)
    # Return as-is for other types
    logger.debug(f"Content is already a native type: {content}")
    return content

def sanitize_name(name: str) -> str:
    """Sanitize a string to be a valid Python identifier.

    Args:
        name: The original name to sanitize.

    Returns:
        A string that is a valid Python identifier.
    """
    # Replace all non-alphanumeric characters (except underscores) with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Prefix with underscore if it starts with a digit
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    # Append underscore if it’s a Python keyword
    if keyword.iskeyword(sanitized):
        sanitized += '_'
    return sanitized

# **Configuration Loading Functions**
def load_mcp_config(config_path: str) -> Dict[str, Any]:
    """Load MCP configuration from a JSON file with secret resolution.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        Dictionary containing the configuration data.

    Raises:
        FileNotFoundError: If the config file is not found.
        json.JSONDecodeError: If the JSON is invalid.
    """
    logger.debug(f"Loading configuration from {config_path}")
    try:
        with open(config_path) as f:
            config = json.load(f)
        config = resolve_secrets(config)  # Resolve environment variables
        logger.info(f"Successfully loaded config from {config_path}: {config}")
        return config
    except FileNotFoundError as e:
        logger.error(f"Config file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {config_path}")
        raise

def resolve_secrets(config: Dict) -> Dict:
    """Resolve environment variable placeholders in a config dictionary.

    Args:
        config: The configuration dictionary to process.

    Returns:
        The config with resolved environment variables.
    """
    for key, value in config.items():
        if isinstance(value, str) and "{{ env." in value:
            env_var = value.split("{{ env.")[1].split("}}")[0]
            config[key] = os.getenv(env_var, value)
        elif isinstance(value, dict):
            config[key] = resolve_secrets(value)
    return config

def load_configs(config_dir: str = os.getenv("MCP_CONFIG_DIR", "./config")) -> None:
    """Load all JSON config files from the specified directory into the servers dictionary.

    Args:
        config_dir: Directory containing JSON config files (default: env var MCP_CONFIG_DIR or './config').
    """
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
    """Async context manager for MCP sessions with configurable Docker handling.

    Args:
        server_params: Parameters for the MCP server session.

    Yields:
        An initialized ClientSession for interacting with the MCP server.

    Raises:
        RuntimeError: If Docker is required but unavailable.
    """
    logger.debug(f"Starting session with params: {server_params}")
    if not USE_DOCKER:
        logger.debug("Bypassing Docker, using direct STDIO client")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.debug("Direct session initialized successfully")
                yield session
    else:
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
                logger.debug("STDIO client established via Docker")
                async with ClientSession(read, write) as session:
                    try:
                        await session.initialize()
                        logger.debug("Docker session initialized successfully")
                        yield session
                    except Exception as e:
                        logger.error(f"Session initialization failed: {str(e)}")
                        raise
        except Exception as e:
            logger.error(f"Failed to create Docker session: {str(e)}")
            raise

async def check_docker_ready(server_params: StdioServerParameters, timeout: int = 30) -> bool:
    """Check if Docker container is ready to accept connections.

    Args:
        server_params: Parameters for the MCP server.
        timeout: Maximum time to wait (in seconds, default: 30).

    Returns:
        Boolean indicating if the Docker container is ready.
    """
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
        A list of resource names.
        Example: ['resource1', 'resource2']
    """
    logger.debug(f"Listing resources for server: {server_name}")
    server_params = servers.get(server_name)
    if not server_params:
        logger.warning(f"Server '{server_name}' not found in servers: {servers.keys()}")
        raise ValueError(f"Server '{server_name}' not found")
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
        A list of tool names.
        Example: ['read_query', 'write_query']
    """
    logger.debug(f"Listing tools for server: {server_name}")
    server_params = servers.get(server_name)
    if not server_params:
        logger.warning(f"Server '{server_name}' not found in servers: {servers.keys()}")
        raise ValueError(f"Server '{server_name}' not found")
    try:
        async with mcp_session_context(server_params) as session:
            tools_result = await session.list_tools()
            logger.debug(f"Raw tools result from server: {tools_result}")
            tools_cache[server_name] = tools_result  # Cache the tools_result
            tool_names = [tool.name for tool in tools_result.tools]
            logger.debug(f"Tool names extracted: {tool_names}")
            return tool_names
    except Exception as e:
        logger.error(f"Failed to list tools for {server_name}: {str(e)}")
        raise RuntimeError(f"Could not connect to server '{server_name}': {str(e)}")

@create_tool
async def mcp_call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call a specific tool on the specified MCP server.

    Args:
        server_name: The name of the server to call the tool on.
        tool_name: The name of the tool to call.
        arguments: A dictionary of arguments to pass to the tool.

    Returns:
        The result of the tool execution, type depends on the tool called.
        Use specific tools (e.g., sqlite_read_query) for predictable return types.
        Example (generic success): [{'id': 1, 'name': 'John'}]
    """
    logger.debug(f"Calling tool '{tool_name}' on server '{server_name}' with args: {arguments}")
    server_params = servers.get(server_name)
    if not server_params:
        logger.warning(f"Server '{server_name}' not found in servers: {servers.keys()}")
        raise ValueError(f"Server '{server_name}' not found")
    async with mcp_session_context(server_params) as session:
        result = await session.call_tool(tool_name, arguments)
        logger.debug(f"Tool call result: meta={result.meta}, content={result.content}, isError={result.isError}")
        if result.isError:
            raise RuntimeError(str(result.content))
        processed_content = parse_text_content(result.content)
        logger.debug(f"Processed content: {processed_content}")
        return processed_content

@create_tool
def list_servers() -> List[str]:
    """List all configured MCP servers.

    Returns:
        A list of server names.
        Example: ['sqlite', 'mysql']
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
        Dict containing tool details:
        - 'name': The tool's name.
        - 'description': A description of the tool's purpose and usage.
        - 'arguments': List of ToolArgument instances.
        - 'return_type': Return type based on server metadata or default 'Any'.
        - 'return_description': Detailed description of the return value with examples.
        - 'is_async': Boolean indicating if the tool is asynchronous.
    """
    logger.debug(f"Fetching details for tool '{tool_name}' on server '{server_name}'")
    if server_name in tools_cache:
        tools_result = tools_cache[server_name]
        logger.debug(f"Using cached tools_result for server '{server_name}'")
    else:
        logger.debug(f"No cache found for server '{server_name}', fetching from server")
        async with mcp_session_context(server_params) as session:
            tools_result = await session.list_tools()
            tools_cache[server_name] = tools_result  # Cache for future use
            logger.debug(f"Cached tools_result for server '{server_name}'")

    logger.debug(f"Raw tools_result from MCP server: {tools_result}")
    logger.debug(f"Number of tools returned: {len(tools_result.tools)}")
    for tool in tools_result.tools:
        logger.debug(f"Examining tool: {tool.name}, full object: {vars(tool) if hasattr(tool, '__dict__') else str(tool)}")
        if tool.name == tool_name:
            args = normalize_args(tool)
            # Use server-provided return type if available, otherwise default to 'Any'
            return_type = getattr(tool, 'return_type', 'Any') if hasattr(tool, 'return_type') else 'Any'
            return_desc = getattr(tool, 'return_description', "The result of the tool execution, type varies by tool.") if hasattr(tool, 'return_description') else "The result of the tool execution, type varies by tool.\nExample: Could be a list, dictionary, or string depending on the tool."

            tool_details = {
                'name': tool.name,
                'description': (
                    f"{getattr(tool, 'description', f'Tool {tool_name} from {server_name}')}\n"
                    "Note: This tool is asynchronous and must be awaited using `await` in an async context."
                ),
                'arguments': args,
                'return_type': return_type,
                'return_description': return_desc,
                'is_async': True
            }
            logger.debug(f"Tool details constructed for '{tool_name}': {tool_details}")
            return tool_details

    logger.warning(f"Tool '{tool_name}' not found in server response")
    return {}

def normalize_args(tool: Any) -> List[ToolArgument]:
    """Normalize tool arguments into a consistent schema.

    Args:
        tool: The tool object from the MCP server response.

    Returns:
        List of ToolArgument instances.
    """
    args = []
    arg_list = None
    if hasattr(tool, 'inputSchema') and tool.inputSchema:
        arg_list = tool.inputSchema.get('properties', {})
        required_args = getattr(tool.inputSchema, 'required', [])
        logger.debug(f"Found 'inputSchema' attribute: {tool.inputSchema}")
    elif hasattr(tool, 'arguments') and tool.arguments:
        arg_list = tool.arguments
        required_args = getattr(tool, 'required', [])
        logger.debug(f"Found 'arguments' attribute: {arg_list}")
    elif hasattr(tool, 'params') and tool.params:
        arg_list = tool.params
        required_args = getattr(tool, 'required', [])
        logger.debug(f"Found 'params' attribute: {arg_list}")
    elif hasattr(tool, 'input_schema') and tool.input_schema:
        arg_list = tool.input_schema
        required_args = getattr(tool, 'required', [])
        logger.debug(f"Found 'input_schema' attribute: {arg_list}")

    if arg_list:
        logger.debug(f"Processing {len(arg_list)} arguments for tool '{tool.name}'")
        for arg_name, arg_details in arg_list.items() if isinstance(arg_list, dict) else enumerate(arg_list):
            logger.debug(f"Argument '{arg_name}' raw data: {arg_details}")
            try:
                if isinstance(arg_list, dict):
                    # Dictionary format from inputSchema 'properties'
                    name = arg_name
                    arg_type = arg_details.get('type', 'str')
                    description = arg_details.get('description', f"Argument for {tool.name}")
                    required = name in required_args
                    default = arg_details.get('default', None)
                    example = arg_details.get('example', None)
                    logger.debug(f"Parsed dict arg: name={name}, type={arg_type}, desc={description}, req={required}, def={default}, ex={example}")
                else:
                    # List format (assuming objects)
                    name = getattr(arg_details, 'name', f"arg_{len(args) + 1}")
                    arg_type = getattr(arg_details, 'type', 'str')
                    description = getattr(arg_details, 'description', f"Argument for {tool.name}")
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
                logger.debug(f"Added argument: {name} to tool '{tool.name}'")
            except Exception as e:
                logger.warning(f"Failed to parse argument '{arg_name}' for '{tool.name}': {str(e)}")
                args.append(ToolArgument(
                    name=f"arg_{len(args) + 1}",
                    arg_type="str",
                    description=f"Unknown argument for {tool.name}",
                    required=True
                ))
                logger.debug("Added default argument due to parsing error")
    else:
        logger.debug(f"No argument attributes found for tool '{tool.name}' in server response")
    return args

async def create_dynamic_tool(server_name: str, tool_name: str, server_params: StdioServerParameters):
    """Create a dynamic tool based on MCP server tool definition, supporting only named parameters.

    Args:
        server_name: The name of the server hosting the tool.
        tool_name: The name of the tool to create.
        server_params: Parameters for establishing a session with the server.

    Returns:
        A Tool instance configured for asynchronous execution, or None if creation fails.
        
    Note:
        This function generates a tool that only accepts named parameters (e.g., `key=value`) as
        keyword arguments. Positional arguments are not supported to ensure compatibility with
        MCP server expectations and to maintain clarity in argument passing. Use the tool with
        explicit argument names as specified in its arguments list (accessible via `tool.arguments`).
    """
    logger.debug(f"Creating dynamic tool for server '{server_name}' and tool '{tool_name}'")
    tool_details = await fetch_tool_details(server_name, tool_name, server_params)
    
    if not tool_details:
        logger.warning(f"No details found for tool '{tool_name}' on server '{server_name}'")
        return None

    async def tool_func(**kwargs):
        logger.debug(f"Executing tool '{tool_name}' on '{server_name}' with kwargs: {kwargs}")
        async with mcp_session_context(server_params) as session:
            result = await session.call_tool(tool_name, kwargs)
            logger.debug(f"Tool execution result: meta={result.meta}, content={result.content}, isError={result.isError}, type={type(result.content)}")
            if result.isError:
                raise RuntimeError(str(result.content))
            processed_content = parse_text_content(result.content)
            logger.debug(f"Processed content for '{tool_name}': {processed_content}")
            return processed_content

    tool = create_tool(tool_func)
    # Use server-prefixed name to avoid conflicts
    original_name = f"{server_name}_{tool_name}"
    tool.name = f"{server_name}_{sanitize_name(tool_name)}"
    tool.original_name = original_name  # Store original name for reference
    tool.description = (
        f"{tool_details.get('description', f'Dynamic tool {tool_name} from {server_name}')}\n"
        "Important: This tool only supports named parameters (e.g., `arg_name=value`). "
        "Positional arguments are not allowed. Refer to the tool's `arguments` attribute for valid parameter names."
    )
    tool.arguments = tool_details.get('arguments', [])
    tool.return_type = tool_details.get('return_type', 'Any')
    tool.return_description = tool_details.get('return_description', "The result of the tool execution, type varies by tool.")
    tool.is_async = tool_details.get('is_async', True)
    tool.toolbox_name = f"dynamic_{server_name}"
    logger.debug(f"Dynamic tool created: name={tool.name}, original_name={tool.original_name}, args={tool.arguments}, toolbox={tool.toolbox_name}, is_async={tool.is_async}")
    return tool

# **Toolbox Initialization**
async def fetch_and_register_tools(server_name: str, server_params: StdioServerParameters, registry: ToolRegistry) -> None:
    """Fetch and register tools for a single server.

    Args:
        server_name: The name of the server.
        server_params: Parameters for the server.
        registry: ToolRegistry instance to register tools.
    """
    logger.debug(f"Processing server: {server_name}")
    try:
        server_tools = await mcp_list_tools.async_execute(server_name=server_name)
        logger.debug(f"Tools listed for '{server_name}': {server_tools}")
        if f"Error: Server '{server_name}' not found" in server_tools:
            logger.error(f"Server '{server_name}' not found")
            return

        for tool_name in server_tools:
            original_unique_tool_name = f"{server_name}_{tool_name}"
            unique_tool_name = f"{server_name}_{sanitize_name(tool_name)}"
            logger.debug(f"Creating dynamic tool: {unique_tool_name} (original: {original_unique_tool_name})")
            
            tool = await create_dynamic_tool(server_name, tool_name, server_params)
            if tool:
                key = (tool.toolbox_name, tool.name)
                if key not in registry.tools:
                    registry.register(tool)
                    logger.debug(f"Registered dynamic tool: {unique_tool_name} with args: {tool.arguments}")
                toolbox["tools"][unique_tool_name] = tool
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
        config_path = os.path.join(os.getenv("MCP_CONFIG_DIR", "./config"), f"{server_name}.json")
        try:
            config = load_mcp_config(config_path)
            explicit_tools = config.get("tools", [])
            logger.debug(f"Config-defined tools for '{server_name}': {explicit_tools}")
            for tool_config in explicit_tools:
                mcp_tool_name = tool_config["name"]
                original_unique_tool_name = f"{server_name}_{mcp_tool_name}"
                unique_tool_name = f"{server_name}_{sanitize_name(mcp_tool_name)}"
                if unique_tool_name not in toolbox["tools"]:
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
                        toolbox["tools"][unique_tool_name] = tool
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

async def create_all_tools(registry: ToolRegistry) -> Dict[str, Any]:
    """Create all tools by querying MCP servers dynamically in parallel and track their state.

    Args:
        registry: ToolRegistry instance to register tools.

    Returns:
        Dictionary of created tools.
    """
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

    # Add dynamic tools from each server in parallel
    tasks = []
    for server_name, server_params in servers.items():
        tasks.append(fetch_and_register_tools(server_name, server_params, registry))
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.debug(f"Tool creation completed. Total tools: {len(toolbox['tools'])}")
    return toolbox["tools"]

async def refresh_tools_cache(server_name: str) -> None:
    """Refresh the tools cache for a specific server.

    Args:
        server_name: The name of the server to refresh tools for.
    """
    logger.debug(f"Refreshing tools cache for {server_name}")
    server_params = servers.get(server_name)
    if server_params:
        async with mcp_session_context(server_params) as session:
            tools_cache[server_name] = await session.list_tools()
            logger.info(f"Tools cache refreshed for {server_name}")
    else:
        logger.warning(f"Server '{server_name}' not found, skipping cache refresh")

async def initialize_toolbox(registry: ToolRegistry) -> None:
    """Initialize toolbox with proper async handling and log final state.

    Args:
        registry: ToolRegistry instance to register tools.
    """
    global _toolbox_initialized
    if _toolbox_initialized:
        logger.debug("MCP toolbox already initialized, skipping")
        return
    logger.debug("Initializing MCP toolbox")
    load_configs()
    toolbox["tools"] = await create_all_tools(registry)
    _toolbox_initialized = True
    logger.info("Toolbox initialization completed. Final tool states:")
    for tool_name, state in toolbox["state"].items():
        if state["status"] == "success":
            logger.info(f"Tool: {tool_name}, Status: {state['status']}, Toolbox: {state['toolbox_name']}")
        else:
            logger.warning(f"Tool: {tool_name}, Status: {state['status']}, Toolbox: {state['toolbox_name']}, Error: {state['error']}")

# **Main Execution (Test Suite Only)**
if __name__ == "__main__":
    logger.info("Starting MCP toolbox test suite")
    async def test_toolbox():
        from quantalogic.codeact.tools_manager import ToolRegistry
        registry = ToolRegistry()
        await initialize_toolbox(registry)
        
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

        dynamic_tool_name = f"{test_server}_{sanitize_name('read_query')}"
        if dynamic_tool_name in toolbox["tools"]:
            dynamic_result = await toolbox["tools"][dynamic_tool_name].async_execute(query="SELECT sqlite_version();")
            logger.info(f"SQLite version via dynamic tool: {dynamic_result}")

    asyncio.run(test_toolbox())
    logger.info("Test suite completed")