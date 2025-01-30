# QuantaLogic

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://quantalogic.github.io/quantalogic/)



QuantaLogic is a  ReAct (Reasoning & Action) framework for building advanced AI agents. 


It seamlessly integrates large language models (LLMs) with a robust tool system, enabling agents to understand, reason about, and execute complex tasks through natural language interaction.

The `cli` version include coding capabilities comparable to Aider.

[📖 Documentation](https://quantalogic.github.io/quantalogic/)

![Video](./examples/generated_tutorials/python/quantalogic_8s.gif)


[HowTo Guide](./docs/howto/howto.md)

## Why QuantaLogic?

We created [QuantaLogic](https://www.quantalogic.app) because we saw a significant gap between the advanced AI models developed by companies like OpenAI, Anthropic, DeepSeek and their practical implementation in everyday business processes. 

> Our mission is to bridge this gap, making the power of generative AI accessible and actionable for businesses of all sizes.


## 🌟 Highlights

- **ReAct Framework**: Advanced implementation combining LLM reasoning with concrete actions
- **Universal LLM Support**: Integration with OpenAI, Anthropic, LM Studio, Bedrock, Ollama, DeepSeek V3, DeepSeek R1, via LiteLLM. Example usage: `quantalogic --model-name deepseek/deepseek-reasoner` or `quantalogic --model-name openrouter/deepseek/deepseek-r1`
- **Secure Tool System**: Docker-based code execution and file manipulation tools
- **Real-time Monitoring**: Web interface with SSE-based event visualization
- **Memory Management**: Intelligent context handling and optimization
- **Enterprise Ready**: Comprehensive logging, error handling, and validation system


## 📋 Table of Contents

- [Usage](#usage)
- [Release Notes](#release-notes)

- [Installation](#-installation)
- [Quick Start](#-quickstart)
- [Key Components](#-key-components)
- [Agent System](#-agent-system)
- [Tool System](#-tool-system)
- [Web Interface](#-web-interface)
- [Examples](#-examples)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)
- [Documentation Development](#-documentation-development)

## Usage

**Usage:** `quantalogic [OPTIONS] COMMAND i[ARGS]...`  
**Environment Variables:** Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `DEEPSEEK_API_KEY` for API integration.

**Options:**
- `--model-name TEXT`: Specify the model (litellm format, e.g., "openrouter/deepseek/deepseek-chat")
- `--log [info|debug|warning]`: Set logging level
- `--mode [code|basic|interpreter|full|code-basic|search|search-full]`: Agent mode
- `--vision-model-name TEXT`: Specify vision model (litellm format)
- `--max-tokens-working-memory INTEGER`: Maximum tokens in working memory (default: 4000)
- `--max-iterations INTEGER`: Maximum task iterations (default: 30)
- `--compact-every-n-iteration INTEGER`: Compact memory every N iterations (default: 5)
- `--no-stream`: Disable streaming output (default: enabled)
- `--help`: Show help message

**Commands:**

- `task`: Execute a task with the QuantaLogic AI Assistant
  - `--file PATH`: Path to task file
  - `--model-name TEXT`: Specify model
  - `--verbose`: Enable verbose output
  - `--mode`: Select agent capabilities
  - `--log`: Set logging level
  - `--vision-model-name`: Specify vision model
  - `--max-iterations`: Maximum task iterations
  - `--max-tokens-working-memory`: Memory limit
  - `--compact-every-n-iteration`: Memory optimization
  - `--no-stream`: Disable streaming


- `list-models`: List available models with optional filtering.
  - `--search TEXT`: Filter models by name or description.
  - `--help`: Show help message.

  Example:
  ```bash
  quantalogic list-models --search qwen
  ```

  Output:
  ```
  Model Name           Description
  -------------------  -------------------------------------------------------
  dashscope/qwen-max   Alibaba's Qwen-Max model optimized for maximum performance
  dashscope/qwen-plus  Alibaba's Qwen-Plus model offering balanced performance
  ```


## Release Notes

See our [Release Notes](RELEASE_NOTES.MD) for detailed version history and changes.

[TODO List](TODO.md)

## Environment Configuration

### Supported Models

| Model Name | API Key Environment Variable | Description |
|------------|------------------------------|-------------|
| openai/gpt-4o-mini | OPENAI_API_KEY | OpenAI's compact version of GPT-4, optimized for efficiency and cost-effectiveness while maintaining strong performance. |
| openai/gpt-4o | OPENAI_API_KEY | OpenAI's flagship model offering state-of-the-art performance across various tasks with enhanced reasoning capabilities. |
| anthropic/claude-3.5-sonnet | ANTHROPIC_API_KEY | Claude 3.5 Sonnet model from Anthropic, balancing performance and speed with strong reasoning capabilities. |
| deepseek/deepseek-chat | DEEPSEEK_API_KEY | DeepSeek's conversational model optimized for chat-based interactions and general-purpose tasks. |
| deepseek/deepseek-reasoner | DEEPSEEK_API_KEY | DeepSeek's specialized model for complex reasoning tasks and problem-solving. |
| openrouter/deepseek/deepseek-r1 | OPENROUTER_API_KEY | DeepSeek R1 model available through OpenRouter, optimized for research and development tasks. |
| openrouter/openai/gpt-4o | OPENROUTER_API_KEY | OpenAI's GPT-4o model accessible through OpenRouter platform. |
| openrouter/mistralai/mistral-large-2411 | OPENROUTER_API_KEY | Mistral's large model optimized for complex reasoning tasks, available through OpenRouter with enhanced multilingual capabilities. |
| mistral/mistral-large-2407 | MISTRAL_API_KEY | Mistral's high-performance model designed for enterprise-grade applications, offering advanced reasoning and multilingual support. |
| dashscope/qwen-max | DASHSCOPE_API_KEY | Alibaba's Qwen-Max model optimized for maximum performance and extensive reasoning capabilities. |
| dashscope/qwen-plus | DASHSCOPE_API_KEY | Alibaba's Qwen-Plus model offering balanced performance and cost-efficiency for a variety of tasks. |
| dashscope/qwen-turbo | DASHSCOPE_API_KEY | Alibaba's Qwen-Turbo model designed for fast and efficient responses, ideal for high-throughput scenarios. |

To configure the environment API key for Quantalogic using LiteLLM, set the required environment variable for your chosen provider and any optional variables like `OPENAI_API_BASE` or `OPENROUTER_REFERRER`. Use a `.env` file or a secrets manager to securely store these keys, and load them in your code using `python-dotenv`. For advanced configurations, refer to the [LiteLLM documentation](https://docs.litellm.ai/docs/).


## 📦 Installation

### Prerequisites

- Python 3.12+
- Docker (optional for code execution tools)

### Via pip

```bash
# Basic installation
pip install quantalogic
```

### From Source

```bash
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic
python -m venv .venv
source ./venv/bin/activate 
poetry install
```

## Using pipx

```
pipx install quantalogic
```


## 🚀 Quickstart

### Basic Usage





### Detailed Usage

#### Agent Modes
- code: Coding-focused agent with basic capabilities
- basic: General-purpose agent without coding tools
- interpreter: Interactive code execution agent
- full: Full-featured agent with all capabilities
- code-basic: Coding agent with basic reasoning
- search: Web search agent with Wikipedia, DuckDuckGo and SERPApi integration

#### Task Execution

Tasks can be provided:

1. Directly via `task` parameter
2. Through a file using --file parameter
3. Interactively via standard input


#### Examples


Using a task file:
```bash
quantalogic task --file tasks/example.md --verbose
```

Selecting agent mode:
```bash
quantalogic --mode interpreter task "Explain quantum computing"
```

Interactive mode:
```bash
quantalogic
```

### Using QuantaLogic With code

```python
from quantalogic import Agent

# Initialize agent with default configuration
agent = Agent(model_name="deepseek/deepseek-chat")

# Execute a task
result = agent.solve_task(
    "Create a Python function that calculates the Fibonacci sequence"
)
print(result)
```

### Environment Configuration Example

```python
import os

from quantalogic import Agent

# Verify that DEEPSEEK_API_KEY is set
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Initialize the AI agent with default configuration
agent = Agent(model_name="deepseek/deepseek-chat")

# Execute a sample task
result = agent.solve_task("Create a Python function that calculates the Fibonacci sequence")
print(result)
```

## 📖 Examples

Watch how QuantaLogic can generate complete tutorials from simple prompts:

[![Tutorial Generation Demo](./examples/generated_tutorials/python/quantalogic_long.mp4)](./examples/generated_tutorials/python/quantalogic_long.mp4)

Example prompt: [04-write-a-tutorial.md](./examples/tasks/04-write-a-tutorial.md)

Here are some practical examples to help you get started:


| Example | Description | File |
|---------|-------------|------|
| Simple Agent | A basic example of an agent implementation. | [examples/01-simple-agent.py](examples/01-simple-agent.py) |
| Agent with Event Monitoring | An example of an agent with event monitoring capabilities. | [examples/02-agent-with-event-monitoring.py](examples/02-agent-with-event-monitoring.py) |
| Agent with Interpreter | An example of an agent that includes an interpreter. | [examples/03-agent-with-interpreter.py](examples/03-agent-with-interpreter.py) |
| Agent Summary Task | An example of an agent performing a summary task. | [examples/04-agent-summary-task.py](examples/04-agent-summary-task.py) |
| Code Example | A general code example. | [examples/05-code.py](examples/05-code.py) |
| Code Screen Example | An example demonstrating code execution with screen output. | [examples/06-code-screen.py](examples/06-code-screen.py) |
| Write Tutorial | An example of generating a tutorial using the agent. | [examples/07-write-tutorial.py](examples/07-write-tutorial.py) |
| PRD Writer | An example of generating a Product Requirements Document (PRD). | [examples/08-prd-writer.py](examples/08-prd-writer.py) |
| SQL Query | An example of executing SQL queries using the agent. | [examples/09-sql-query.py](examples/09-sql-query.py) |
| Finance Agent | An example of a finance-focused agent. | [examples/10-finance-agent.py](examples/10-finance-agent.py) |
| Textual Agent Interface | An example of a textual user interface for the agent. | [examples/11-textual-agent-interface.py](examples/11-textual-agent-interface.py) |


## 🔨 Key Components

### Agent System

The core agent implements the `ReAct`paradigm, combining:

- Language model reasoning
- Tool execution capabilities
- Memory management
- Event handling
- Task validation

```python
from quantalogic import Agent
from quantalogic.tools import PythonTool, ReadFileTool

# Create agent with specific tools
agent = Agent(
    model_name="openrouter/deepseek/deepseek-chat",
    tools=[
        PythonTool(),
        ReadFileTool()
    ]
)

```

### How it works


The ReAct (Reasoning & Action) framework represents a significant advancement in the development of intelligent agents capable of autonomously reasoning through tasks and taking appropriate actions. 

QuantaLogic implements this framework, allowing integration with large language models (LLMs) to construct sophisticated agents that can tackle complex problems through natural language interaction. 

## What is a ReAct Agent?

### Basic Concept

A ReAct agent utilizes the synergy of reasoning and action. It not only processes natural language inputs but also executes actions in response to these inputs, utilizing various available tools. This functionality is particularly beneficial for environments where complex tasks can be decomposed into manageable subtasks.

### The QuantaLogic Implementation

QuantaLogic provides an effective implementation of the ReAct framework with several core components:

- **Generative Model**: This serves as the agent's brain, enabling it to interpret tasks and generate human-like text responses.
- **Memory Management**: This capability allows the agent to maintain context, keeping track of previous inputs and interactions to provide coherent responses.
- **Tool Management**: The agent has access to a diverse range of tools, enabling it to perform actions such as code execution, file manipulation, and API communication.

## How the ReAct Framework Works

### Workflow of a ReAct Agent

The following state diagram shows the core workflow of a QuantaLogic agent:

```mermaid
stateDiagram-v2
    [*] --> InitializeAgent
    InitializeAgent --> Idle: Agent Initialized

    state Idle {
        [*] --> WaitForTask
        WaitForTask --> SolveTask: Task Received
    }

    state SolveTask {
        [*] --> ResetSession
        ResetSession --> AddSystemPrompt
        AddSystemPrompt --> PreparePrompt
        PreparePrompt --> EmitTaskStartEvent
        EmitTaskStartEvent --> UpdateTokens
        UpdateTokens --> CompactMemoryIfNeeded
        CompactMemoryIfNeeded --> GenerateResponse
        GenerateResponse --> ObserveResponse
        ObserveResponse --> CheckToolExecution
        CheckToolExecution --> TaskComplete: Tool Executed (task_complete)
        CheckToolExecution --> UpdatePrompt: Tool Not Executed
        UpdatePrompt --> UpdateTokens
        TaskComplete --> EmitTaskCompleteEvent
        EmitTaskCompleteEvent --> [*]
    }

    state CompactMemoryIfNeeded {
        [*] --> CheckMemoryOccupancy
        CheckMemoryOccupancy --> CompactMemory: Memory Occupancy > MAX_OCCUPANCY
        CheckMemoryOccupancy --> [*]: Memory Occupancy <= MAX_OCCUPANCY
        CompactMemory --> [*]
    }

    state ObserveResponse {
        [*] --> ProcessResponse
        ProcessResponse --> ExecuteTool: Tool Identified
        ProcessResponse --> UpdateAnswer: No Tool Identified
        ExecuteTool --> UpdateAnswer
        UpdateAnswer --> [*]
    }



    Idle --> [*]: Task Completed
    SolveTask --> Idle: Task Completed
```

The following sequence diagram illustrates the workflow of a ReAct agent as it processes and solves a task:

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant ToolManager
    participant Memory

    User->>Agent: Submit task
    Agent->>Memory: Store task details
    Agent->>ToolManager: Retrieve tools
    ToolManager-->>Agent: Provide available tools
    Agent->>Agent: Prepare prompt for task
    Agent->>Agent: Analyze input and generate response
    Agent->>ToolManager: Execute required tool
    ToolManager-->>Agent: Return tool execution result
    Agent->>User: Present final result
```

### Key Components Explained

1. **User Input**: The agent begins by receiving a task or question from the user, which initiates the interaction.
2. **Memory Management**: Before tackling the task, the agent logs relevant task details into its memory, ensuring it has the necessary context for processing.
3. **Tool Retrieval**: The agent communicates with the ToolManager to inquire about available tools that can facilitate the required actions.
4. **Prompt Generation**: The agent constructs a prompt that outlines the task specifics, available tools, and any other pertinent context information.
5. **Analysis and Response Generation**: The agent uses its generative model to analyze the task input and formulate a response.
6. **Tool Execution**: If certain tools are needed for the task, the agent instructs the ToolManager to execute those tools, fetching the results for processing.
7. **Output to User**: Finally, the agent compiles and presents the results back to the user.

### Tool System

The QuantaLogic framework incorporates a well-defined tool system that enhances the functionality of AI agents by enabling them to perform a variety of tasks efficiently. Each tool is designed to address specific needs that arise in the context of complex problem-solving and task execution:

1. **Core Functionality**: Tools such as **AgentTool** and **LLMTool** are fundamental to the agent's operation, allowing it to manage tasks and interact with large language models. The integration of these tools enables the agent to process natural language inputs and execute corresponding actions effectively. **AgentTool** enables the agent to delegate tasks to specialized agents, and **LLMTool** provides the agent to explore a specific area of a latent space using role play.

2. **Code Execution**: Tools like **PythonTool**, **NodeJsTool**, and **ElixirTool** are vital for executing code in different programming languages. This capability allows the agent to handle programming tasks directly, facilitating real-time coding assistance and code evaluation.

3. **File Operations**: The framework includes tools for file management, such as **ReadFileTool**, **WriteFileTool**, and **ReplaceInFileTool**. These tools are essential for enabling the agent to read from and write to files, as well as update file content dynamically. This functionality supports scenarios where agents need to manipulate data or configuration files as part of the task execution process.

4. **Search Capabilities**: Tools like **RipgrepTool** and **SearchDefinitionNames** enhance the agent's ability to search through codebases and identify relevant definitions. This is crucial when dealing with large volumes of code, allowing the agent to quickly locate information necessary for problem-solving.

5. **Utility Functions**: Additional tools such as **DownloadHttpFileTool**, **ListDirectoryTool**, and **ExecuteBashCommandTool** provide broader functionality that supports various tasks, from fetching external resources to executing system commands. These utilities expand the operational scope of agents, allowing them to perform diverse actions beyond simple text processing.

6. **Documentation and Representation**: Tools like **MarkitdownTool** facilitate the generation of documentation, ensuring that output from the agent can be formatted and presented clearly. This is particularly beneficial for creating reports or guides based on the agent's findings and actions.

By integrating these tools into its architecture, QuantaLogic allows agents to perform a wide range of tasks autonomously while ensuring that they have the necessary resources and capabilities to do so effectively. This tool system is fundamental to the agent's ability to reason and act in sophisticated ways, thereby enhancing the overall utility of the framework in complex scenarios.

 

### Development

### Tools Documentation

For detailed documentation of all available tools, please see [REFERENCE_TOOLS.md](REFERENCE_TOOLS.md).
## 🔧 Development
### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/quantalogic/quantalogic.git
cd quantalogic

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
poetry install

```

### Run Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=quantalogic

# Run specific tests
pytest tests/unit
```

### Code Quality

```bash
# Format code
ruff format

# Type checking
mypy quantalogic

# Linting
ruff check quantalogic
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests
4. Implement changes
5. Submit pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📄 License

Copyright 2024 QuantaLogic Contributors

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## Project Growth
[![Star History Chart](https://api.star-history.com/svg?repos=quantalogic/quantalogic&type=Date)](https://star-history.com/#quantalogic/quantalogic&Date)

Initiated with ❤️ by Raphaël MANSUY. Founder of [Quantalogic](https://www.quantalogic.app). 
