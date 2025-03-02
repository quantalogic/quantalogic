# QuantaLogic Tools Reference

This document contains detailed documentation for all tools available in the QuantaLogic framework, based on the provided implementation code.

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

4. [Database Documentation Tools](#database-documentation-tools)
   - [GenerateDatabaseReportTool](#generatedatabasereporttool)

5. [SQL Query Tools](#sql-query-tools)
   - [SQLQueryTool](#sqlquerytool)

6. [Utility Tools](#utility-tools)
   - [JinjaTool](#jinjatool)
   - [DownloadHttpFileTool](#downloadhttpfiletool)
   - [ListDirectoryTool](#listdirectorytool)
   - [MarkitdownTool](#markitdowntool)

7. [Search Tools](#search-tools)
   - [RipgrepTool](#ripgreptool)
   - [SearchDefinitionNames](#searchdefinitionnames)

8. [Vision and LLM Tools](#vision-and-llm-tools)
   - [LLMImageGenerationTool](#llmimagegenerationtool)
   - [LLMVisionTool](#llmvisiontool)
   - [LLMTool](#llmtool)

9. [Git Tools](#git-tools)
   - [BitbucketOperationsTool](#bitbucketoperationstool)
   - [GitOperationsTool](#gitoperationstool)

10. [RAG Tools](#rag-tools)
    - [RagTool](#ragtool)
    - [RagToolBeta](#ragtoolbeta)
    - [DocumentMetadata](#documentmetadata)
    - [QueryResponse](#queryresponse)

## Argument Injection and Property Precedence

QuantaLogic tools support advanced argument injection with property precedence. When a tool has both properties and arguments with the same name, the property value takes precedence over the argument value.

### Implementation Details

The argument injection mechanism is implemented in the `Tool` class (`quantalogic/tools/tool.py`) through the `get_injectable_properties_in_execution()` method. This method:

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

The **AgentTool** enables task delegation to another agent, providing specialized functionality for handling tasks. (Note: Full implementation not provided in the code; description based on original documentation.)

#### Parameters

| Parameter    | Type   | Description                                                                         | Example                         |
|--------------|--------|-------------------------------------------------------------------------------------|---------------------------------|
| `name`       | string | Internal name of the tool (default: "agent_tool")                                   | `agent_tool`                    |
| `description`| string | Detailed description of the tool's purpose                                          | `Executes tasks using a specified agent` |
| `agent_role` | string | The role of the agent (e.g., expert, assistant)                                     | `expert`                        |
| `agent`      | Any    | The agent to delegate tasks to                                                      | `Agent` object                  |
| `task`       | string | The task to delegate to the specified agent                                         | `Summarize the latest news.`    |

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

The **TaskCompleteTool** is used to respond to users after a task has been completed. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter    | Type   | Description                                                                         | Example                              |
|--------------|--------|-------------------------------------------------------------------------------------|--------------------------------------|
| `name`       | string | Internal name of the tool (default: "task_complete")                                | `task_complete`                      |
| `description`| string | Description of the tool's purpose                                                  | `Replies to the user when the task is completed.` |
| `answer`     | string | The answer to the user. Supports variable interpolation (e.g., `$var1$`)            | `The answer to the meaning of life`  |

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

The **InputQuestionTool** prompts the user with a question and captures their input. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter    | Type   | Description                                                                         | Example                       |
|--------------|--------|-------------------------------------------------------------------------------------|-----------------------------|
| `name`       | string | Internal name of the tool (default: "input_question_tool")                          | `input_question_tool`       |
| `description`| string | Description of the tool's purpose                                                  | `Prompts the user with a question and captures their input.` |
| `question`   | string | The question to ask the user                                                       | `What is your favorite color?` |
| `default`    | string | Optional default value if no input is provided                                     | `blue`                      |

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

The **ExecuteBashCommandTool** allows for the execution of bash commands and captures their output. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter    | Type   | Description                                                                         | Example                   |
|--------------|--------|-------------------------------------------------------------------------------------|---------------------------|
| `name`       | string | Internal name of the tool (default: "execute_bash_tool")                            | `execute_bash_tool`       |
| `description`| string | Description of the tool's purpose                                                  | `Executes a bash command and returns its output.` |
| `command`    | string | The bash command to execute                                                        | `ls -la`                  |
| `working_dir`| string | The working directory where the command will be executed. Defaults to current dir  | `/path/to/directory`      |
| `timeout`    | int    | Maximum time in seconds to wait for the command to complete. Defaults to 60 seconds| `60`                      |
| `env`        | dict   | Optional environment variables to set for the command execution                    | `{"PATH": "/custom/path"}`|

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

The **PythonTool** executes Python scripts in an isolated Docker environment. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type    | Description                                                                   | Example                                    |
|-------------------|---------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string  | Internal name of the tool (default: "python_tool")                            | `python_tool`                              |
| `install_commands`| string  | Commands to install Python packages before running the script                 | `pip install rich requests`                |
| `script`          | string  | The Python script to execute                                                  | `print("Hello, World!")`                   |
| `version`         | string  | The Python version to use in the Docker container. (default: Python 3.x)      | `3.11`                                     |
| `host_dir`        | string  | Absolute path on the host machine to mount for file access                    | `./demo01/`                                |
| `memory_limit`    | string  | Optional memory limit for the Docker container                                | `1g`                                       |
| `environment_vars`| dict    | Environment variables to set inside the Docker container                      | `{"ENV": "production", "DEBUG": "False"}`  |

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

The **NodeJsTool** executes Node.js scripts in an isolated Docker environment. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type    | Description                                                                   | Example                                    |
|-------------------|---------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string  | Internal name of the tool (default: "nodejs_tool")                            | `nodejs_tool`                              |
| `install_commands`| string  | Commands to install Node.js packages before running the script                | `npm install chalk axios`                  |
| `script`          | string  | The Node.js script to execute                                                 | `console.log('Hello, World!');`            |
| `version`         | string  | The Node.js version to use in the Docker container. (default: Node.js LTS)    | `20`                                       |
| `host_dir`        | string  | Absolute path on the host machine to mount for file access                    | `./project/`                               |
| `memory_limit`    | string  | Optional memory limit for the Docker container                                | `1g`                                       |
| `module_type`     | string  | The module system to use: 'esm' for ECMAScript Modules or 'commonjs'          | `esm`                                      |

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

The **ElixirTool** executes Elixir code in an isolated Docker environment with Mix support. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type    | Description                                                                   | Example                                    |
|-------------------|---------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string  | Internal name of the tool (default: "elixir_tool")                            | `elixir_tool`                              |
| `mix_commands`    | string  | Mix commands to run before executing the script                               | `mix deps.get && mix compile`              |
| `script`          | string  | Elixir code to execute                                                        | `IO.puts("Hello from Elixir!")`            |
| `version`         | string  | The Elixir version to use                                                     | `1.15`                                     |
| `host_dir`        | string  | Host directory to mount for file access                                       | `./elixir_project/`                        |
| `memory_limit`    | string  | Container memory limit                                                        | `512m`                                     |
| `environment_vars`| dict    | Environment variables to set                                                  | `{"MIX_ENV": "prod"}`                      |

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

The **ReadFileTool** reads content from local files or HTTP sources. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter    | Type   | Description                                                                   | Example                                    |
|--------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`       | string | Internal name of the tool (default: "read_file_tool")                         | `read_file_tool`                           |
| `description`| string | Description of the tool's purpose                                             | `Reads a local file or HTTP content`       |
| `file_path`  | string | The path to the file or URL to read                                           | `/path/to/file.txt` or `https://example.com/data.txt` |

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

The **WriteFileTool** writes content to a file with flexible configuration options. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter     | Type   | Description                                                                   | Example                                    |
|---------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`        | string | Internal name of the tool (default: "write_file_tool")                        | `write_file_tool`                          |
| `description` | string | Description of the tool's purpose                                             | `Writes a file with the given content`     |
| `file_path`   | string | The path to the file to write. Using an absolute path is recommended          | `/path/to/file.txt`                        |
| `content`     | string | The content to write to the file. Avoid adding newlines at the beginning or end | `Hello, world!`                           |
| `append_mode` | string | If true, content will be appended to the end of the file. Defaults to "False" | `"False"`                                  |
| `overwrite`   | string | If true, existing files can be overwritten. Defaults to "False"               | `"False"`                                  |

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

The **EditWholeContentTool** replaces the entire content of an existing file. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter     | Type   | Description                                                                   | Example                                    |
|---------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`        | string | Internal name of the tool (default: "edit_whole_content_tool")                | `edit_whole_content_tool`                  |
| `description` | string | Description of the tool's purpose                                             | `Edits the whole content of an existing file` |
| `file_path`   | string | The path to the file to edit. Using an absolute path is recommended           | `/path/to/file.txt`                        |
| `content`     | string | The content to write to the file. Avoid adding newlines at the beginning or end | `Hello, world!`                           |

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

The **ReplaceInFileTool** updates sections of content in an existing file using advanced SEARCH/REPLACE blocks. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter     | Type   | Description                                                                   | Example                                    |
|---------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`        | string | Internal name of the tool (default: "replace_in_file_tool")                   | `replace_in_file_tool`                     |
| `description` | string | Description of the tool's purpose                                             | `Updates sections of content in an existing file` |
| `path`        | string | The path of the file to modify. Absolute path recommended                     | `./src/main.py`                            |
| `diff`        | string | SEARCH/REPLACE blocks defining exact changes to be made in the code           | See Example Format Below                   |

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

## Database Documentation Tools

### GenerateDatabaseReportTool

The **GenerateDatabaseReportTool** generates comprehensive database documentation reports, including ER diagrams, from a database connection string. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter           | Type   | Description                                                                   | Example                                    |
|---------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`              | string | Internal name of the tool (default: "generate_database_report_tool")          | `generate_database_report_tool`            |
| `description`       | string | Description of the tool's purpose                                             | `Generates a comprehensive Markdown database documentation report with ER diagram` |
| `connection_string` | string | SQLAlchemy-compatible database connection string                              | `postgresql://user:password@localhost/mydatabase` |

#### Key Characteristics
- Generates detailed database documentation in Markdown format
- Includes ER diagrams for visual representation
- Supports SQLAlchemy-compatible connection strings
- Handles various database types (SQLite, PostgreSQL, MySQL, etc.)
- Provides structured documentation for tables, columns, and relationships

#### Documentation Features
- Table schema details
- Column descriptions and data types
- Primary and foreign key relationships
- Index information
- Visual ER diagrams
- Markdown formatting for easy readability

#### Supported Databases
- SQLite
- PostgreSQL
- MySQL
- Oracle
- Microsoft SQL Server
- Other SQLAlchemy-supported databases

#### Example Usage
```python
from quantalogic.tools.database import GenerateDatabaseReportTool

# Initialize the tool with a connection string
tool = GenerateDatabaseReportTool(
    connection_string="sqlite:///sample.db"
)

# Generate and print the database report
report = tool.execute()
print(report)
```

#### Output Format
- **Markdown Document**:
  - Table of contents
  - Table schemas with detailed column information
  - Relationship diagrams
  - Index and constraint details
- **ER Diagram**:
  - Visual representation of table relationships
  - Generated using Graphviz
  - Embedded in Markdown document

#### Advanced Features
- Automatic relationship detection
- Configurable output format
- Support for large databases
- Error handling for invalid connections

#### Restrictions
- Requires valid SQLAlchemy connection string
- Database must be accessible
- Performance may vary with large databases
- Requires Graphviz for ER diagram generation

## SQL Query Tools

### SQLQueryTool

The **SQLQueryTool** executes SQL queries against a database and returns the results in a paginated markdown table format. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "sql_query_tool")                         | `sql_query_tool`                           |
| `description`     | string | Description of the tool's purpose                                             | `Executes a SQL query and returns results in markdown table format with pagination support.` |
| `connection_string`| string | SQLAlchemy-compatible database connection string                              | `postgresql://user:password@localhost/mydb` |
| `query`           | string | The SQL query to execute                                                      | `SELECT * FROM customers WHERE country = 'France'` |
| `start_row`       | int    | 1-based starting row number for results                                       | `1`                                        |
| `end_row`         | int    | 1-based ending row number for results                                         | `100`                                      |

#### Key Characteristics
- Executes SQL queries against a database
- Returns results in markdown table format
- Supports pagination with start and end row numbers
- Handles various numeric types for row numbers
- Provides detailed error handling and validation

#### Query Execution
- Supports any valid SQL query
- Returns results as a list of dictionaries
- Handles large result sets with pagination
- Validates query syntax and parameters

#### Pagination Features
- Configurable start and end row numbers
- Automatically adjusts for out-of-range values
- Provides metadata about total rows and displayed range
- Includes notice for remaining rows

#### Error Handling
- Validates row numbers and query syntax
- Handles database connection issues
- Provides detailed error messages
- Raises specific exceptions for different error types

#### Example Usage
```python
sql_tool = SQLQueryTool(connection_string="sqlite:///sample.db")
results = sql_tool.execute(
    query="SELECT * FROM customers", 
    start_row=1, 
    end_row=10
)
print(results)
```

#### Output Format
- **Header**: Displays the range of rows shown and total rows
- **Table**: Markdown-formatted table with column headers and data
- **Footer**: Notice about remaining rows if applicable

#### Example Output
```markdown
**Query Results:** `1-10` of `50` rows

| id | name          | country |
|----|---------------|---------|
| 1  | John Doe      | USA     |
| 2  | Jane Smith    | Canada  |
| ...| ...           | ...     |

*Showing first 10 rows - 40 more rows available*
```

#### Advanced Features
- Flexible row number input handling
- Automatic result truncation for long values
- Comprehensive error diagnostics
- Configurable pagination range

#### Restrictions
- Requires valid database connection string
- Performance depends on query complexity
- Limited by database access permissions
- Results are truncated based on pagination

## Utility Tools

### JinjaTool

The **JinjaTool** renders Jinja2 templates with access to the agent's variables. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "jinja_tool")                             | `jinja_tool`                               |
| `description`     | string | Description of the tool's purpose                                             | `Renders Jinja2 templates with variable access` |
| `inline_template` | string | Jinja2 template string to render                                              | `Hello, {{ var1 }}!`                       |
| `need_variables`  | bool   | When True, provides access to the agent's variable store                      | `True`                                     |

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

### DownloadHttpFileTool

The **DownloadHttpFileTool** downloads files from HTTP/HTTPS URLs to a local file system. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "download_http_file_tool")                | `download_http_file_tool`                  |
| `description`     | string | Description of the tool's purpose                                             | `Downloads a file from an HTTP URL`        |
| `url`             | string | The complete URL of the file to download                                      | `https://example.com/data.txt`             |
| `output_path`     | string | The local file path where the downloaded file will be saved                   | `/path/to/save/data.txt`                   |

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

The **ListDirectoryTool** provides advanced directory content listing with flexible filtering and pagination. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "list_directory_tool")                    | `list_directory_tool`                      |
| `description`     | string | Description of the tool's purpose                                             | `Lists directory contents with .gitignore filtering` |
| `directory_path`  | string | Absolute or relative path to target directory                                 | `~/documents/projects`                     |
| `recursive`       | string | Enable recursive directory traversal (true/false)                             | `true`                                     |
| `max_depth`       | int    | Maximum directory traversal depth                                             | `1`                                        |
| `start_line`      | int    | First line to return in paginated results                                     | `1`                                        |
| `end_line`        | int    | Last line to return in paginated results                                      | `200`                                      |

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

The **MarkitdownTool** converts various file formats to Markdown using the MarkItDown library. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "markitdown_tool")                        | `markitdown_tool`                          |
| `description`     | string | Description of the tool's purpose                                             | `Converts files to Markdown`               |
| `file_path`       | string | Path to the file to convert (local path or URL)                               | `/path/to/file.pdf` or `https://example.com/file.docx` |
| `output_file_path`| string | Optional path to write the Markdown output                                    | `/path/to/output.md`                       |

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
result = markitdown_tool.execute(
    file_path="/path/to/file.pdf",
    output_file_path="/path/to/output.md"
)
print(result)
```

#### Restrictions
- Requires compatible file formats
- Limited to 2000 lines of output
- Depends on MarkItDown library capabilities

## Search Tools

### RipgrepTool

The **RipgrepTool** performs advanced text searches across files using ripgrep. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter           | Type   | Description                                                                   | Example                                    |
|---------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`              | string | Internal name of the tool (default: "ripgrep_search_tool")                    | `ripgrep_search_tool`                      |
| `description`       | string | Description of the tool's purpose                                             | `Search files using ripgrep with regex and file filters` |
| `cwd`               | string | Base path for relative searches                                               | `/project/root`                            |
| `directory_path`    | string | The directory path to search in                                               | `./src`                                    |
| `regex_rust_syntax` | string | The regex pattern to search for (using Rust regex syntax)                     | `fn\s+search_.*\(`                         |
| `file_pattern`      | string | Optional glob pattern to filter files                                         | `**/*.py`                                  |

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

The **SearchDefinitionNames** tool searches for code definition names across multiple programming languages using Tree-sitter. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter           | Type   | Description                                                                   | Example                                    |
|---------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`              | string | Internal name of the tool (default: "search_definition_names_tool")           | `search_definition_names_tool`             |
| `description`       | string | Description of the tool's purpose                                             | `Searches for definition names in a directory` |
| `directory_path`    | string | The path to the directory to search in                                        | `./project/src`                            |
| `language_name`     | string | Optional specific programming language to search                              | `python`                                   |
| `file_pattern`      | string | Optional glob pattern to filter files                                         | `**/*.py`                                  |

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

### LLMImageGenerationTool

The **LLMImageGenerationTool** generates images using either DALL-E or Stable Diffusion via AWS Bedrock, with configurable settings for size, style, and quality.

#### Parameters

| Parameter         | Type   | Required | Default Value | Description                                                                 |
|-------------------|--------|----------|---------------|-----------------------------------------------------------------------------|
| `prompt`          | string | Yes      | -             | Text description of the image to generate                                   |
| `provider`        | string | No       | `"dall-e"`    | Image generation provider (`dall-e` or `stable-diffusion`)                  |
| `size`            | string | No       | `"1024x1024"` | Size of the generated image                                                |
| `quality`         | string | No       | `"standard"`  | Quality level for DALL-E (`standard` or `hd`)                              |
| `style`           | string | No       | `"vivid"`     | Style preference for DALL-E (`vivid` or `natural`)                         |
| `negative_prompt` | string | No       | `""`          | What to avoid in the image (Stable Diffusion only)                         |
| `cfg_scale`       | string | No       | `"7.5"`       | Classifier Free Guidance scale (Stable Diffusion only, range: 1.0-20.0)    |

#### Key Characteristics
- Supports DALL-E and Stable Diffusion providers
- Configurable image size, quality, and style
- Saves images with metadata in JSON format
- Handles generation process with error reporting

#### Generation Features
- Text-to-image generation based on prompts
- Customizable Stable Diffusion parameters (negative prompt, CFG scale)
- DALL-E-specific quality and style options
- Automatic file saving in `generated_images` directory

#### Example Usage
```python
from quantalogic.tools.image_generation import LLMImageGenerationTool

# Initialize the tool
tool = LLMImageGenerationTool()

# Generate an image using DALL-E
prompt = "A serene Japanese garden with a red maple tree"
image_path = tool.execute(prompt=prompt)

print(f"Image saved at: {image_path}")
```

#### Output Format
- Returns the file path of the saved image
- Example: `generated_images/dall-e_20231015_143022.png`
- Accompanied by a JSON metadata file with generation details

#### Advanced Features
- Flexible provider selection
- Detailed metadata tracking
- Configurable generation parameters

#### Restrictions
- Requires appropriate API access for DALL-E or AWS Bedrock
- Saves files locally, requiring write permissions
- Performance depends on provider availability

### LLMVisionTool

The **LLMVisionTool** analyzes images using advanced multimodal language models. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "llm_vision_tool")                        | `llm_vision_tool`                          |
| `description`     | string | Description of the tool's purpose                                             | `Analyzes images using language models`    |
| `system_prompt`   | string | System prompt to guide the model's behavior                                   | `You are an expert in image analysis`      |
| `prompt`          | string | Question or instruction about the image                                       | `What is shown in this image?`             |
| `image_url`       | string | URL of the image to analyze                                                   | `https://example.com/image.jpg`            |
| `temperature`     | float  | Controls randomness of the model's output (0.0-1.0)                           | `0.7`                                      |
| `model_name`      | string | Specific multimodal language model to use                                     | `openrouter/openai/gpt-4o-mini`            |

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

The **LLMTool** generates answers to questions using advanced language models. (Note: Full implementation not provided; based on original documentation.)

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "llm_tool")                               | `llm_tool`                                 |
| `description`     | string | Description of the tool's purpose                                             | `Generates answers using a language model` |
| `system_prompt`   | string | Persona or system prompt to guide the model's behavior                        | `You are an expert in machine learning`    |
| `prompt`          | string | Question to ask the language model. Supports variable interpolation           | `What is the meaning of $var1$?`           |
| `temperature`     | string | Creativity level (0.0-1.0): 0.0 no creativity, 1.0 full creativity            | `0.5`                                      |
| `model_name`      | string | Specific language model to use                                                | `openrouter/openai/gpt-4o-mini`            |

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

## Git Tools

### BitbucketOperationsTool

The **BitbucketOperationsTool** performs various Bitbucket-specific Git operations like cloning, branching, committing, pushing, and pulling.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "bitbucket_operations_tool")              | `bitbucket_operations_tool`                |
| `description`     | string | Description of the tool's purpose                                             | `Performs Bitbucket operations including clone and commit` |
| `access_token`    | string | Bitbucket access token for authentication                                     | `your_access_token_here`                   |
| `operation`       | string | Operation to perform (e.g., `clone`, `create_branch`, `commit`, `push`, `pull`, `checkout`, `status`) | `clone`                                    |
| `repo_url`        | string | URL of the Bitbucket repository (required for `clone`)                        | `https://bitbucket.org/workspace/repository.git` |
| `repo_path`       | string | Local path to the repository                                                  | `/tmp/bitbucket_repos/repository`          |
| `branch_name`     | string | Name of the branch (for `create_branch`, `push`, `checkout`)                  | `feature/new-feature`                      |
| `commit_message`  | string | Message for the commit (for `commit`)                                         | `Add new feature`                          |
| `files_to_commit` | string | Comma-separated list of files to commit (for `commit`)                        | `file1.py,file2.py`                        |

#### Key Characteristics
- Handles Bitbucket-specific Git operations
- Supports authentication via access token
- Manages repository cloning and local operations
- Provides detailed operation status

#### Supported Operations
- `clone`: Clone a repository
- `create_branch`: Create and checkout a new branch
- `commit`: Commit specified or all changes
- `push`: Push changes to remote
- `pull`: Pull updates from remote
- `checkout`: Switch to an existing branch
- `status`: Get repository status

#### Example Usage
```python
tool = BitbucketOperationsTool(access_token="your_access_token_here")

# Clone a repository
result = tool.execute(
    operation="clone",
    repo_url="https://bitbucket.org/workspace/repository.git",
    repo_path="/tmp/bitbucket_repos/repository"
)
print(result)

# Create a new branch
result = tool.execute(
    operation="create_branch",
    repo_path="/tmp/bitbucket_repos/repository",
    branch_name="feature/new-feature"
)
print(result)
```

#### Output Format
- Returns a dictionary with `status` ("success" or "error") and `message`
- Example: `{"status": "success", "message": "Repository cloned to /tmp/bitbucket_repos/repository"}`

#### Advanced Features
- Token-based authentication for private repositories
- Error logging and handling
- Flexible file committing options

#### Restrictions
- Requires valid Bitbucket access token
- Operations depend on repository existence and permissions
- Limited to Bitbucket repositories

### GitOperationsTool

The **GitOperationsTool** provides a simple interface for common Git operations like creating branches, making commits, pushing, pulling, and checking out branches.

#### Parameters

| Parameter         | Type   | Description                                                                   | Example                                    |
|-------------------|--------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string | Internal name of the tool (default: "git_operations_tool")                    | `git_operations_tool`                      |
| `description`     | string | Description of the tool's purpose                                             | `Performs Git operations on a repository`  |
| `auth_token`      | string | Authentication token for private repositories                                 | `your_github_token`                        |
| `repo_path`       | string | Local path to the Git repository                                              | `/path/to/repo`                            |
| `operation`       | string | Git operation to perform (e.g., `create_branch`, `commit`, `push`, `pull`, `checkout`) | `create_branch`                            |
| `branch_name`     | string | Name of the branch (for `create_branch`, `checkout`, `push`)                  | `feature/new-feature`                      |
| `commit_message`  | string | Commit message (for `commit`)                                                 | `Add new feature implementation`           |
| `files_to_commit` | string | Comma-separated list of files to commit or '.' for all (for `commit`)         | `file1.py,file2.py` or `.`                 |

#### Key Characteristics
- Supports common Git operations
- Handles authentication for private repositories
- Validates repository state and remote configuration
- Provides detailed error handling

#### Supported Operations
- `create_branch`: Create and checkout a new branch
- `commit`: Commit specified or all changes with auto-generated message if none provided
- `push`: Push changes to remote repository
- `pull`: Pull latest changes from remote
- `checkout`: Switch to an existing branch

#### Example Usage
```python
tool = GitOperationsTool(auth_token="your_token_here")

# Create a new branch
tool.execute(
    repo_path="/path/to/repo",
    operation="create_branch",
    branch_name="feature/new-feature"
)

# Make a commit
tool.execute(
    repo_path="/path/to/repo",
    operation="commit",
    commit_message="Add new feature",
    files_to_commit="file1.py,file2.py"
)
```

#### Output Format
- Returns a string with operation result
- Example: `Successfully created and checked out branch: feature/new-feature`

#### Advanced Features
- Automatic commit message generation based on changes
- Authentication setup for HTTPS URLs
- Detailed change analysis for commits
- Support for multiple Git providers (GitHub, GitLab, Bitbucket, Azure DevOps)

#### Restrictions
- Requires existing Git repository at `repo_path`
- Operations may fail with uncommitted changes for `checkout`
- Depends on network access for `push` and `pull`

## RAG Tools

### RagTool

The **RagTool** is an advanced Retrieval Augmented Generation (RAG) tool with metadata tracking, source attribution, and configurable processing options using LlamaIndex.

#### Parameters

| Parameter            | Type         | Description                                                                   | Example                                    |
|----------------------|--------------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`               | string       | Internal name of the tool (default: "rag_tool")                               | `rag_tool`                                 |
| `description`        | string       | Description of the tool's purpose                                             | `Advanced RAG tool with metadata tracking` |
| `vector_store`       | string       | Type of vector store to use (`chroma`, `faiss`)                               | `chroma`                                   |
| `embedding_model`    | string       | Type of embedding model (`openai`, `huggingface`, `instructor`, `bedrock`)    | `openai`                                   |
| `persist_dir`        | string       | Directory to persist the index                                                | `./storage/rag`                            |
| `document_paths`     | List[str]    | List of paths to documents to index                                           | `["./docs/file1.pdf"]`                     |
| `chunk_size`         | int          | Size of text chunks for processing                                            | `512`                                      |
| `chunk_overlap`      | int          | Overlap between chunks                                                        | `50`                                       |
| `similarity_top_k`   | int          | Number of similar chunks to retrieve                                          | `4`                                        |
| `similarity_threshold`| float       | Minimum similarity score threshold                                            | `0.6`                                      |
| `api_key`            | string       | API key for embeddings (e.g., OpenAI)                                         | `your_api_key`                             |
| `query`              | string       | Query string for searching the index (execute method)                         | `What is the main topic?`                  |
| `top_k`              | int          | Number of top results to consider (execute method)                            | `5`                                        |
| `similarity_threshold`| float      | Minimum similarity score (execute method)                                     | `0.7`                                      |

#### Key Characteristics
- Supports multiple vector stores and embedding models
- Tracks document metadata
- Provides source attribution in responses
- Lazy loading of dependencies for efficiency

#### Supported Vector Stores
- Chroma
- FAISS

#### Supported Embedding Models
- OpenAI
- HuggingFace
- Instructor
- Bedrock

#### Methods
- `add_documents(document_path, custom_metadata)`: Adds documents with optional metadata
- `execute(query, top_k, similarity_threshold)`: Queries the index and returns a `QueryResponse`

#### Example Usage
```python
tool = RagTool(
    vector_store="chroma",
    embedding_model="openai",
    persist_dir="./storage/rag",
    document_paths=["./docs/file1.pdf"]
)
response = tool.execute("What is the main topic?")
print(response)
```

#### Output Format
- Returns a `QueryResponse` object with:
  - `answer`: Generated response
  - `sources`: List of source dictionaries
  - `relevance_scores`: List of similarity scores
  - `total_chunks_searched`: Number of chunks searched
  - `query_time_ms`: Query execution time in milliseconds

#### Advanced Features
- Configurable chunking and similarity parameters
- Persistent index storage
- Detailed source tracking with metadata
- Error handling with logging

#### Restrictions
- Requires documents to be indexed before querying
- Depends on external libraries (LlamaIndex, Chroma, etc.)
- Performance varies with document size and query complexity

### RagToolBeta

The **RagToolBeta** is a simpler RAG implementation using LlamaIndex, supporting multiple vector stores and embedding models.

#### Parameters

| Parameter         | Type         | Description                                                                   | Example                                    |
|-------------------|--------------|-------------------------------------------------------------------------------|--------------------------------------------|
| `name`            | string       | Internal name of the tool (default: "rag_tool")                               | `rag_tool`                                 |
| `description`     | string       | Description of the tool's purpose                                             | `RAG tool for querying indexed documents`  |
| `vector_store`    | string       | Vector store type (`chroma`, `faiss`)                                         | `chroma`                                   |
| `embedding_model` | string       | Embedding model type (`openai`, `huggingface`, `instructor`, `bedrock`)       | `openai`                                   |
| `persist_dir`     | string       | Directory for persistence                                                     | `./storage/rag`                            |
| `document_paths`  | List[str]    | Optional list of paths to documents or directories to index                   | `["./docs/file1.pdf"]`                     |
| `query`           | string       | Query string for searching (execute method)                                   | `What is the main topic?`                  |

#### Key Characteristics
- Basic RAG functionality
- Supports multiple vector stores and embedding models
- Persists index to disk
- Simpler than `RagTool` with fewer configuration options

#### Supported Vector Stores
- Chroma
- FAISS

#### Supported Embedding Models
- OpenAI
- HuggingFace
- Instructor
- Bedrock

#### Methods
- `add_documents(document_path)`: Adds documents to the index
- `execute(query)`: Queries the index and returns a response string

#### Example Usage
```python
tool = RagToolBeta(
    vector_store="chroma",
    embedding_model="openai",
    persist_dir="./storage/rag",
    document_paths=["./docs/file1.pdf"]
)
print(tool.execute("What is the main topic?"))
```

#### Output Format
- Returns a string response from the query engine

#### Advanced Features
- Automatic index persistence
- Simple document loading from files or directories
- Error logging

#### Restrictions
- No advanced configuration like chunk size or similarity threshold
- Requires documents to be added before querying
- Depends on LlamaIndex and related libraries

### DocumentMetadata

The **DocumentMetadata** class defines metadata for indexed documents in the `RagTool`.

#### Parameters

| Parameter        | Type         | Description                                                                   | Example                                    |
|------------------|--------------|-------------------------------------------------------------------------------|--------------------------------------------|
| `source_path`    | string       | Path to the document                                                          | `./docs/file1.pdf`                         |
| `file_type`      | string       | File extension or type                                                        | `.pdf`                                     |
| `creation_date`  | datetime     | File creation date                                                            | `2025-03-02 11:05:51`                      |
| `last_modified`  | datetime     | File last modified date                                                       | `2025-03-02 11:05:51`                      |
| `chunk_size`     | int          | Size of text chunks                                                           | `512`                                      |
| `overlap`        | int          | Overlap between chunks                                                        | `50`                                       |
| `custom_metadata`| Dict[str, Any] | Optional custom metadata                                                    | `{"author": "John Doe"}`                   |

#### Key Characteristics
- Structured metadata for document tracking
- Supports custom metadata fields
- Used internally by `RagTool`

#### Example Usage
```python
metadata = DocumentMetadata(
    source_path="./docs/file1.pdf",
    file_type=".pdf",
    creation_date=datetime.fromtimestamp(1614782751),
    last_modified=datetime.fromtimestamp(1614782751),
    chunk_size=512,
    overlap=50
)
```

#### Restrictions
- Used as a data model, not a standalone tool
- Requires Pydantic for validation

### QueryResponse

The **QueryResponse** class structures the response from `RagTool` queries with source attribution.

#### Parameters

| Parameter           | Type         | Description                                                                   | Example                                    |
|---------------------|--------------|-------------------------------------------------------------------------------|--------------------------------------------|
| `answer`            | string       | Generated response to the query                                               | `The main topic is AI.`                    |
| `sources`           | List[Dict]   | List of source dictionaries with content and metadata                         | `[ {"content": "AI is...", "source_path": "./docs/file1.pdf"} ]` |
| `relevance_scores`  | List[float]  | List of similarity scores for each source                                     | `[0.95, 0.87]`                            |
| `total_chunks_searched`| int       | Number of chunks searched                                                     | `10`                                       |
| `query_time_ms`     | float        | Query execution time in milliseconds                                          | `123.45`                                   |

#### Key Characteristics
- Structured response format
- Includes relevance scores and source details
- Supports `len()` and `str()` operations

#### Example Usage
```python
response = QueryResponse(
    answer="The main topic is AI.",
    sources=[{"content": "AI is...", "source_path": "./docs/file1.pdf"}],
    relevance_scores=[0.95],
    total_chunks_searched=10,
    query_time_ms=123.45
)
print(response)  # Prints "The main topic is AI."
```

#### Restrictions
- Used as a data model within `RagTool`
- Requires Pydantic for validation
