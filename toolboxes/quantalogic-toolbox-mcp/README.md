# 🛠️ QuantaLogic MCP Toolbox

> A generic adapter for interacting with one or more MCP servers via JSON-based configuration, with automatic tool discovery, caching, and session management.

---

[![PyPI Version](https://img.shields.io/pypi/v/quantalogic-toolbox-mcp.svg)](https://pypi.org/project/quantalogic-toolbox-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 📋 Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Quickstart Example](#quickstart-example)
4. [Architecture](#architecture)
5. [API Reference](#api-reference)
6. [Contributing](#contributing)
7. [License](#license)

---

## 🚀 Installation

Install from PyPI:

```bash
pip install quantalogic-toolbox-mcp
```

Or with Poetry:

```bash
poetry add quantalogic-toolbox-mcp
```

---

## ⚙️ Configuration

By default, the toolbox reads JSON files from `./mcp_config/` or the directory set by `MCP_CONFIG_DIR`. You can also specify a single file via the `MCP_CONFIG_FILE` environment variable.

Create a config file (`mcp.json`) in `mcp_config/` with the following structure:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-v",
        "mcp-test:/mcp",
        "mcp/sqlite",
        "--db-path",
        "/mcp/test.db"
      ]
    },
    "mcp_hn": {
      "command": "uvx",
      "args": ["mcp-hn"]
    },
    "fetcher": {
      "command": "npx",
      "args": ["-y", "fetcher-mcp"]
    },
    "job_search": {
      "command": "npx",
      "args": ["-y", "job-searchoor"]
    },
    "edgeone": {
      "command": "npx",
      "args": ["edgeone-pages-mcp"]
    }
  }
}
```

- **command**: Executable or Docker alias
- **args**: Argument list to launch the server

Environment variables in `env` entries can use `{{ env.VAR_NAME }}` and will be resolved at runtime.

---

## 🏃 Quickstart Example

```python
from quantalogic_toolbox_mcp.tools import get_tools
import asyncio

async def main():
    # Discover core and dynamic tools
    tools = get_tools()

    # List configured servers
    from quantalogic_toolbox_mcp.tools import list_servers
    servers = await list_servers()
    print("Servers:", servers)

    # List tools on a server
    resources = await tools[0]('sqlite')  # mcp_list_tools
    print("Tools on sqlite:", resources)

    # Call a specific tool dynamically
    dynamic = [t for t in tools if hasattr(t, 'server_name') and t.server_name == 'sqlite'][0]
    result = await dynamic(input_file="/mcp/test.db")
    print("Result:", result)

asyncio.run(main())
```

---

## 🏛️ Architecture
```mermaid
%%{init: { 'theme': 'base', 'themeVariables': { 
    'primaryColor': '#A3C9E2', 
    'secondaryColor': '#B7E3CC', 
    'tertiaryColor': '#F9E0BB', 
    'lineColor': '#B5B5B5', 
    'fontFamily': 'Inter, Arial, sans-serif'
} }}%%
flowchart TD
    A[Load JSON configs] --> B{Cache valid?}
    B -- Yes --> C[Load servers & tools from cache]
    B -- No  --> D[Read & resolve configs]
    D --> E[Fetch tool lists & details]
    C & E --> F[Populate `tools_cache`]
    F --> G["get_tools()"]
    G --> H[Execute core or dynamic tools]
    H --> I[Parse & return results]
```

---

## 📖 API Reference

- **get_tools()** → `List[Callable]`
  - Returns core functions and dynamic tool wrappers.

- **mcp_list_resources(server_name: str)** → `List[str]`
- **mcp_list_tools(server_name: str)** → `List[str]`
- **mcp_call_tool(server_name: str, tool_name: str, arguments: dict)** → `Any`
- **list_servers()** → `List[str]`

For full signatures and details, refer to `toolboxes/quantalogic-toolbox-mcp/quantalogic_toolbox_mcp/tools.py`.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests in `tests/`
4. Run `pytest` and `ruff .`
5. Submit a pull request against `main`

Please see `CONTRIBUTING.md` for more details.

---

## 📜 License

This project is licensed under the MIT License – see the [LICENSE](../../LICENSE) file for details.