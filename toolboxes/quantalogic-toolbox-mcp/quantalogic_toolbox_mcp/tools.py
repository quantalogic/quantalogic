"""Toolbox for interacting with MCP servers with JSON-based configuration.

This module provides a generic adapter for interacting with multiple MCP servers,
configured via JSON files in a configurable directory (default: ./config). Each server has its own tools,
and core tools are provided to interact with any server by specifying its name.
Tools are automatically queried from servers during initialization with caching and refresh options.
"""

import ast
import asyncio
import hashlib
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
CONFIG_DIR = os.getenv("MCP_CONFIG_DIR", "./config")
_tools_cache = None  # Cache for get_tools() results

# **Utility Functions**
def parse_string_content(text: str) -> Any:
    """Parse a string into a Python object, trying JSON first, then AST, with enhanced error handling.

    Args:
        text: The string to parse.

    Returns:
        Parsed content as a Python type (e.g., list, dict, str). Returns original string if parsing fails.

    Note:
        Updated to handle unparsable content gracefully by returning the raw text as a fallback.
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
            logger.warning(f"Failed to parse content as JSON or Python literal: {e}. Returning raw text: {text[:50]}...")
            return text  # Fallback to raw string to avoid crashing

def parse_text_content(content: Any) -> Any:
    """Parse MCP tool response content into a usable Python type.

    Args:
        content: The raw content from the server response.

    Returns:
        Parsed content as a Python type (e.g., list, dict, str).
    """
    logger.debug(f"Parsing content: {str(content)[:50]}...")
    if isinstance(content, list):
        return [parse_text_content(item) for item in content]
    elif hasattr(content, 'text'):
        text_content = content.text
        return parse_string_content(text_content)
    elif isinstance(content, str):
        return parse_string_content(content)
    logger.debug(f"Content is already a native type: {content}")
    return content

def sanitize_name(name: str) -> str:
    """Sanitize a string to be a valid Python identifier."""
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    if keyword.iskeyword(sanitized):
        sanitized += '_'
    return sanitized

# **Configuration Loading Functions**
def compute_config_hash(config_dir: str) -> str:
    """Compute a hash based on the contents of all JSON config files in the directory, excluding the cache file."""
    hashes = []
    for filename in sorted(os.listdir(config_dir)):
        if filename.endswith(".json") and filename != "config_cache.json":
            config_path = os.path.join(config_dir, filename)
            try:
                with open(config_path, "rb") as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                hashes.append(file_hash)
            except FileNotFoundError:
                logger.debug(f"Config file {config_path} not found during hash computation, skipping")
    return hashlib.md5("".join(hashes).encode()).hexdigest()

def load_mcp_config(config_path: str) -> Dict[str, Any]:
    """Load MCP configuration from a JSON file with secret resolution."""
    logger.debug(f"Loading configuration from {config_path}")
    try:
        with open(config_path) as f:
            config = json.load(f)
        config = resolve_secrets(config)
        logger.info(f"Successfully loaded config from {config_path}: {config}")
        return config
    except FileNotFoundError as e:
        logger.error(f"Config file not found: {config_path} - {str(e)}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {config_path} - {str(e)}")
        raise

def resolve_secrets(config: Dict) -> Dict:
    """Resolve environment variable placeholders in a config dictionary.
    
    Recursively processes nested dictionaries and resolves environment variables
    in the format {{ env.VARIABLE_NAME }}.
    
    Args:
        config: The configuration dictionary to process
        
    Returns:
        The processed configuration with environment variables resolved
    """
    if not isinstance(config, dict):
        return config
        
    result = {}
    for key, value in config.items():
        if isinstance(value, str) and "{{ env." in value:
            env_var = value.split("{{ env.")[1].split("}}")[0].strip()
            env_value = os.getenv(env_var)
            if env_value is None:
                logger.warning(f"Environment variable '{env_var}' not found. This may cause API authentication failures.")
                # For API keys, provide a more specific message
                if "API_KEY" in env_var or "APIKEY" in env_var:
                    logger.error(f"Missing API key: '{env_var}'. Please set this environment variable before using this tool.")
                result[key] = value
            else:
                logger.debug(f"Resolved environment variable '{env_var}'")
                result[key] = env_value
        elif isinstance(value, dict):
            result[key] = resolve_secrets(value)
        elif isinstance(value, list):
            result[key] = [resolve_secrets(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result

def load_configs(config_dir: str = CONFIG_DIR) -> None:
    """Load all JSON config files from the specified directory into the servers dictionary."""
    global tools_cache
    cache_file = os.path.join(config_dir, "config_cache.json")
    current_hash = compute_config_hash(config_dir)

    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache_data = json.load(f)
            if cache_data.get("config_hash") == current_hash:
                servers.clear()
                tools_cache.clear()
                for server_name, server_data in cache_data["servers"].items():
                    # Create params dictionary with required fields
                    params = {
                        "command": server_data["command"],
                        "args": server_data["args"]
                    }
                    
                    # Add optional parameters if they exist and are not None
                    if "env" in server_data and server_data["env"] is not None:
                        params["env"] = server_data["env"]
                        logger.debug(f"Loaded environment variables for server {server_name} from cache: {list(params['env'].keys())}")
                        
                    if "cwd" in server_data and server_data["cwd"] is not None:
                        params["cwd"] = server_data["cwd"]
                    
                    server_params = StdioServerParameters(**params)
                    servers[server_name] = server_params
                    tools_cache[server_name] = type('ToolsResult', (), {'tools': [
                        type('Tool', (), {
                            'name': name,
                            'description': details.get('description', f'Tool {name} from {server_name}'),
                            'inputSchema': {
                                'properties': {
                                    arg['name']: {
                                        'type': arg.get('type', 'str'),
                                        'description': arg.get('description', ''),
                                        'default': arg.get('default', None),
                                        'example': arg.get('example', None)
                                    } for arg in details.get('arguments', [])
                                },
                                'required': [arg['name'] for arg in details.get('arguments', []) if arg.get('required', False)]
                            },
                            'return_type': details.get('return_type', 'Any')
                        })()
                        for name, details in server_data.get("tools", {}).items()
                    ]})()
                logger.info("Loaded servers and tools from cache")
                return
        except Exception as e:
            logger.warning(f"Failed to load cache: {str(e)}, reloading configs")

    servers.clear()
    tools_cache.clear()
    if not os.path.exists(config_dir):
        logger.warning(f"Config directory {config_dir} does not exist, creating it")
        os.makedirs(config_dir)

    cache_tools = {}
    for filename in os.listdir(config_dir):
        if filename.endswith(".json") and filename != "config_cache.json":
            config_path = os.path.join(config_dir, filename)
            try:
                config = load_mcp_config(config_path)
                server_configs = config.get("mcpServers", config.get("mcp_servers", {config.get("server_name", filename[:-5]): config}))
                for server_name, server_data in server_configs.items():
                    # Create server parameters with environment variables if provided
                    params = {
                        "command": server_data["command"],
                        "args": server_data["args"]
                    }
                    
                    # Add environment variables if specified
                    if "env" in server_data:
                        params["env"] = server_data["env"]
                        logger.debug(f"Using environment variables for server {server_name}: {list(params['env'].keys())}")
                    
                    # Add working directory if specified
                    if "cwd" in server_data:
                        params["cwd"] = server_data["cwd"]
                    
                    server_params = StdioServerParameters(**params)
                    servers[server_name] = server_params
                    cache_tools[server_name] = {}
                    try:
                        server_tools = asyncio.run(mcp_list_tools(server_name))
                        for tool_name in server_tools:
                            tool_details = asyncio.run(fetch_tool_details(server_name, tool_name, server_params))
                            if tool_details:
                                cache_tools[server_name][tool_name] = tool_details
                    except Exception as e:
                        logger.warning(f"Failed to fetch tools for server '{server_name}': {str(e)}")
                    for tool_name, tool_config in server_data.get("tools", {}).items():
                        cache_tools[server_name][tool_name] = tool_config
            except Exception as e:
                logger.error(f"Failed to load config {config_path}: {str(e)}")

    cache_data = {
        "config_hash": current_hash,
        "servers": {
            name: {
                "command": params.command,
                "args": params.args,
                "env": params.env if hasattr(params, 'env') and params.env else None,
                "cwd": params.cwd if hasattr(params, 'cwd') and params.cwd else None,
                "tools": cache_tools.get(name, {})
            }
            for name, params in servers.items()
        }
    }
    try:
        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)
        logger.info("Saved servers and tools to cache")
    except Exception as e:
        logger.warning(f"Failed to save cache: {str(e)}")

# **MCP Session Management**
@asynccontextmanager
async def mcp_session_context(server_params: StdioServerParameters) -> AsyncIterator[ClientSession]:
    """Async context manager for MCP sessions with separate handling for Docker and direct commands.

    Args:
        server_params: Parameters for the MCP server session, including command and args.

    Yields:
        An initialized ClientSession for interacting with the MCP server.

    Raises:
        RuntimeError: If Docker is unavailable or session initialization fails after retries.

    Note:
        Added retry mechanism for direct commands to match Docker logic, improving robustness.
        Handles GeneratorExit exceptions gracefully to prevent session context issues.
    """
    logger.debug(f"Starting session with params: {server_params}")

    try:
        if server_params.command == "docker":
            proc = await asyncio.create_subprocess_exec(
                "docker", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            logger.debug(f"Docker version check: returncode={proc.returncode}, stdout={stdout.decode()}, stderr={stderr.decode()}")
            if proc.returncode != 0:
                raise RuntimeError("Docker is not available or not running")

            try:
                async with stdio_client(server_params) as (read, write):
                    try:
                        async with ClientSession(read, write) as session:
                            for attempt in range(5):
                                try:
                                    await session.initialize()
                                    logger.debug("Docker session initialized successfully")
                                    yield session
                                    return
                                except Exception as e:
                                    if attempt < 4:
                                        logger.debug(f"Docker session init failed, retrying in 1s: {str(e)}")
                                        await asyncio.sleep(1)
                                    else:
                                        logger.error(f"Docker session init failed after 5 attempts: {str(e)}")
                                        raise RuntimeError(f"Failed to initialize Docker session: {str(e)}")
                    except GeneratorExit:
                        logger.debug("Generator exited during Docker session")
                        # Let the GeneratorExit propagate after cleanup
                        raise
                    except Exception as e:
                        logger.error(f"Error in Docker ClientSession: {str(e)}")
                        raise
            except GeneratorExit:
                logger.debug("Generator exited during Docker stdio_client")
                # Let the GeneratorExit propagate after cleanup
                raise
            except Exception as e:
                logger.error(f"Error in Docker stdio_client: {str(e)}")
                raise
        else:
            # Direct command logic with retries
            try:
                async with stdio_client(server_params) as (read, write):
                    try:
                        async with ClientSession(read, write) as session:
                            for attempt in range(5):
                                try:
                                    await session.initialize()
                                    logger.debug("Direct session initialized successfully")
                                    yield session
                                    return
                                except Exception as e:
                                    if attempt < 4:
                                        logger.debug(f"Direct session init failed, retrying in 1s: {str(e)}")
                                        await asyncio.sleep(1)
                                    else:
                                        logger.error(f"Direct session init failed after 5 attempts: {str(e)}")
                                        raise RuntimeError(f"Failed to initialize direct session: {str(e)}")
                    except GeneratorExit:
                        logger.debug("Generator exited during direct session")
                        # Let the GeneratorExit propagate after cleanup
                        raise
                    except Exception as e:
                        logger.error(f"Error in direct ClientSession: {str(e)}")
                        raise
            except GeneratorExit:
                logger.debug("Generator exited during direct stdio_client")
                # Let the GeneratorExit propagate after cleanup
                raise
            except Exception as e:
                logger.error(f"Error in direct stdio_client: {str(e)}")
                raise
    except GeneratorExit:
        logger.debug("Generator exited during mcp_session_context")
        # Let the GeneratorExit propagate
        raise
    except Exception as e:
        logger.error(f"Unhandled error in mcp_session_context: {str(e)}")
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
    """List available resources on the specified MCP server."""
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
    """List available tools on the specified MCP server."""
    logger.debug(f"Listing tools for server: {server_name}")
    server_params = servers.get(server_name)
    if not server_params:
        logger.warning(f"Server '{server_name}' not found in servers: {servers.keys()}")
        raise ValueError(f"Server '{server_name}' not found")
    try:
        async with mcp_session_context(server_params) as session:
            tools_result = await session.list_tools()
            tools_cache[server_name] = tools_result
            tool_names = [tool.name for tool in tools_result.tools]
            logger.debug(f"Tool names extracted: {tool_names}")
            return tool_names
    except Exception as e:
        logger.error(f"Failed to list tools for {server_name}: {str(e)}")
        raise RuntimeError(f"Could not connect to server '{server_name}': {str(e)}")

async def mcp_call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call a specific tool on the specified MCP server.

    Note:
        Enhanced logging to capture tool execution details and errors.
    """
    logger.debug(f"Calling tool '{tool_name}' on server '{server_name}' with args: {arguments}")
    server_params = servers.get(server_name)
    if not server_params:
        logger.warning(f"Server '{server_name}' not found in servers: {servers.keys()}")
        raise ValueError(f"Server '{server_name}' not found")
    try:
        async with mcp_session_context(server_params) as session:
            result = await session.call_tool(tool_name, arguments)
            logger.debug(f"Tool call result: meta={result.meta}, content={result.content}, isError={result.isError}")
            if result.isError:
                raise RuntimeError(str(result.content))
            processed_content = parse_text_content(result.content)
            logger.debug(f"Processed content: {processed_content}")
            return processed_content
    except Exception as e:
        logger.error(f"Failed to call tool '{tool_name}' on server '{server_name}': {str(e)}")
        raise

