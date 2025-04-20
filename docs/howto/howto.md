# Comprehensive Q&A How-To Guide for QuantaLogic

This document provides an improved and detailed question-and-answer format for users of QuantaLogic, based on its functionalities and capabilities. Each entry has been designed to provide clear solutions and insights for various tasks related to this powerful AI framework.

## 1. What is QuantaLogic?

### **Question:** What is QuantaLogic and what are its primary features?

**Answer:**  
QuantaLogic is a flexible AI framework that enables developers to build advanced agents capable of understanding, reasoning about, and executing complex tasks through natural language interaction. It supports both the classic **ReAct** (Reasoning & Action) paradigm and the new **CodeAct** extension:
- **ReAct Framework**: Agents reason step-by-step and use tools or code to solve tasks, adapting as they go.
- **CodeAct Extension**: Agents generate and execute Python code as their main way to act, iterating based on real results—ideal for complex, multi-step automation and advanced problem solving.
- **Universal LLM Support**: Integration with multiple large language models (LLMs) like OpenAI and DeepSeek.
- **Secure Tool System**: Uses Docker for secure code execution and file manipulation.
- **Real-time Monitoring**: A web interface allows for event visualization.
- **Memory Management**: Includes intelligent context handling and optimization.

## 1a. What is the difference between CodeAct and ReAct?

### **Question:** How is CodeAct different from ReAct, and when should I use each?

**Answer:**  
- **ReAct** lets agents reason step-by-step and use tools or code in a loop, based on the [ReAct paper](https://arxiv.org/abs/2210.03629). It's great for tasks where agents need to plan, use tools, and adapt to feedback.
- **CodeAct** builds on ReAct by making **executable Python code** the main language for agent actions. The agent writes and runs code, observes the results (including errors), and iterates until the task is solved. This is inspired by recent research ([Yang et al., 2024](https://arxiv.org/html/2402.01030v4)).

**When to use each:**
- Use **ReAct** for flexible reasoning with tool use.
- Use **CodeAct** when generating and executing code is the best way to solve a problem or automate a workflow (e.g., advanced automation, mathematical problem-solving, or when you want verifiable, step-by-step execution).

---

## 2. How Do I Install QuantaLogic?

### **Question:** What are the steps to install QuantaLogic on my system?

**Answer:**  
To install QuantaLogic, follow these steps:

1. **Prerequisites**: Ensure you have Python 3.12 or higher installed. Docker is optional but recommended.
2. **Installation via pip**:
   ```bash
   pip install quantalogic
   ```
3. **Installation from source**:
   ```bash
   git clone https://github.com/quantalogic/quantalogic.git
   cd quantalogic
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   poetry install
   ```
4. **Using pipx**:
   ```bash
   pipx install quantalogic
   ```

## 3. How Can I Quickly Get Started with QuantaLogic?

### **Question:** What is the quickest way to begin using QuantaLogic after installation?

**Answer:**  
You can start using QuantaLogic either through its CLI or programmatically in Python. Here are examples for both:

#### **CLI Example**:
```bash
quantalogic task "What is the capital of France?"
```

#### **Python Example**:
```python
import os
from quantalogic import Agent

if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

agent = Agent(model_name="deepseek/deepseek-chat")
result = agent.solve_task("Write a Python function that calculates the Fibonacci sequence.")
print(result)
```

## 4. How Do I Create and Configure an Agent?

### **Question:** What steps should I take to create a customized agent with QuantaLogic?

**Answer:**  
To create a customized agent, specify the tools and configurations during initialization:

```python
from quantalogic import Agent
from quantalogic.tools import PythonTool, ReadFileTool

agent = Agent(
    model_name="openrouter/deepseek/deepseek-chat",
    tools=[PythonTool(), ReadFileTool()]
)
```

## 5. How Do I Execute a Task Using My Agent?

### **Question:** How can I execute a task using a QuantaLogic agent?

**Answer:**  
You execute tasks by calling the `solve_task` method on your agent. For example:

```python
result = agent.solve_task("Generate a Fibonacci sequence function.")
print(result)
```

## 6. How Does Event Monitoring Work in QuantaLogic?

### **Question:** How can I monitor events during task execution?

**Answer:**  
You can set up event listeners to monitor specific tasks and actions performed by your agent:

```python
from quantalogic.console_print_events import console_print_events

agent.event_emitter.on(
    [
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end"
    ],
    console_print_events
)
```

## 7. What Tools Does QuantaLogic Provide?

### **Question:** What are some key tools available in QuantaLogic?

**Answer:**  
QuantaLogic includes several tools, each designed for specific tasks:
- **PythonTool**: Executes Python scripts.
- **NodeJsTool**: Executes Node.js scripts.
- **LLMTool**: Integrates with LLMs for text generation.
- **File Manipulation Tools**: ReadFileTool, WriteFileTool, ReplaceInFileTool for file operations.
- **Search Tools**: For searching definitions and content within specified directories.

## 8. How Can I Contribute to QuantaLogic?

### **Question:** What are the steps to contribute to the QuantaLogic project?

**Answer:**  
To contribute, follow these steps:
1. Fork the repository.
2. Create a new feature branch.
3. Write tests for your changes.
4. Implement the changes.
5. Submit a pull request.

Refer to the [CONTRIBUTING.md](../CONTRIBUTING.md) for more detailed instructions.

## 9. How Can I Run Tests for QuantaLogic?

### **Question:** What is the procedure to run tests in QuantaLogic?

**Answer:**  
To run tests, use the following commands:

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=quantalogic

# Run specific tests
pytest tests/unit
```

## 10. How Do I Stay Updated with QuantaLogic?

### **Question:** What resources can I use to stay informed about updates and new features in QuantaLogic?

**Answer:**  
You can stay updated by:
- Following the official [QuantaLogic Documentation](https://quantalogic.github.io/quantalogic/).

- Engaging with the community through forums and discussions related to QuantaLogic.

---

This comprehensive Q&A guide is designed to assist both new and experienced users in leveraging QuantaLogic's functionalities effectively. For more details, refer to the official documentation and explore the various tools and capabilities available within the QuantaLogic framework. Happy coding!

