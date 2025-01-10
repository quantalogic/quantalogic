# Tools API Reference

QuantaLogic provides a rich set of tools that enable agents to perform various tasks. This reference documents all available tools and their usage.

## Core Tools

### LLM Tools

#### LLMTool
```python
from quantalogic.tools import LLMTool

tool = LLMTool(model_name="your-model")
```

Generates text using language models. Works in isolation without access to memory or file system.

**Arguments:**
- `system_prompt` (str): Guide the model's behavior
- `prompt` (str): The actual query or instruction
- `temperature` (float, optional): Sampling temperature

#### LLMVisionTool
```python
from quantalogic.tools import LLMVisionTool

tool = LLMVisionTool(model_name="your-vision-model")
```

Analyzes images using multimodal models.

**Arguments:**
- `system_prompt` (str): Guide model behavior
- `prompt` (str): Question about the image
- `image_path` (str): Path to image file

### Code Execution Tools

#### PythonTool
```python
from quantalogic.tools import PythonTool

tool = PythonTool()
```

Executes Python code in an isolated Docker environment.

**Features:**
- Python 3.x support
- pip package management
- Docker isolation
- Memory limits
- Host directory mounting

**Arguments:**
- `code` (str): Python code to execute
- `packages` (list, optional): Required pip packages
- `host_dir` (str, optional): Directory to mount
- `memory_limit` (str, optional): Container memory limit

#### NodeJsTool
```python
from quantalogic.tools import NodeJsTool

tool = NodeJsTool()
```

Executes Node.js code in an isolated environment.

**Features:**
- ESM and CommonJS support
- npm package management
- Docker isolation

**Arguments:**
- `code` (str): Node.js code
- `packages` (list, optional): npm packages
- `version` (str, optional): Node.js version

### File Operations

#### ReadFileTool
```python
from quantalogic.tools import ReadFileTool

tool = ReadFileTool()
```

Reads file contents safely.

**Arguments:**
- `file_path` (str): Path to file
- `encoding` (str, optional): File encoding

#### WriteFileTool
```python
from quantalogic.tools import WriteFileTool

tool = WriteFileTool()
```

Creates or updates files.

**Arguments:**
- `file_path` (str): Target file path
- `content` (str): Content to write
- `mode` (str, optional): Write mode (w/a)

#### ListDirectoryTool
```python
from quantalogic.tools import ListDirectoryTool

tool = ListDirectoryTool()
```

Lists directory contents with filtering.

**Arguments:**
- `directory_path` (str): Target directory
- `recursive` (bool, optional): Enable recursion
- `max_depth` (int, optional): Maximum depth
- `pattern` (str, optional): File pattern filter

### Search Tools

#### RipgrepTool
```python
from quantalogic.tools import RipgrepTool

tool = RipgrepTool()
```

Fast code search using ripgrep.

**Arguments:**
- `directory_path` (str): Search directory
- `regex_rust_syntax` (str): Search pattern
- `file_pattern` (str, optional): File filter

#### DuckDuckGoSearchTool
```python
from quantalogic.tools import DuckDuckGoSearchTool

tool = DuckDuckGoSearchTool()
```

Web search using DuckDuckGo.

**Arguments:**
- `query` (str): Search query
- `search_type` (str): text/images/videos/news
- `max_results` (int): Result limit
- `region` (str, optional): Search region

### Document Processing

#### MarkitdownTool
```python
from quantalogic.tools import MarkitdownTool

tool = MarkitdownTool()
```

Converts documents to Markdown.

**Arguments:**
- `file_path` (str): Source file/URL
- `output_file_path` (str, optional): Output path

**Supported Formats:**
- PDF
- PowerPoint
- Word
- Excel
- HTML

### System Tools

#### ExecuteBashCommandTool
```python
from quantalogic.tools import ExecuteBashCommandTool

tool = ExecuteBashCommandTool()
```

Executes shell commands safely.

**Arguments:**
- `command` (str): Command to execute
- `working_dir` (str, optional): Working directory
- `timeout` (int, optional): Command timeout

### Agent Tools

#### AgentTool
```python
from quantalogic.tools import AgentTool

tool = AgentTool(agent_role="expert", agent=sub_agent)
```

Delegates tasks to other agents.

**Arguments:**
- `task` (str): Task description
- `agent_role` (str): Role specification
- `agent` (Agent): Target agent instance

## Creating Custom Tools

Extend the `Tool` base class to create custom tools:

```python
from quantalogic.tools import Tool, ToolArgument

class CustomTool(Tool):
    name: str = "custom_tool"
    description: str = "Your tool description"
    arguments: list = [
        ToolArgument(
            name="arg_name",
            arg_type="string",
            description="Argument description",
            required=True,
            example="Example value"
        )
    ]

    def execute(self, **kwargs) -> Any:
        # Implement tool logic
        pass
```

## Best Practices

### 1. Tool Selection
```python
# Choose the right tool for the task
if task_involves_code:
    tool = PythonTool()
elif task_involves_search:
    tool = RipgrepTool()
else:
    tool = LLMTool()
```

### 2. Error Handling
```python
try:
    result = tool.execute(**args)
except ToolExecutionError as e:
    logger.error(f"Tool failed: {e}")
    # Handle error appropriately
```

### 3. Resource Management
```python
# Set reasonable limits
python_tool = PythonTool()
result = python_tool.execute(
    code="your_code",
    memory_limit="1g",
    timeout=60
)
```

### 4. Security
```python
# Always use isolation
bash_tool = ExecuteBashCommandTool()
result = bash_tool.execute(
    command="ls -la",
    working_dir="/safe/directory"
)
```

## Tool Categories

### Code Tools
- PythonTool
- NodeJsTool
- ElixirTool

### File Tools
- ReadFileTool
- WriteFileTool
- ListDirectoryTool
- ReplaceInFileTool

### Search Tools
- RipgrepTool
- DuckDuckGoSearchTool
- WikipediaSearchTool
- SerpApiSearchTool

### Processing Tools
- MarkitdownTool
- UnifiedDiffTool
- DownloadHttpFileTool

### System Tools
- ExecuteBashCommandTool
- AgentTool

## Next Steps

- Learn about [Tool Development](../best-practices/tool-development.md)
- Explore [Memory Tools](./memory.md)
