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
CONFIG_DIR = os.getenv("MCP_CONFIG_DIR", "./config")
_tools_cache = None  # Cache for get_tools() results

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

def load_configs(config_dir: str = CONFIG_DIR) -> None:
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

# **Core Tools**
async def mcp_list_resources(server_name: str) -> List[str]:
    """List available resources on the specified MCP server.

    Args:
        server_name (str): The name of the server to list resources from.

    Returns:
        List[str]: A list of resource names.
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

async def mcp_list_tools(server_name: str) -> List[str]:
    """List available tools on the specified MCP server.

    Args:
        server_name (str): The name of the server to list tools from.

    Returns:
        List[str]: A list of tool names.
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

async def mcp_call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call a specific tool on the specified MCP server.

    Args:
        server_name (str): The name of the server to call the tool on.
        tool_name (str): The name of the tool to call.
        arguments (Dict[str, Any]): A dictionary of arguments to pass to the tool.

    Returns:
        Any: The result of the tool execution, type depends on the tool called.
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

async def list_servers() -> List[str]:
    """List all configured MCP servers.

    Returns:
        List[str]: A list of server names.
        Example: ['sqlite', 'mysql']
    """
    logger.debug("Listing all configured servers")
    server_list = list(servers.keys())
    logger.debug(f"Server list: {server_list}")
    return server_list

# **Dynamic Tool Class**
class DynamicTool:
    """A callable class representing a dynamic tool for MCP servers.

    This class encapsulates a tool hosted on an MCP server, allowing it to be called
    asynchronously with specified arguments. It provides metadata required for tool
    registration and execution without external dependencies.

    Attributes:
        name (str): The unique identifier for the tool (e.g., 'server_toolname').
        description (str): A description of the tool's purpose and usage.
        arguments (List[Dict[str, Any]]): List of argument definitions, each with name, type, description, required, default, and example.
        return_type (str): The expected type of the tool's return value.
        server_name (str): The name of the MCP server hosting the tool.
        tool_name (str): The original tool name on the server.
        tool_config (Dict[str, Any]): Configuration data for the tool.
    """
    def __init__(self, server_name: str, tool_name: str, tool_config: Dict[str, Any]):
        self.name = f"{server_name}_{sanitize_name(tool_name)}"
        self.description = tool_config.get('description', f'Execute {tool_name} on {server_name}')
        self.arguments = tool_config.get("arguments", [])
        self.return_type = tool_config.get("return_type", "Any")
        self.server_name = server_name
        self.tool_name = tool_name
        self.tool_config = tool_config

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool by invoking mcp_call_tool with the server and tool name.

        Args:
            **kwargs: Keyword arguments to pass to the tool, matching the expected arguments.

        Returns:
            Any: The result of the tool execution, as returned by the MCP server.

        Example:
            result = await tool_name(param1="value1", param2=42)
        """
        logger.debug(f"Executing dynamic tool '{self.name}' with args: {kwargs}")
        return await mcp_call_tool(self.server_name, self.tool_name, kwargs)

    async def async_execute(self, **kwargs) -> Any:
        """Execute the tool by invoking the __call__ method.

        Args:
            **kwargs: Keyword arguments to pass to the tool, matching the expected arguments.

        Returns:
            Any: The result of the tool execution, as returned by the MCP server.
        """
        return await self(**kwargs)

    def to_docstring(self) -> str:
        """Generate a docstring-like representation of the tool.

        Returns:
            str: A string describing the tool's name, description, and arguments.
        """
        args_str = ", ".join(
            f"{arg['name']}: {arg['type']}" for arg in self.arguments
        )
        toolbox_name = "quantalogic_toolbox_mcp"
        return f"{toolbox_name}.{self.name}({args_str}) -> {self.return_type}\n{self.description}"

    def __repr__(self) -> str:
        return f"<DynamicTool {self.name}>"

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
        - 'arguments': List of argument dictionaries.
        - 'return_type': Return type based on server metadata or default 'Any'.
    """
    logger.debug(f"Fetching details for tool '{tool_name}' on server '{server_name}'")
    if server_name in tools_cache:
        tools_result = tools_cache[server_name]
        logger.debug(f"Using cached tools_result for server '{server_name}'")
    else:
        logger.debug(f"No cache found for server '{server_name}', fetching from server")
        async with mcp_session_context(server_params) as session:
            tools_result = await session.list_tools()
            tools_cache[server_name] = tools_result
            logger.debug(f"Cached tools_result for server '{server_name}'")

    logger.debug(f"Raw tools_result from MCP server: {tools_result}")
    logger.debug(f"Number of tools returned: {len(tools_result.tools)}")
    for tool in tools_result.tools:
        logger.debug(f"Examining tool: {tool.name}, full object: {vars(tool) if hasattr(tool, '__dict__') else str(tool)}")
        if tool.name == tool_name:
            args = normalize_args(tool)
            return_type = getattr(tool, 'return_type', 'Any') if hasattr(tool, 'return_type') else 'Any'
            tool_details = {
                'name': tool.name,
                'description': getattr(tool, 'description', f'Tool {tool_name} from {server_name}'),
                'arguments': args,
                'return_type': return_type
            }
            logger.debug(f"Tool details constructed for '{tool_name}': {tool_details}")
            return tool_details

    logger.warning(f"Tool '{tool_name}' not found in server response")
    return {}