async def list_servers() -> List[str]:
    """List all configured MCP servers."""
    logger.debug("Listing all configured servers")
    server_list = list(servers.keys())
    logger.debug(f"Server list: {server_list}")
    return server_list

# **Dynamic Tool Class**
class DynamicTool:
    """A callable class representing a dynamic tool for MCP servers."""
    def __init__(self, server_name: str, tool_name: str, tool_config: Dict[str, Any]):
        self.name = f"{server_name}_{sanitize_name(tool_name)}"
        self.description = tool_config.get('description', f'Execute {tool_name} on {server_name}')
        self.arguments = tool_config.get("arguments", [])
        self.return_type = tool_config.get("return_type", "Any")
        self.server_name = server_name
        self.tool_name = tool_name
        self.tool_config = tool_config

    async def __call__(self, **kwargs) -> Any:
        logger.debug(f"Executing dynamic tool '{self.name}' with args: {kwargs}")
        return await mcp_call_tool(self.server_name, self.tool_name, kwargs)

    async def async_execute(self, **kwargs) -> Any:
        return await self(**kwargs)

    def to_docstring(self) -> str:
        args_str = ", ".join(f"{arg['name']}: {arg['type']}" for arg in self.arguments)
        toolbox_name = "quantalogic_toolbox_mcp"
        return f"{toolbox_name}.{self.name}({args_str}) -> {self.return_type}\n{self.description}"

    def __repr__(self) -> str:
        """Return a string representation of the DynamicTool instance."""
        return f"<DynamicTool {self.name}>"

