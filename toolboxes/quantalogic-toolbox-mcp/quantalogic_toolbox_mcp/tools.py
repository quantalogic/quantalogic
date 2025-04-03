import json
import os
import asyncio
import logging
import sys
from typing import Any, Dict, List, AsyncGenerator, Optional

# Configure logging with maximum detail
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initial diagnostic log to confirm script execution
logger.debug("Script 'tools.py' started execution")

# Check for required packages
missing_packages = []
try:
    from quantalogic.tools.tool import Tool, ToolArgument, ToolDefinition
except ImportError:
    logger.error("Failed to import from quantalogic.tools.tool. Please install the quantalogic package.")
    missing_packages.append("quantalogic")

try:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
except ImportError:
    logger.error("Failed to import from mcp. Please install the mcp package.")
    missing_packages.append("mcp")

if missing_packages:
    logger.critical(f"Missing required packages: {', '.join(missing_packages)}")
    logger.info("Try installing with: pip install " + " ".join(missing_packages))
    print(f"Error: Missing required packages: {', '.join(missing_packages)}")
    print(f"Try installing with: pip install " + " ".join(missing_packages))
    sys.exit(1)

class McpTool(Tool):
    """A Tool subclass for executing MCP remote tools with dynamic metadata and streaming support."""
    def __init__(self, mcp_session: ClientSession, remote_tool_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mcp_session = mcp_session
        self.remote_tool_name = remote_tool_name

    async def async_execute(self, **kwargs: Any) -> Any:
        """Execute the MCP tool asynchronously."""
        try:
            logger.debug(f"Executing MCP tool '{self.remote_tool_name}' with args: {kwargs}")
            result = await self.mcp_session.call_tool(self.remote_tool_name, kwargs)
            return result
        except Exception as e:
            logger.error(f"Failed to execute '{self.remote_tool_name}': {str(e)}")
            raise RuntimeError(f"MCP tool execution failed: {str(e)}")

    def execute(self, **kwargs: Any) -> Any:
        """Synchronous execution wrapper."""
        return asyncio.run(self.async_execute(**kwargs))

    async def stream_execute(self, **kwargs: Any) -> AsyncGenerator[Any, None]:
        """Stream results from the MCP tool."""
        try:
            logger.debug(f"Streaming MCP tool '{self.remote_tool_name}' with args: {kwargs}")
            async for chunk in self.mcp_session.stream_tool(self.remote_tool_name, kwargs):
                yield chunk
        except Exception as e:
            logger.error(f"Failed to stream '{self.remote_tool_name}': {str(e)}")
            raise RuntimeError(f"MCP tool streaming failed: {str(e)}")

class ConfigurableMcpToolbox:
    """A fully-featured Toolbox supporting 100% MCP client protocol via multiple JSON configurations."""
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.mcp_sessions: Dict[str, ClientSession] = {}
        self.resources: Dict[str, Dict] = {}
        self.prompts: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()

    async def load_json(self, json_path: str) -> None:
        """Load configuration from a JSON file with env var substitution."""
        logger.debug(f"Starting to load JSON config from '{json_path}'")
        try:
            with open(json_path, 'r') as f:
                raw_data = f.read()
            data = json.loads(self._substitute_env_vars(raw_data))
            logger.debug(f"Loaded JSON data: {json.dumps(data, indent=2)}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load '{json_path}': {str(e)}")
            raise ValueError(f"Invalid JSON file '{json_path}': {str(e)}")

        async with self._lock:
            for server_name, config in data.get("mcp_servers", {}).items():
                if server_name in self.mcp_sessions:
                    logger.warning(f"Overriding existing MCP server '{server_name}'")
                try:
                    transport_type = config.get("transport_type", "stdio").lower()
                    if transport_type != "stdio":
                        logger.warning(f"Only 'stdio' supported in this version; got '{transport_type}'")
                        transport_type = "stdio"
                    server_params = StdioServerParameters(
                        command=config.get("command", ""),
                        args=config.get("args", []),
                        env=config.get("env", {})
                    )
                    logger.debug(f"Attempting to start server '{server_name}' with params: {server_params}")
                    async with stdio_client(server_params) as stdio_transport:
                        stdio, write = stdio_transport
                        logger.debug(f"Stdio transport established for '{server_name}'")
                        session = ClientSession(stdio, write)
                        logger.debug(f"Initializing session for '{server_name}'")
                        try:
                            # Increased timeout to 30 seconds to allow more time for server initialization
                            await asyncio.wait_for(session.initialize(), timeout=30.0)
                            logger.debug(f"Session initialized successfully for '{server_name}'")
                        except asyncio.TimeoutError:
                            logger.error(f"Timeout waiting for '{server_name}' session initialization")
                            # Check stream status safely for anyio streams
                            logger.debug(f"Stdio _closed: {getattr(stdio, '_closed', 'N/A')}, Write _closed: {getattr(write, '_closed', 'N/A')}")
                            raise RuntimeError(f"MCP server '{server_name}' did not respond to initialization")
                        except Exception as e:
                            logger.error(f"Session initialization failed for '{server_name}': {str(e)}")
                            logger.exception("Detailed traceback:")
                            raise
                        self.mcp_sessions[server_name] = session
                        logger.info(f"Initialized MCP server '{server_name}' with stdio")
                except Exception as e:
                    logger.error(f"Failed to initialize '{server_name}': {str(e)}")
                    raise RuntimeError(f"Server initialization failed: {str(e)}")

        for resource in data.get("resources", []):
            resource_id = resource["id"]
            key = f"{server_name}.{resource_id}"
            if key in self.resources:
                logger.warning(f"Overriding resource '{key}'")
            self.resources[key] = resource
            logger.info(f"Loaded resource '{key}'")

        for prompt in data.get("prompts", []):
            prompt_name = prompt["name"]
            key = f"{server_name}.{prompt_name}"
            if key in self.prompts:
                logger.warning(f"Overriding prompt '{key}'")
            self.prompts[key] = prompt
            logger.info(f"Loaded prompt '{key}'")

        await self._load_or_sync_tools(data.get("tools", []), json_path)

    async def load_directory(self, directory_path: str) -> None:
        """Load all JSON files from a directory asynchronously."""
        logger.debug(f"Loading directory '{directory_path}'")
        if not os.path.isdir(directory_path):
            logger.error(f"Directory '{directory_path}' does not exist")
            raise ValueError(f"Directory '{directory_path}' does not exist")
        json_files = sorted([f for f in os.listdir(directory_path) if f.endswith(".json")])
        if not json_files:
            logger.warning(f"No JSON files found in '{directory_path}'")
            return
        
        for json_file in json_files:
            json_path = os.path.join(directory_path, json_file)
            await self.load_json(json_path)

    def load_directory_sync(self, directory_path: str) -> None:
        """Synchronous wrapper for loading a directory."""
        logger.debug(f"Starting synchronous load of directory '{directory_path}'")
        try:
            # Use absolute path if provided path is relative
            if not os.path.isabs(directory_path):
                # Get the directory where this script is located
                script_dir = os.path.dirname(os.path.abspath(__file__))
                abs_directory_path = os.path.join(script_dir, directory_path)
                if os.path.isdir(abs_directory_path):
                    directory_path = abs_directory_path
                    logger.debug(f"Using absolute path: {directory_path}")
            
            asyncio.run(self.load_directory(directory_path))
            logger.debug(f"Completed synchronous load of directory '{directory_path}'")
            logger.info(f"Loaded {len(self.tools)} tools")
        except Exception as e:
            logger.error(f"Failed to load directory '{directory_path}': {str(e)}")
            logger.exception("Detailed traceback:")
            raise

    async def _load_or_sync_tools(self, tools_data: List[Dict[str, Any]], source: str) -> None:
        """Load tools from JSON or sync with server metadata."""
        async with self._lock:
            for tool_data in tools_data:
                tool_name = tool_data["name"]
                impl = tool_data.get("implementation", {})
                if impl.get("type") != "mcp_tool":
                    logger.error(f"Tool '{tool_name}' in '{source}': Only 'mcp_tool' supported")
                    continue

                server_name = impl.get("server")
                if server_name not in self.mcp_sessions:
                    logger.error(f"Tool '{tool_name}' in '{source}': Unknown server '{server_name}'")
                    continue

                remote_tool_name = impl.get("tool_name")
                session = self.mcp_sessions[server_name]
                
                try:
                    tool_info = await self._get_tool_info(session, remote_tool_name)
                    if tool_name in self.tools:
                        logger.warning(f"Overriding existing tool '{tool_name}' from '{source}'")
                    self.tools[tool_name] = self._create_tool(tool_data, session, tool_info)
                    logger.info(f"Loaded tool '{tool_name}' from '{source}'")
                except Exception as e:
                    logger.error(f"Failed to sync tool '{tool_name}' from '{source}': {str(e)}")
                    logger.exception("Detailed traceback:")

    async def _get_tool_info(self, session: ClientSession, tool_name: str) -> Dict[str, Any]:
        """Fetch tool metadata from the MCP server."""
        try:
            logger.debug(f"Fetching tools from server session: {session}")
            response = await session.list_tools()
            tools_list = response.tools
            logger.info(f"Available tools from server '{session}': {[tool.name for tool in tools_list]}")
            for tool in tools_list:
                if tool.name == tool_name:
                    return {
                        "description": tool.description or "",
                        "arguments": [
                            ToolArgument(
                                name=arg["name"],
                                arg_type=arg.get("type", "str"),
                                description=arg.get("description", ""),
                                required=arg.get("required", False),
                                default=arg.get("default", None)
                            ) for arg in tool.input_schema.get("parameters", [])
                        ],
                        "return_type": tool.return_type or "str",
                        "return_description": tool.get("return_description", "Result from MCP tool")
                    }
            raise ValueError(f"Tool '{tool_name}' not found on server")
        except Exception as e:
            logger.error(f"Failed to fetch tools from server: {str(e)}")
            logger.exception("Detailed traceback:")
            raise

    def _create_tool(self, tool_data: Dict[str, Any], session: ClientSession, tool_info: Dict[str, Any]) -> Tool:
        """Create a Tool instance with synced metadata."""
        return McpTool(
            mcp_session=session,
            remote_tool_name=tool_data["implementation"]["tool_name"],
            name=tool_data["name"],
            description=tool_data.get("description", tool_info["description"]),
            arguments=tool_info["arguments"],
            return_type=tool_info["return_type"],
            return_description=tool_info["return_description"],
            is_async=True
        )

    def _substitute_env_vars(self, raw_json: str) -> str:
        """Substitute environment variables in JSON string (e.g., ${VAR})."""
        import re
        def replace_match(match):
            var_name = match.group(1)
            return os.getenv(var_name, f"${var_name}")
        return re.sub(r'\${([^}]+)}', replace_match, raw_json)

    async def add_server(self, server_name: str, config: Dict) -> None:
        """Add a new MCP server at runtime."""
        async with self._lock:
            if server_name in self.mcp_sessions:
                logger.warning(f"Overriding existing server '{server_name}'")
            try:
                transport_type = config.get("transport_type", "stdio").lower()
                server_params = StdioServerParameters(
                    command=config.get("command", ""),
                    args=config.get("args", []),
                    env=config.get("env", {})
                )
                async with stdio_client(server_params) as stdio_transport:
                    stdio, write = stdio_transport
                    session = ClientSession(stdio, write)
                    await session.initialize()
                    self.mcp_sessions[server_name] = session
                    logger.info(f"Added server '{server_name}' with stdio")
            except Exception as e:
                logger.error(f"Failed to add server '{server_name}': {str(e)}")
                raise RuntimeError(f"Server addition failed: {str(e)}")

    async def remove_server(self, server_name: str) -> None:
        """Remove an MCP server and its associated tools/resources."""
        async with self._lock:
            if server_name not in self.mcp_sessions:
                logger.warning(f"Server '{server_name}' not found for removal")
                return
            try:
                await self.mcp_sessions[server_name].close()
                del self.mcp_sessions[server_name]
                self.tools = {k: v for k, v in self.tools.items() if v.mcp_session != server_name}
                self.resources = {k: v for k, v in self.resources.items() if not k.startswith(f"{server_name}.")}
                self.prompts = {k: v for k, v in self.prompts.items() if not k.startswith(f"{server_name}.")}
                logger.info(f"Removed server '{server_name}'")
            except Exception as e:
                logger.error(f"Failed to remove server '{server_name}': {str(e)}")

    async def fetch_resource(self, server_name: str, resource_id: str) -> Dict:
        """Fetch an MCP resource from a server."""
        if server_name not in self.mcp_sessions:
            raise ValueError(f"Server '{server_name}' not found")
        key = f"{server_name}.{resource_id}"
        if key not in self.resources:
            raise ValueError(f"Resource '{resource_id}' not defined for '{server_name}'")
        try:
            resource_data = await self.mcp_sessions[server_name].call_tool("fetch_resource", {"id": resource_id})
            logger.info(f"Fetched resource '{key}'")
            return resource_data
        except Exception as e:
            logger.error(f"Failed to fetch resource '{key}': {str(e)}")
            raise RuntimeError(f"Resource fetch failed: {str(e)}")

    async def send_prompt(self, server_name: str, prompt_name: str, text: Optional[str] = None) -> str:
        """Send a prompt to an MCP server."""
        if server_name not in self.mcp_sessions:
            raise ValueError(f"Server '{server_name}' not found")
        key = f"{server_name}.{prompt_name}"
        prompt_text = text or self.prompts.get(key, {}).get("text")
        if not prompt_text:
            raise ValueError(f"Prompt '{prompt_name}' not defined or text not provided")
        try:
            response = await self.mcp_sessions[server_name].call_tool("send_prompt", {"text": prompt_text})
            logger.info(f"Sent prompt '{key}'")
            return response
        except Exception as e:
            logger.error(f"Failed to send prompt '{key}': {str(e)}")
            raise RuntimeError(f"Prompt send failed: {str(e)}")

    async def refresh_tools(self, server_name: str) -> None:
        """Refresh tools for a specific server."""
        if server_name not in self.mcp_sessions:
            raise ValueError(f"Server '{server_name}' not found")
        async with self._lock:
            session = self.mcp_sessions[server_name]
            try:
                response = await session.list_tools()
                tools_list = response.tools
                for tool in tools_list:
                    tool_name = f"{server_name}.{tool.name}"
                    tool_info = {
                        "description": tool.description or "",
                        "arguments": [
                            ToolArgument(
                                name=arg["name"],
                                arg_type=arg.get("type", "str"),
                                description=arg.get("description", ""),
                                required=arg.get("required", False),
                                default=arg.get("default", None)
                            ) for arg in tool.input_schema.get("parameters", [])
                        ],
                        "return_type": tool.return_type or "str",
                        "return_description": tool.get("return_description", "Result from MCP tool")
                    }
                    self.tools[tool_name] = McpTool(
                        mcp_session=session,
                        remote_tool_name=tool.name,
                        name=tool_name,
                        description=tool_info["description"],
                        arguments=tool_info["arguments"],
                        return_type=tool_info["return_type"],
                        return_description=tool_info["return_description"],
                        is_async=True
                    )
                logger.info(f"Refreshed tools for '{server_name}'")
            except Exception as e:
                logger.error(f"Failed to refresh tools for '{server_name}': {str(e)}")

    async def shutdown(self) -> None:
        """Cleanly shut down all MCP clients."""
        async with self._lock:
            for server_name, session in self.mcp_sessions.items():
                try:
                    await session.close()
                    logger.info(f"Shut down MCP server '{server_name}'")
                except Exception as e:
                    logger.error(f"Failed to shut down '{server_name}': {str(e)}")
            self.mcp_sessions.clear()
            self.tools.clear()
            self.resources.clear()
            self.prompts.clear()

    def get_tool(self, tool_name: str) -> Tool:
        """Retrieve a tool by name."""
        if not self.tools:
            logger.error("No tools have been loaded. Try to load configuration first.")
            raise RuntimeError("No tools have been loaded")
        if tool_name not in self.tools:
            logger.error(f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}")
            raise KeyError(f"Tool '{tool_name}' not found")
        return self.tools[tool_name]

    def list_tools(self) -> List[str]:
        """List all available tool names."""
        return list(self.tools.keys())

    def to_markdown(self) -> str:
        """Generate Markdown documentation for all tools."""
        markdown = "# MCP Toolbox Tools\n\n"
        for tool_name, tool in self.tools.items():
            markdown += tool.to_markdown() + "\n"
        return markdown

# Only proceed if imports were successful
if 'missing_packages' not in locals() or not missing_packages:
    # Initialize the Toolbox
    toolbox = ConfigurableMcpToolbox()

    # Try to load configuration - use multiple approaches to find the config directory
    try:
        # Current directory
        if os.path.isdir("config"):
            logger.info("Loading configuration from './config/'")
            toolbox.load_directory_sync("config/")
        # Script's directory
        elif os.path.isdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")):
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
            logger.info(f"Loading configuration from '{config_path}'")
            toolbox.load_directory_sync(config_path)
        # Package directory
        elif os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")):
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
            logger.info(f"Loading configuration from '{config_path}'")
            toolbox.load_directory_sync(config_path)
        # Full path
        elif os.path.isdir("/toolboxes/quantalogic-toolbox-mcp/quantalogic_toolbox_mcp/config"):
            config_path = "/toolboxes/quantalogic-toolbox-mcp/quantalogic_toolbox_mcp/config"
            logger.info(f"Loading configuration from '{config_path}'")
            toolbox.load_directory_sync(config_path)
        else:
            logger.warning("No config directory found. Tools will not be loaded automatically.")
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        logger.exception("Detailed traceback:")

    # Export tools to module namespace
    if toolbox.tools:
        locals().update(toolbox.tools)
        logger.info(f"Exported {len(toolbox.tools)} tools to module namespace")
    else:
        logger.warning("No tools were loaded, nothing to export to namespace")

    if __name__ == "__main__":
        print("Available tools:", toolbox.list_tools())

        # Only try to execute tools if they were loaded
        if not toolbox.tools:
            print("No tools were loaded. Please check the log for details.")
            print("Common issues:")
            print("1. Missing 'quantalogic' or 'mcp' packages")
            print("2. Config directory not found")
            print("3. Error during MCP server initialization")
            exit(1)

        # Example: Synchronous execution of SQLite query
        try:
            if "sql_query" in toolbox.tools:
                query_result = toolbox.get_tool("sql_query").execute(
                    query="SELECT * FROM users LIMIT 1"
                )
                print(f"SQL Query result: {query_result}")
            else:
                print("'sql_query' tool not found in loaded tools")
        except Exception as e:
            print(f"Error: {e}")

        # Example: Asynchronous execution with streaming and shutdown
        async def run_async():
            try:
                if "sql_query" in toolbox.tools:
                    tool = toolbox.get_tool("sql_query")
                    print(f"Tool Markdown:\n{tool.to_markdown()}")

                    # Stream example (assuming server supports streaming)
                    print("Streaming SQL query results:")
                    async for chunk in tool.stream_execute(query="SELECT * FROM users"):
                        print(f"Chunk: {chunk}")

                    # Resource and prompt example
                    if "sqlite" in toolbox.mcp_sessions:
                        resource = await toolbox.fetch_resource("sqlite", "test_db")
                        print(f"Resource: {resource}")
                        prompt_response = await toolbox.send_prompt("sqlite", "query_info")
                        print(f"Prompt response: {prompt_response}")

                        # Refresh tools
                        await toolbox.refresh_tools("sqlite")
                        print("Refreshed tools:", toolbox.list_tools())
                else:
                    print("'sql_query' tool not found in loaded tools")
            finally:
                await toolbox.shutdown()

        # Only run the async test if tools are loaded
        if toolbox.tools:
            asyncio.run(run_async())