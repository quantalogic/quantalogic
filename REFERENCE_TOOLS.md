# QuantaLogic Tools Reference

This document contains detailed documentation for all tools available in the QuantaLogic framework.

## Table of Contents

1. [Task Automation Tools](#task-automation-tools)
   - [AgentTool](#agenttool)
   - [TaskCompleteTool](#taskcompletetool)
   - [InputQuestionTool](#inputquestiontool)
   - [ExecuteBashCommandTool](#executebashcommandtool)

2. [Code Execution Tools](#code-execution-tools)
   - [PythonTool](#pythontool)
   - [NodeJsTool](#nodejstool)
   - [ElixirTool](#elixirtool)

3. [File Operations Tools](#file-operations-tools)
   - [ReadFileTool](#readfiletool)
   - [WriteFileTool](#writefiletool)
   - [EditWholeContentTool](#editwholecontenttool)
   - [ReplaceInFileTool](#replaceinfiletool)

4. [Search Tools](#search-tools)
   - [RipgrepTool](#ripgreptool)
   - [SearchDefinitionNames](#searchdefinitionnames)

5. [Vision and LLM Tools](#vision-and-llm-tools)
   - [LLMVisionTool](#llmvisiontool)
   - [LLMTool](#llmtool)

6. [Utility Tools](#utility-tools)
   - [DownloadHttpFileTool](#downloadhttpfiletool)
   - [ListDirectoryTool](#listdirectorytool)
   - [MarkitdownTool](#markitdowntool)
   - [UnifiedDiffTool](#unifieddifftool)

7. [API Tools](#api-tools)
   - [APITool](#apitool)
   - [SerpAPISearchTool](#serpapisearchtool)
   - [WikipediaSearchTool](#wikipediasearchtool)

## Argument Injection and Property Precedence

QuantaLogic tools support advanced argument injection with property precedence. When a tool has both properties and arguments with the same name, the property value takes precedence over the argument value.

### Implementation Details

The argument injection mechanism is implemented in the Tool class (tool.py) through the `get_injectable_properties_in_execution()` method. This method:

1. Checks for matching property names in the tool's configuration
2. Returns a dictionary of injectable properties
3. Filters out None values to ensure only valid properties are injected

### Property Precedence Rules

1. Tool properties take precedence over arguments
2. Properties must match argument names exactly
3. None values are excluded from injection
4. Properties are injected before argument validation

### Example Usage

```python
class MyTool(Tool):
    field1: str | None = Field(default=None)
    
    def execute(self, **kwargs):
        # field1 will be injected if defined
        print(self.field1)

# Property takes precedence over argument
tool = MyTool(field1="property_value")
tool.execute(field1="argument_value")  # Prints "property_value"
```

## Task Automation Tools

### AgentTool

The **Agent Tool** enables task delegation to another agent, providing specialized functionality for handling tasks.

#### Parameters

| Parameter    | Type   | Description                                                                         | Example                         |
|--------------|--------|-------------------------------------------------------------------------------------|---------------------------------|
| `name`       | string | Internal name of the tool (default: "agent_tool")                                   | `agent_tool`                    |
| `description`| string | Detailed description of the tool's purpose                                          | `Executes tasks using a specified agent` |
| `agent_role` | string | The role of the agent (e.g., expert, assistant)                                   | `expert`                        |
| `agent`      | Any    | The agent to delegate tasks to                                                     | `Agent` object                  |
| `task`       | string | The task to delegate to the specified agent.                                       | `Summarize the latest news.`    |

#### Key Characteristics
- Uses Pydantic for validation
- Delegate agent doesn't have access to the main agent's memory or conversation
- Context must be explicitly provided by the main agent

#### Example Usage
```python
agent_tool = AgentTool(
    name="custom_agent_tool", 
    description="Specialized task delegation", 
    agent_role="expert", 
    agent=some_agent
)
result = agent_tool.execute(task="Summarize the latest news.")
print(result)
```

### TaskCompleteTool

The **Task Complete Tool** is used to respond to users after a task has been completed.

#### Parameters

| Parameter    | Type   | Description                                                                         | Example                              |
|--------------|--------|-------------------------------------------------------------------------------------|-----------------------------------------|
| `name`       | string | Internal name of the tool (default: "task_complete")                                | `task_complete`                        |
| `description`| string | Description of the tool's purpose                                                   | `Replies to the user when the task is completed.` |
| `answer`     | string | The answer to the user. Supports variable interpolation (e.g., `$var1$`)            | `The answer to the meaning of life`    |

#### Key Characteristics
- Supports simple string responses
- Allows variable interpolation for dynamic answers

#### Example Usage
```python
task_tool = TaskCompleteTool()
response = task_tool.execute(answer="The answer is 42.")
print(response)
```

### InputQuestionTool

The **Input Question Tool** prompts the user with a question and captures their input.

#### Parameters

| Parameter    | Type   | Description                                                                         | Example                       |
|--------------|--------|-------------------------------------------------------------------------------------|-----------------------------|
| `name`       | string | Internal name of the tool (default: "input_question_tool")                          | `input_question_tool`       |
| `description`| string | Description of the tool's purpose                                                   | `Prompts the user with a question and captures their input.` |
| `question`   | string | The question to ask the user.                                                       | `What is your favorite color?` |
| `default`    | string | Optional default value if no input is provided.                                     | `blue`                      |

#### Key Characteristics
- Uses `rich.prompt` for interactive input
- Supports optional default values
- Logs user input for debugging
- Handles and logs potential input errors

#### Example Usage
```python
input_tool = InputQuestionTool()
user_response = input_tool.execute(
    question="What is your favorite color?", 
    default="blue"
)
print("User Response:", user_response)
```

### ExecuteBashCommandTool

The **Execute Bash Command Tool** allows for the execution of bash commands and captures their output.

#### Parameters

| Parameter    | Type   | Description                                                                         | Example                   |
|--------------|--------|-------------------------------------------------------------------------------------|-----------------------------|
| `name`       | string | Internal name of the tool (default: "execute_bash_tool")                            | `execute_bash_tool`         |
| `description`| string | Description of the tool's purpose                                                   | `Executes a bash command and returns its output.` |
| `command`    | string | The bash command to execute.                                                        | `ls -la`                    |
| `working_dir`| string | The working directory where the command will be executed. Defaults to current dir.  | `/path/to/directory`        |
| `timeout`    | int    | Maximum time in seconds to wait for the command to complete. Defaults to 60 seconds.| `60`                        |
| `env`        | dict   | Optional environment variables to set for the command execution.                    | `{"PATH": "/custom/path"}` |

#### Key Characteristics
- Supports executing bash commands in a specified working directory
- Configurable timeout to prevent long-running commands
- Optional environment variable configuration
- Validates command execution

#### Example Usage
```python
bash_tool = ExecuteBashCommandTool()
output = bash_tool.execute(
    command="ls -la", 
    working_dir="/path/to/directory", 
    timeout=30,
    env={"CUSTOM_VAR": "value"}
)
print(output)
```

## Code Execution Tools

### PythonTool

The **Python Tool** executes Python scripts in an isolated Docker environment.

#### Parameters

| Parameter         | Type    | Description                                                                   | Example                                    |
|-------------------|---------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string  | Internal name of the tool (default: "python_tool")                            | `python_tool`                               |
| `install_commands`| string  | Commands to install Python packages before running the script.                | `pip install rich requests`                 |
| `script`          | string  | The Python script to execute.                                                 | `print("Hello, World!")`                    |
| `version`         | string  | The Python version to use in the Docker container. (default: Python 3.x)      | `3.11`                                      |
| `host_dir`        | string  | Absolute path on the host machine to mount for file access.                   | `./demo01/`                                 |
| `memory_limit`    | string  | Optional memory limit for the Docker container.                               | `1g`                                        |
| `environment_vars`| dict    | Environment variables to set inside the Docker container.                     | `{"ENV": "production", "DEBUG": "False"}`   |

#### Execution Environment Characteristics
- Runs in an isolated Docker container
- Strict console output requirements:
  - Only `print()` and `sys.stdout.write()` are accepted
  - No GUI, plots, or visualizations
  - No external file operations without authorization
- Full network access
- Standard library modules available
- Host directory can be mounted at `/usr/src/host_data`

#### Accepted Output Methods
✓ `print()`
✓ `sys.stdout.write()`
✗ No matplotlib, tkinter, or GUI libraries
✗ No external file generation
✗ No web servers or network services

#### Example Usage
```python
python_tool = PythonTool()
output = python_tool.execute(
    install_commands="pip install rich requests",
    script='print("Hello, World!")',
    version="3.12",
    host_dir="./demo01/",
    memory_limit="1g",
    environment_vars={"ENV": "production"}
)
print("Script Output:", output)
```

#### Restrictions
- Scripts must produce console text output
- No external resource access without explicit authorization
- Memory and computational resources are limited

### NodeJsTool

The **Node.js Tool** executes Node.js scripts in an isolated Docker environment.

#### Parameters

| Parameter         | Type    | Description                                                                   | Example                                    |
|-------------------|---------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string  | Internal name of the tool (default: "nodejs_tool")                            | `nodejs_tool`                               |
| `install_commands`| string  | Commands to install Node.js packages before running the script.               | `npm install chalk axios`                   |
| `script`          | string  | The Node.js script to execute.                                                | `console.log('Hello, World!');`             |
| `version`         | string  | The Node.js version to use in the Docker container. (default: Node.js LTS)    | `20`                                        |
| `host_dir`        | string  | Absolute path on the host machine to mount for file access.                   | `./project/`                                |
| `memory_limit`    | string  | Optional memory limit for the Docker container.                               | `1g`                                        |
| `module_type`     | string  | The module system to use: 'esm' for ECMAScript Modules or 'commonjs'          | `esm`                                       |

#### Execution Environment Characteristics
- Runs in an isolated Docker container
- Strict console output requirements:
  - Only `console.log()`, `console.info()`, and `process.stdout.write()` are accepted
  - No browser-based output
  - No external file operations without authorization
- Full network access
- Standard Node.js modules available
- Host directory can be mounted for file access

#### Accepted Output Methods
✓ `console.log()`
✓ `console.info()`
✓ `process.stdout.write()`
✗ No browser-based output
✗ No external file generation
✗ No web servers or network services

#### Example Usage
```python
node_tool = NodeJsTool()
output = node_tool.execute(
    install_commands="npm install chalk axios",
    script='console.log("Hello, Node.js World!");',
    version="20",
    host_dir="./project/",
    memory_limit="1g",
    module_type="esm"
)
print("Node.js Output:", output)
```

#### Restrictions
- Scripts must produce console text output
- No external resource access without explicit authorization
- Memory and computational resources are limited

### ElixirTool

The **Elixir Tool** executes Elixir code in an isolated Docker environment with Mix support.

#### Parameters

| Parameter         | Type    | Description                                                                   | Example                                    |
|-------------------|---------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string  | Internal name of the tool (default: "elixir_tool")                            | `elixir_tool`                               |
| `mix_commands`    | string  | Mix commands to run before executing the script                               | `mix deps.get && mix compile`               |
| `script`          | string  | Elixir code to execute.                                                       | `IO.puts("Hello from Elixir!")`             |
| `version`         | string  | The Elixir version to use.                                                    | `1.15`                                      |
| `host_dir`        | string  | Host directory to mount for file access.                                      | `./elixir_project/`                         |
| `memory_limit`    | string  | Container memory limit.                                                       | `512m`                                      |
| `environment_vars`| dict    | Environment variables to set.                                                 | `{"MIX_ENV": "prod"}`                       |

#### Execution Environment Characteristics
- Runs in an isolated Docker container using official Elixir Docker images
- Full Mix project support with dependency management
- Configurable Elixir versions
- Environment variable support
- Host directory mounting
- Full access to standard library

#### Accepted Output Methods
✓ `IO.puts/1`
✓ `IO.write/1`
✓ Logger module
✓ File operations when host directory is mounted
✗ No external network services without authorization

#### Example Usage
```python
elixir_tool = ElixirTool()
output = elixir_tool.execute(
    mix_commands="mix deps.get && mix compile",
    script='IO.puts("Hello from Elixir!")',
    version="1.15",
    host_dir="./elixir_project/",
    memory_limit="512m",
    environment_vars={"MIX_ENV": "prod"}
)
print("Elixir Output:", output)
```

#### Restrictions
- Scripts must produce console text output
- No external resource access without explicit authorization
- Memory and computational resources are limited

## File Operations Tools

### ReadFileTool

The **ReadFileTool** reads content from local files or HTTP sources.

#### Parameters

| Parameter    | Type   | Description                                                                   | Example                                    |
|--------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`       | string | Internal name of the tool (default: "read_file_tool")                         | `read_file_tool`                            |
| `description`| string | Description of the tool's purpose                                             | `Reads a local file or HTTP content`        |
| `file_path`  | string | The path to the file or URL to read.                                          | `/path/to/file.txt` or `https://example.com/data.txt` |

#### Key Characteristics
- Supports reading local files and HTTP content
- Truncates content to first 3000 lines
- Not recommended for HTML files or very large files
- Prefers using `read_file_block_tool` to manage memory usage

#### Supported Input Types
- Local file paths
- HTTP/HTTPS URLs

#### Content Handling
- Automatically detects URL vs. file path
- Limits content to 3000 lines to prevent memory overflow
- Adds a truncation notice if content exceeds the limit

#### Example Usage
```python
read_tool = ReadFileTool()

# Reading a local file
local_content = read_tool.execute(file_path="/path/to/local/file.txt")
print("Local File Content:", local_content)

# Reading from a URL
url_content = read_tool.execute(file_path="https://example.com/data.txt")
print("URL Content:", url_content)
```

#### Restrictions
- Not suitable for HTML files
- Truncates content to prevent memory issues
- Recommended to use `read_file_block_tool` for large files

### WriteFileTool

The **WriteFileTool** writes content to a file with flexible configuration options.

#### Parameters

| Parameter     | Type   | Description                                                                   | Example                                    |
|---------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`        | string | Internal name of the tool (default: "write_file_tool")                        | `write_file_tool`                           |
| `description` | string | Description of the tool's purpose                                             | `Writes a file with the given content`      |
| `file_path`   | string | The path to the file to write. Using an absolute path is recommended.         | `/path/to/file.txt`                         |
| `content`     | string | The content to write to the file. Avoid adding newlines at the beginning or end. | `Hello, world!`                            |
| `append_mode` | string | If true, content will be appended to the end of the file. Defaults to "False".| `"False"`                                   |
| `overwrite`   | string | If true, existing files can be overwritten. Defaults to "False".              | `"False"`                                   |

#### Key Characteristics
- Supports writing to files with multiple configuration options
- Can append or overwrite existing files
- Recommends using absolute file paths
- Validates file writing operations

#### Content Writing Modes
- **Default Mode**: Fails if file already exists
- **Append Mode**: Adds content to the end of an existing file
- **Overwrite Mode**: Replaces existing file content

#### Content Handling
- Recommends avoiding newlines at the beginning or end of content
- Supports using CDATA to escape special characters
- Provides flexibility in file writing operations

#### Example Usage
```python
write_tool = WriteFileTool()

# Writing a new file
write_tool.execute(
    file_path="/path/to/new_file.txt", 
    content="Hello, world!"
)

# Appending to an existing file
write_tool.execute(
    file_path="/path/to/existing_file.txt", 
    content="Additional content", 
    append_mode="True"
)

# Overwriting an existing file
write_tool.execute(
    file_path="/path/to/existing_file.txt", 
    content="Completely new content", 
    overwrite="True"
)
```

#### Restrictions
- Fails by default if file already exists
- Requires explicit configuration for appending or overwriting
- Recommends using absolute file paths

### EditWholeContentTool

The **EditWholeContentTool** replaces the entire content of an existing file.

#### Parameters

| Parameter     | Type   | Description                                                                   | Example                                    |
|---------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`        | string | Internal name of the tool (default: "edit_whole_content_tool")                | `edit_whole_content_tool`                   |
| `description` | string | Description of the tool's purpose                                             | `Edits the whole content of an existing file` |
| `file_path`   | string | The path to the file to edit. Using an absolute path is recommended.          | `/path/to/file.txt`                         |
| `content`     | string | The content to write to the file. Avoid adding newlines at the beginning or end. | `Hello, world!`                            |

#### Key Characteristics
- Replaces the entire content of an existing file
- Supports tilde (`~`) expansion for file paths
- Recommends using absolute file paths
- Validates file editing operations

#### Path Handling
- Expands tilde (`~`) to the user's home directory
- Supports both relative and absolute file paths

#### Content Handling
- Completely replaces existing file content
- Recommends avoiding newlines at the beginning or end of content
- Supports using CDATA to escape special characters

#### Example Usage
```python
edit_tool = EditWholeContentTool()

# Editing a file with absolute path
edit_tool.execute(
    file_path="/path/to/file.txt", 
    content="Completely new content"
)

# Editing a file with tilde expansion
edit_tool.execute(
    file_path="~/documents/example.txt", 
    content="Updated content in home directory"
)
```

#### Restrictions
- Requires an existing file to edit
- Completely replaces the file's content
- Recommends using absolute file paths

### ReplaceInFileTool

The **ReplaceInFileTool** updates sections of content in an existing file using advanced SEARCH/REPLACE blocks.

#### Parameters

| Parameter     | Type   | Description                                                                   | Example                                    |
|---------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`        | string | Internal name of the tool (default: "replace_in_file_tool")                   | `replace_in_file_tool`                      |
| `description` | string | Description of the tool's purpose                                             | `Updates sections of content in an existing file` |
| `path`        | string | The path of the file to modify. Absolute path recommended.                    | `./src/main.py`                             |
| `diff`        | string | SEARCH/REPLACE blocks defining exact changes to be made in the code           | See Example Format Below                    |

#### SEARCH/REPLACE Block Format
```
<<<<<<< SEARCH
[exact content to find, characters must match EXACTLY]
=======
[new content to replace with]
>>>>>>> REPLACE
```

#### Key Characteristics
- Supports precise, character-exact replacements
- Provides similarity-based matching with 85% threshold
- Handles multiple SEARCH/REPLACE blocks
- Tracks changes to prevent overlapping modifications

#### Replacement Mechanics
1. **Exact Matching**
   - SEARCH content must match file content exactly
   - Includes all characters, whitespace, indentation
   - Considers comments, docstrings, and other text

2. **Replacement Rules**
   - Replaces only the first occurrence found
   - Multiple changes require separate SEARCH/REPLACE blocks
   - Include sufficient context to uniquely identify lines

3. **Special Operations**
   - Empty REPLACE section deletes corresponding lines
   - Entire missing block leaves file unchanged
   - Moving code requires delete and insert blocks

#### Example Usage
```python
replace_tool = ReplaceInFileTool()
result = replace_tool.execute(
    path="./src/main.py", 
    diff="""
<<<<<<< SEARCH
def old_function():
    pass
=======
def new_function():
    print('Hello, World!')
>>>>>>> REPLACE
"""
)
```

#### Advanced Features
- Similarity-based matching (85% threshold)
- Prevents overlapping replacements
- Supports complex code transformations

#### Restrictions
- Requires precise matching
- Limited to single-file modifications
- No automatic conflict resolution

## Utility Tools

### JinjaTool

The **JinjaTool** renders Jinja2 templates with access to the agent's variables.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string | Internal name of the tool (default: "jinja_tool")                             | `jinja_tool`                                |
| `description`     | string | Description of the tool's purpose                                             | `Renders Jinja2 templates with variable access` |
| `inline_template` | string | Jinja2 template string to render                                              | `Hello, {{ var1 }}!`                        |
| `need_variables`  | bool   | When True, provides access to the agent's variable store                      | `True`                                      |

#### Key Characteristics
- Renders Jinja2 templates with variable interpolation
- Requires `need_variables=True` to access agent's variables
- Supports all Jinja2 template features
- Useful for generating dynamic content

#### Variable Access
- Variables are accessed using `{{ var_name }}` syntax
- Must set `need_variables=True` to enable variable access
- Variables must be defined in the agent's context

#### Example Usage
```xml
<jinja_tool>
  <inline_template>Hello, {{ var1 }}! You have {{ var2|length }} items.</inline_template>
</jinja_tool>
```

#### Restrictions
- Requires `need_variables=True` for variable access
- Template must be valid Jinja2 syntax
- Variables must exist in agent's context

## Search Tools

### RipgrepTool

The **RipgrepTool** performs advanced text searches across files using ripgrep.

#### Parameters

| Parameter           | Type   | Description                                                                   | Example                                    |
|---------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`              | string | Internal name of the tool (default: "ripgrep_search_tool")                    | `ripgrep_search_tool`                       |
| `description`       | string | Description of the tool's purpose                                             | `Search files using ripgrep with regex and file filters` |
| `cwd`               | string | Base path for relative searches                                               | `/project/root`                             |
| `directory_path`    | string | The directory path to search in                                               | `./src`                                     |
| `regex_rust_syntax` | string | The regex pattern to search for (using Rust regex syntax)                     | `fn\s+search_.*\(`                          |
| `file_pattern`      | string | Optional glob pattern to filter files                                         | `**/*.py`                                   |

#### Key Characteristics
- Utilizes ripgrep for fast, powerful text searching
- Supports Rust-style regex patterns
- Allows directory and file pattern filtering
- Provides detailed search results

#### Search Features
- Regex pattern matching
- File type filtering
- Recursive directory searching
- Configurable search scope

#### Regex Pattern Syntax
- Uses Rust regex syntax
- Supports complex pattern matching
- Requires escaping special characters

#### File Filtering
- Supports glob patterns
- Can search specific file types
- Allows recursive or targeted searches

#### Example Usage
```python
ripgrep_tool = RipgrepTool()
results = ripgrep_tool.execute(
    directory_path="./src", 
    regex_rust_syntax=r"fn\s+search_.*\(",
    file_pattern="**/*.py",
    cwd="/project/root"
)
print(results)
```

#### Advanced Options
- Configurable current working directory
- Precise file type selection
- Regex-based text matching

#### Restrictions
- Requires ripgrep to be installed
- Regex patterns must follow Rust syntax
- Large searches may impact performance

### SearchDefinitionNames

The **SearchDefinitionNames** tool searches for code definition names across multiple programming languages using Tree-sitter.

#### Parameters

| Parameter           | Type   | Description                                                                   | Example                                    |
|---------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`              | string | Internal name of the tool (default: "search_definition_names_tool")           | `search_definition_names_tool`              |
| `description`       | string | Description of the tool's purpose                                             | `Searches for definition names in a directory` |
| `directory_path`    | string | The path to the directory to search in                                        | `./project/src`                             |
| `language_name`     | string | Optional specific programming language to search                              | `python`                                    |
| `file_pattern`      | string | Optional glob pattern to filter files                                         | `**/*.py`                                   |

#### Supported Languages
- Python
- JavaScript
- TypeScript
- Java
- C
- C++
- Go
- Rust
- Scala

#### Definition Types Searched
- Functions (including async functions)
- Classes
- Methods
- Class variables
- Module-level definitions

#### Key Characteristics
- Uses Tree-sitter for precise code parsing
- Supports multiple programming languages
- Returns detailed definition information
- Provides line numbers and file locations

#### Search Features
- Recursive directory searching
- Language-specific definition extraction
- Flexible file filtering
- Comprehensive code location mapping

#### Example Usage
```python
search_tool = SearchDefinitionNames()
results = search_tool.execute(
    directory_path="./project/src", 
    language_name="python",
    file_pattern="**/*.py"
)
print(results)
```

#### Output Format
- Grouped by file name
- Includes line numbers
- Provides definition type and name

#### Advanced Options
- Language-specific searching
- Precise file type selection
- Detailed code location tracking

#### Restrictions
- Requires Tree-sitter and language parsers
- Performance may vary with large codebases
- Supports a specific set of programming languages

## Vision and LLM Tools

### LLMVisionTool

The **LLMVisionTool** analyzes images using advanced multimodal language models.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string | Internal name of the tool (default: "llm_vision_tool")                        | `llm_vision_tool`                           |
| `description`     | string | Description of the tool's purpose                                             | `Analyzes images using language models`     |
| `system_prompt`   | string | System prompt to guide the model's behavior                                   | `You are an expert in image analysis`       |
| `prompt`          | string | Question or instruction about the image                                       | `What is shown in this image?`              |
| `image_url`       | string | URL of the image to analyze                                                   | `https://example.com/image.jpg`             |
| `temperature`     | float  | Controls randomness of the model's output (0.0-1.0)                           | `0.7`                                       |
| `model_name`      | string | Specific multimodal language model to use                                     | `openrouter/openai/gpt-4o-mini`              |

#### Supported Models
- OpenAI GPT-4o Mini (Default)
- Ollama LLaMA 3.2 Vision (Optional)
- Other multimodal language models

#### Key Characteristics
- Multimodal image and text analysis
- Flexible system and user prompting
- Configurable model temperature
- Supports various image analysis tasks

#### Analysis Capabilities
- Object detection
- Scene understanding
- Image description
- Visual reasoning
- Detailed image interpretation

#### Prompt Engineering
- Customizable system prompts
- Specific image-related instructions
- Fine-tuned model behavior control

#### Example Usage
```python
vision_tool = LLMVisionTool(model_name="openrouter/openai/gpt-4o-mini")
result = vision_tool.execute(
    system_prompt="You are an expert in image analysis and visual understanding.",
    prompt="What objects are in this image?",
    image_url="https://example.com/sample_image.jpg",
    temperature=0.7
)
print(result)
```

#### Advanced Features
- Dynamic model selection
- Adjustable output creativity
- Comprehensive image understanding

#### Restrictions
- Requires valid image URL
- Performance depends on model capabilities
- Potential usage and cost limitations based on model provider

### LLMTool

The **LLMTool** generates answers to questions using advanced language models.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string | Internal name of the tool (default: "llm_tool")                               | `llm_tool`                                  |
| `description`     | string | Description of the tool's purpose                                             | `Generates answers using a language model`  |
| `system_prompt`   | string | Persona or system prompt to guide the model's behavior                        | `You are an expert in machine learning`     |
| `prompt`          | string | Question to ask the language model. Supports variable interpolation           | `What is the meaning of $var1$?`            |
| `temperature`     | string | Creativity level (0.0-1.0): 0.0 no creativity, 1.0 full creativity            | `0.5`                                       |
| `model_name`      | string | Specific language model to use                                                | `openrouter/openai/gpt-4o-mini`              |

#### Operational Constraints
- Total isolation from external resources
- No access to:
  - Memory
  - File system
  - External tools
  - URLs or files
- All context must be explicitly provided in the prompt

#### Key Characteristics
- Flexible prompt engineering
- Variable interpolation support
- Configurable model creativity
- Supports various language models

#### Prompt Engineering
- Customizable system prompts
- Define model persona and behavior
- Explicit context provision
- Variable interpolation

#### Creativity Control
- Temperature range: 0.0 to 1.0
- 0.0: Deterministic, factual responses
- 0.5: Balanced creativity
- 1.0: Maximum creative output

#### Example Usage
```python
llm_tool = LLMTool(model_name="openrouter/openai/gpt-4o-mini")
result = llm_tool.execute(
    system_prompt="You are an expert in natural language processing.",
    prompt="Explain the concept of $topic$ in simple terms.",
    temperature="0.7"
)
print(result)
```

#### Supported Models
- OpenAI GPT-4o Mini (Default)
- Various language models via configuration

#### Advanced Features
- Dynamic model selection
- Precise creativity control
- Flexible prompt structuring

#### Restrictions
- Requires complete context in prompt
- No external resource access
- Performance depends on model capabilities
- Potential usage and cost limitations

## Utility Tools

### DownloadHttpFileTool

The **DownloadHttpFileTool** downloads files from HTTP/HTTPS URLs to a local file system.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string | Internal name of the tool (default: "download_http_file_tool")                | `download_http_file_tool`                   |
| `description`     | string | Description of the tool's purpose                                             | `Downloads a file from an HTTP URL`         |
| `url`             | string | The complete URL of the file to download                                      | `https://example.com/data.txt`              |
| `output_path`     | string | The local file path where the downloaded file will be saved                   | `/path/to/save/data.txt`                    |

#### Key Characteristics
- Downloads files from HTTP and HTTPS URLs
- Validates URL format before downloading
- Supports saving to specified local paths
- Provides download result feedback

#### URL Validation
- Checks for valid URL scheme and network location
- Prevents invalid or malformed URL downloads
- Ensures secure and reliable file retrieval

#### Download Behavior
- Supports various file types
- Preserves original file content
- Handles network and download errors
- Returns descriptive operation result

#### Security Considerations
- Validates URL before download
- No automatic execution of downloaded files
- Relies on system-level file permissions

#### Example Usage
```python
download_tool = DownloadHttpFileTool()
result = download_tool.execute(
    url="https://example.com/sample_file.txt", 
    output_path="/path/to/save/sample_file.txt"
)
print(result)
```

#### Supported File Types
- Text files
- Binary files
- Documents
- Archives
- Any downloadable file type

#### Advanced Features
- URL format validation
- Flexible output path configuration
- Error handling and reporting

#### Restrictions
- Requires valid HTTP/HTTPS URL
- Limited by network connectivity
- No file content execution
- Dependent on system file write permissions

### ListDirectoryTool

The **ListDirectoryTool** provides advanced directory content listing with flexible filtering and pagination.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string | Internal name of the tool (default: "list_directory_tool")                    | `list_directory_tool`                       |
| `description`     | string | Description of the tool's purpose                                             | `Lists directory contents with .gitignore filtering` |
| `directory_path`  | string | Absolute or relative path to target directory                                 | `~/documents/projects`                      |
| `recursive`       | string | Enable recursive directory traversal (true/false)                             | `true`                                      |
| `max_depth`       | int    | Maximum directory traversal depth                                             | `1`                                         |
| `start_line`      | int    | First line to return in paginated results                                     | `1`                                         |
| `end_line`        | int    | Last line to return in paginated results                                      | `200`                                       |

#### Key Characteristics
- Advanced directory content listing
- .gitignore-aware file filtering
- Recursive and depth-limited traversal
- Pagination support
- Flexible path handling

#### Traversal Modes
- **Flat Listing**: Single directory level
- **Recursive Listing**: Explore nested directories
- **Depth-Limited**: Control directory depth
- **Pagination**: Manage large result sets

#### Filtering Capabilities
- Respects .gitignore rules
- Supports absolute and relative paths
- Handles tilde (`~`) expansion
- Configurable result range

#### Path Handling
- Supports home directory expansion
- Resolves relative and absolute paths
- Handles various path representations

#### Example Usage
```python
list_tool = ListDirectoryTool()
results = list_tool.execute(
    directory_path="~/projects", 
    recursive="true", 
    max_depth=2,
    start_line=1, 
    end_line=100
)
print(results)
```

#### Output Characteristics
- Includes file/directory names
- Provides file types
- Shows file sizes
- Indicates directory structure

#### Advanced Features
- .gitignore integration
- Flexible traversal configuration
- Pagination control
- Detailed file information

#### Restrictions
- Performance may vary with large directories
- Depth and line limits apply
- Depends on filesystem access
- Respects system file permissions

### MarkitdownTool

The **MarkitdownTool** converts various file formats to Markdown using the MarkItDown library.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string | Internal name of the tool (default: "markitdown_tool")                        | `markitdown_tool`                           |
| `description`     | string | Description of the tool's purpose                                             | `Converts files to Markdown`                |
| `file_path`       | string | Path to the file to convert (local path or URL)                               | `/path/to/file.pdf` or `https://example.com/file.docx` |
| `output_file_path`| string | Optional path to write the Markdown output                                   | `/path/to/output.md`                        |

#### Supported Formats
- PDF
- PowerPoint
- Word Documents
- Excel
- HTML
- Plain Text
- Other common document types

#### Key Characteristics
- Converts multiple file formats to Markdown
- Supports local files and URLs
- Optional output file generation
- Preserves document structure
- Handles large files with line limit

#### URL and Path Handling
- Direct file path support
- HTTP/HTTPS URL conversion
- Temporary file management
- Flexible input methods

#### Conversion Features
- Semantic content extraction
- Markdown formatting preservation
- Handles complex document structures
- Supports various encoding types

#### Line Limit
- Maximum 2000 lines returned
- Prevents overwhelming output
- Configurable in implementation

#### Example Usage
```python
markitdown_tool = MarkitdownTool()

# Convert local file
markdown_content = markitdown_tool.execute(
    file_path="/path/to/document.pdf", 
    output_file_path="/path/to/output.md"
)

# Convert URL file
markdown_content = markitdown_tool.execute(
    file_path="https://example.com/report.docx"
)
print(markdown_content)
```

#### Output Options
- Return Markdown content directly
- Write to specified output file
- Supports console or file output

#### Advanced Features
- Intelligent content parsing
- Cross-format conversion
- Minimal information loss
- URL and local file support

#### Restrictions
- Line limit of 2000 lines
- Depends on MarkItDown library capabilities
- Performance varies by file complexity
- Requires network access for URLs

### UnifiedDiffTool

The **UnifiedDiffTool** applies unified diff patches to files with advanced error handling and validation.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string | Internal name of the tool (default: "unified_diff")                           | `unified_diff`                              |
| `description`     | string | Description of the tool's purpose                                             | `Applies a unified diff patch to update a file` |
| `file_path`       | string | Absolute path to the file to be patched                                       | `/path/to/file.txt`                         |
| `patch`           | string | Unified diff patch content in CDATA format                                    | `<![CDATA[--- a/file.txt\n+++ b/file.txt\n@@ -1,3 +1,4 @@\n Hello, world!\n+New line!]]>` |

#### Patch Parsing Features
- Comprehensive patch content parsing
- Metadata extraction
- Hunk-level line tracking
- Detailed line type classification

#### Line Type Classification
- **Context Lines**: Unchanged content
- **Addition Lines**: New content
- **Deletion Lines**: Removed content

#### Patch Validation
- Strict header parsing
- Filename tracking
- Metadata preservation
- Comprehensive error handling

#### Patch Application Modes
- **Strict Mode**: Precise patch application
- **Lenient Mode**: Tolerant patch application
- Configurable application tolerance
- Advanced context matching

#### Error Handling
- Custom `PatchError` with context
- Detailed error reporting
- Flexible error tolerance
- Informative error messages

#### Example Usage
```python
diff_tool = UnifiedDiffTool()
result = diff_tool.execute(
    file_path="/path/to/file.txt",
    patch="""
    <![CDATA[
    --- a/file.txt
    +++ b/file.txt
    @@ -1,3 +1,4 @@
     Hello, world!
    +New line!
    ]]>
    """
)
print(result)
```

#### Advanced Features
- Intelligent patch parsing
- Precise line number tracking
- Configurable application strictness
- Comprehensive error diagnostics

#### Patch Application Strategies
- Context-aware line matching
- Flexible offset tolerance
- Preserves original file structure
- Minimizes unintended modifications

#### Restrictions
- Requires valid unified diff format
- Performance depends on patch complexity
- Absolute file paths recommended
- Potential data loss in complex patches

## API Tools

### APITool

The **APITool** provides a flexible interface for interacting with various web APIs and services.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|---------------------------------------------|
| `name`            | string | Internal name of the tool (default: "api_tool")                               | `api_tool`                                  |
| `description`     | string | Description of the tool's purpose                                             | `Interact with web APIs and services`       |
| `method`          | string | HTTP method for the API request (GET, POST, PUT, DELETE, etc.)                | `GET`                                       |
| `url`             | string | Complete URL of the API endpoint                                              | `https://api.example.com/users`             |
| `headers`         | dict   | Optional HTTP headers for the request                                         | `{"Authorization": "Bearer token"}`         |
| `params`          | dict   | Optional query parameters for GET requests                                    | `{"page": 1, "limit": 10}`                  |
| `body`            | dict   | Optional request body for POST/PUT requests                                   | `{"name": "John", "email": "john@example.com"}` |
| `timeout`         | float  | Request timeout in seconds                                                    | `5.0`                                       |

#### Key Characteristics
- Flexible API interaction
- Support for multiple HTTP methods
- Configurable request parameters
- Comprehensive error handling
- Secure authentication support

#### Request Configuration
- Dynamic method selection
- Customizable headers
- Query parameter support
- Request body configuration
- Timeout management

#### Authentication Methods
- Bearer token support
- API key authentication
- Basic authentication
- OAuth 2.0 integration
- Custom header-based auth

#### Response Handling
- JSON parsing
- XML support
- Raw response access
- Error code interpretation
- Detailed response metadata

#### Example Usage
```python
api_tool = APITool()
response = api_tool.execute(
    method="GET",
    url="https://api.example.com/users",
    headers={"Authorization": "Bearer your_token"},
    params={"page": 1, "limit": 10},
    timeout=5.0
)
print(response.json())
```

#### Advanced Features
- Intelligent request construction
- Flexible authentication
- Comprehensive error handling
- Response type detection
- Logging and tracing

#### Error Handling
- Network error detection
- Timeout management
- HTTP status code interpretation
- Detailed error messages
- Retry mechanism support

#### Restrictions
- Requires valid API endpoint
- Network connectivity required
- Depends on external service availability
- Potential rate limiting
- Security considerations for API access

### SerpAPI Search Tool

The **SerpAPI Search Tool** allows agents to perform web searches using the SerpAPI service.

#### Parameters
| Parameter | Type   | Description                     | Example                     |
|-----------|--------|---------------------------------|-----------------------------|
| query     | string | The search query to execute     | "latest AI research papers" |
| location  | string | Geographic location for results | "United States"             |
| num       | int    | Number of results to return     | 5                           |

#### Example Usage
```python
from quantalogic.tools import SerpAPISearchTool

search_tool = SerpAPISearchTool()
results = search_tool.execute(query="latest AI research", location="United States", num=5)
print(results)
```

### Wikipedia Search Tool

The **Wikipedia Search Tool** enables agents to search and retrieve information from Wikipedia.

#### Parameters

| Parameter | Type   | Description                     | Example                     |
|-----------|--------|---------------------------------|-----------------------------|
| query     | string | The search query to execute     | "Artificial Intelligence"   |
| lang      | string | Language code for results       | "en"                        |
| sentences | int    | Number of summary sentences     | 3                           |

#### Example Usage
```python
from quantalogic.tools import WikipediaSearchTool

wiki_tool = WikipediaSearchTool()
results = wiki_tool.execute(query="Artificial Intelligence", lang="en", sentences=3)
print(results)

```