# **Dynamic Tool Creation**
async def fetch_tool_details(server_name: str, tool_name: str, server_params: StdioServerParameters) -> Dict[str, Any]:
    """Fetch detailed tool information from MCP server dynamically."""
    logger.debug(f"Fetching details for tool '{tool_name}' on server '{server_name}'")
    if server_name in tools_cache:
        tools_result = tools_cache[server_name]
    else:
        async with mcp_session_context(server_params) as session:
            tools_result = await session.list_tools()
            tools_cache[server_name] = tools_result

    for tool in tools_result.tools:
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
    """Normalize tool arguments into a consistent schema."""
    args = []
    arg_list = None
    if hasattr(tool, 'inputSchema') and tool.inputSchema:
        arg_list = tool.inputSchema.get('properties', {})
        required_args = getattr(tool.inputSchema, 'required', [])
    elif hasattr(tool, 'arguments') and tool.arguments:
        arg_list = tool.arguments
        required_args = getattr(tool, 'required', [])
    elif hasattr(tool, 'params') and tool.params:
        arg_list = tool.params
        required_args = getattr(tool, 'required', [])
    elif hasattr(tool, 'input_schema') and tool.input_schema:
        arg_list = tool.input_schema
        required_args = getattr(tool, 'required', [])

    if arg_list:
        for arg_name, arg_details in arg_list.items() if isinstance(arg_list, dict) else enumerate(arg_list):
            if isinstance(arg_list, dict):
                name = arg_name
                arg_type = arg_details.get('type', 'str')
                description = arg_details.get('description', f"Argument for {tool.name}")
                required = name in required_args
                default = arg_details.get('default', None)
                example = arg_details.get('example', None)
            else:
                name = getattr(arg_details, 'name', f"arg_{len(args) + 1}")
                arg_type = getattr(arg_details, 'type', 'str')
                description = getattr(arg_details, 'description', f"Argument for {tool.name}")
                required = getattr(arg_details, 'required', True)
                default = getattr(arg_details, 'default', None)
                example = getattr(arg_details, 'example', None)
            args.append({
                'name': name,
                'type': arg_type,
                'description': description,
                'required': required,
                'default': default,
                'example': example
            })
    return args

