# Tools API Reference

QuantaLogic provides a rich set of tools that enable agents to perform various tasks. This reference documents all available tools and their usage.

## Core Tools

### LLM Tools

#### LLMTool
```python
from quantalogic.tools import LLMTool
```

Generates text using language models. Works in isolation without access to memory, file system, or other resources.

**Arguments:**
- `system_prompt` (str, required): Guide model behavior with a persona or system prompt
- `prompt` (str, required): The actual query or instruction
- `temperature` (str, optional): Sampling temperature (default: 0.7)

**Note:** All context must be explicitly provided in the prompt. No access to memory, files, tools, or external resources.

#### LLMVisionTool
```python
from quantalogic.tools import LLMVisionTool
```

Analyzes images using multimodal models.

**Arguments:**
- `system_prompt` (str, required): Guide model behavior
- `prompt` (str, required): Question about the image
- `image_url` (str, required): URL of the image to analyze

### Code Execution Tools

#### PythonTool
```python
from quantalogic.tools import PythonTool
```

Executes Python code in an isolated Docker environment.

**Features:**
- Python 3.11 support
- pip package management
- Docker isolation
- Host directory mounting
- Memory limits
- Network access

**Arguments:**
- `code` (str, required): Python code to execute (must use print() for output)
- `packages` (list, optional): Required pip packages
- `host_dir` (str, optional): Directory to mount at /usr/src/host_data
- `memory_limit` (str, optional): Container memory limit

**Note:** Only console output via print() is supported. No GUI, plots, or unauthorized file operations.

#### NodeJsTool
```python
from quantalogic.tools import NodeJsTool
```

Executes Node.js code (ESM or CommonJS) in an isolated environment.

**Features:**
- ESM and CommonJS support
- npm package management
- Docker isolation
- Network access

**Arguments:**
- `code` (str, required): Node.js code (must use console.log() for output)
- `packages` (list, optional): npm packages
- `version` (str, optional): Node.js version (default: LTS)

**Note:** Only console output via console.log(), console.info(), or process.stdout.write() is supported.

### File Operations

#### WriteFileTool
```python
from quantalogic.tools import WriteFileTool
```

Writes content to files safely.

**Arguments:**
- `file_path` (str, required): Path to file (absolute path recommended)
- `content` (str, required): Content to write (use CDATA for special characters)
- `mode` (str, optional): File mode (default: "w")

**Note:** Tool will fail if file exists when not in append mode.

#### DownloadHttpFileTool
```python
from quantalogic.tools import DownloadHttpFileTool
```

Downloads files from HTTP URLs.

**Arguments:**
- `url` (str, required): URL of file to download
- `output_path` (str, required): Local path to save file

### Search Tools

#### RipgrepTool
```python
from quantalogic.tools import RipgrepTool
```

Fast code search using ripgrep.

**Arguments:**
- `directory_path` (str, required): Directory to search in
- `regex_rust_syntax` (str, required): Regex pattern in Rust syntax
- `cwd` (str, optional): Base path for relative searches
- `file_pattern` (str, optional): File filter

#### DuckDuckGoSearchTool
```python
from quantalogic.tools import DuckDuckGoSearchTool
```

Web search using DuckDuckGo.

**Arguments:**
- `query` (str, required): Search query
- `search_type` (str, required): text/images/videos/news
- `max_results` (int, required): Result limit
- `region` (str, optional): Search region
- `safesearch` (str, optional): moderate/strict/off

### System Tools

#### ExecuteBashCommandTool
```python
from quantalogic.tools import ExecuteBashCommandTool
```

Executes bash commands safely.

**Arguments:**
- `command` (str, required): Bash command to execute
- `working_dir` (str, optional): Working directory
- `timeout` (int, optional): Command timeout in seconds (default: 60)

**Note:** Requires validation before execution.

#### AgentTool
```python
from quantalogic.tools import AgentTool
```

Delegates tasks to another agent.

**Arguments:**
- `task` (str, required): Task to delegate
- `agent_role` (str, required): Role of the agent (e.g., expert)
- `agent` (Agent, required): Agent instance to delegate to

**Note:** Delegate agent doesn't have access to main agent's memory/context.

## Next Steps

- Learn about [Tool Development](../best-practices/tool-development.md)
- Explore [Memory Tools](./memory.md)