def normalize_args(tool: Any) -> List[Dict[str, Any]]:
    """Normalize tool arguments into a consistent schema.

    Args:
        tool: The tool object from the MCP server response.

    Returns:
        List of argument dictionaries with name, type, description, etc.
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
                    name = arg_name
                    arg_type = arg_details.get('type', 'str')
                    description = arg_details.get('description', f"Argument for {tool.name}")
                    required = name in required_args
                    default = arg_details.get('default', None)
                    example = arg_details.get('example', None)
                    logger.debug(f"Parsed dict arg: name={name}, type={arg_type}, desc={description}, req={required}, def={default}, ex={example}")
                else:
                    name = getattr(arg_details, 'name', f"arg_{len(args) + 1}")
                    arg_type = getattr(arg_details, 'type', 'str')
                    description = getattr(arg_details, 'description', f"Argument for {tool.name}")
                    required = getattr(arg_details, 'required', True)
                    default = getattr(arg_details, 'default', None)
                    example = getattr(arg_details, 'example', None)
                    logger.debug(f"Parsed object arg: name={name}, type={arg_type}, desc={description}, req={required}, def={default}, ex={example}")
                
                args.append({
                    'name': name,
                    'type': arg_type,
                    'description': description,
                    'required': required,
                    'default': default,
                    'example': example
                })
                logger.debug(f"Added argument: {name} to tool '{tool.name}'")
            except Exception as e:
                logger.warning(f"Failed to parse argument '{arg_name}' for '{tool.name}': {str(e)}")
                args.append({
                    'name': f"arg_{len(args) + 1}",
                    'type': 'str',
                    'description': f"Unknown argument for {tool.name}",
                    'required': True
                })
                logger.debug("Added default argument due to parsing error")
    else:
        logger.debug(f"No argument attributes found for tool '{tool.name}' in server response")
    return args

# **Tool List Generation**
def get_tools() -> List:
    """Return a list of core tools and dynamically created specific tool wrappers.

    Returns:
        List: A list of callable objects representing the tools.
    """
    global _tools_cache
    if _tools_cache is not None:
        logger.debug("Returning cached tools")
        return _tools_cache

    logger.debug("Generating tool list")
    tools = [
        mcp_list_resources,
        mcp_list_tools,
        mcp_call_tool,
        list_servers,
    ]
    
    # Load configuration
    config_path = os.path.join(CONFIG_DIR, "mcp.json")
    if os.path.exists(config_path):
        try:
            config = load_mcp_config(config_path)
            server_configs = config.get("mcpServers", {})
            for server_name, server_data in server_configs.items():
                # Handle explicitly defined tools in config
                for tool_name, tool_config in server_data.get("tools", {}).items():
                    tool = DynamicTool(server_name, tool_name, tool_config)
                    tools.append(tool)
                    logger.debug(f"Added config-defined tool: {tool.name}")
                
                # Query server for additional tools
                server_params = servers.get(server_name)
                if server_params:
                    try:
                        server_tools = asyncio.run(mcp_list_tools(server_name=server_name))
                        logger.debug(f"Tools listed for '{server_name}': {server_tools}")
                        for tool_name in server_tools:
                            tool_details = asyncio.run(fetch_tool_details(server_name, tool_name, server_params))
                            if tool_details:
                                tool = DynamicTool(server_name, tool_name, tool_details)
                                tools.append(tool)
                                logger.debug(f"Added dynamically fetched tool: {tool.name}")
                    except Exception as e:
                        logger.warning(f"Failed to query tools for server '{server_name}': {str(e)}")
        except Exception as e:
            logger.error(f"Failed to load dynamic tools from {config_path}: {e}")
    else:
        logger.warning(f"Configuration file {config_path} not found, using core tools only")
    
    _tools_cache = tools
    logger.info(f"Returning {len(tools)} tools: {[tool.name if hasattr(tool, 'name') else tool.__name__ for tool in tools]}")
    return tools

# **Module Initialization**
load_configs()