# **Tool List Generation**
def get_tools() -> List:
    """Return a list of core tools and dynamically created specific tool wrappers."""
    global _tools_cache
    if _tools_cache is not None:
        logger.debug("Returning cached tools")
        return _tools_cache

    tools = [
        mcp_list_resources,
        mcp_list_tools,
        mcp_call_tool,
        list_servers,
    ]

    config_path = os.path.join(CONFIG_DIR, "mcp.json")
    if os.path.exists(config_path):
        try:
            config = load_mcp_config(config_path)
            server_configs = config.get("mcpServers", {})
            for server_name, server_data in server_configs.items():
                for tool_name, tool_config in server_data.get("tools", {}).items():
                    tool = DynamicTool(server_name, tool_name, tool_config)
                    tools.append(tool)
                if server_name in tools_cache:
                    for tool in tools_cache[server_name].tools:
                        tool_config = {
                            'name': tool.name,
                            'description': getattr(tool, 'description', f'Tool {tool.name} from {server_name}'),
                            'arguments': normalize_args(tool),
                            'return_type': getattr(tool, 'return_type', 'Any')
                        }
                        tool_instance = DynamicTool(server_name, tool.name, tool_config)
                        tools.append(tool_instance)
                else:
                    server_params = servers.get(server_name)
                    if server_params:
                        try:
                            server_tools = asyncio.run(mcp_list_tools(server_name))
                            for tool_name in server_tools:
                                tool_details = asyncio.run(fetch_tool_details(server_name, tool_name, server_params))
                                if tool_details:
                                    tool = DynamicTool(server_name, tool_name, tool_details)
                                    tools.append(tool)
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