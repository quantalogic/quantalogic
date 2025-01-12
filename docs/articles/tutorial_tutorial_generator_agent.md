# Building a Tutorial an AI Agent with the Quantalogic ReAct Framework

Picture this: You're tasked with creating 10 detailed tutorials by tomorrow morning. Sounds impossible? Not anymore! Let me show you how I automated this exact challenge using the Quantalogic ReAct framework, saving 8 hours of work in the process.

## Why Should You Care? 🤔

Before we dive in, let's address the elephant in the room: Why build an AI tutorial writer?

- ⏱️ **Save Time**: Turn a 4-hour writing session into a 15-minute task
- 🎯 **Consistency**: Generate uniformly structured content every time
- 🔄 **Rapid Iteration**: Update tutorials in seconds based on feedback
- 📚 **Scale**: Create multiple tutorials simultaneously 

The full code is available [here](../../examples/07-write-tutorial.py).

**Why is this important?** In an age where engaging, high-quality educational resources are paramount, leveraging AI can significantly enhance the learning experience, catering to the unique needs of your audience.

**What will you learn?** You'll learn to set up your development environment, gather user input interactively, and utilize the ReAct framework for automatic content generation.

**How can you apply this knowledge?** With practical examples and step-by-step instructions, you'll leave with a toolset ready for immediate application.

**When should you start?** Right now! Let’s dive in.

## Understanding the ReAct Framework

The Quantalogic ReAct framework is a versatile platform designed to integrate various AI tools seamlessly. It empowers users to create dynamic written content with features that include:

- **Interactive Input Collection**: Gather real-time user preferences.
- **Dynamic Content Generation**: Automatically produce structured educational content.
- **Feedback Mechanisms**: Monitor and adapt based on user interactions.

By harnessing these features, you can craft educational materials that are both engaging and informative.

## Setting Up Your Environment

To begin using the QLAgent ReAct framework, ensure you have the following:

1. **Python 3.12 or newer** installed on your system.
2. Required libraries for interaction and management. Install them using pip:

   ```bash
   pip install rich quantalogic
   ```

3. **API Keys**: Set up your required API keys as environment variables, such as `DEEPSEEK_API_KEY`. Other models like OpenAI GPT-4 or Anthropic Claude can be used as well, provided you set their respective API keys.

## Creating Your Tutorial Writer

### Agent Initialization

The initial step in building your tutorial agent is to set up the QLAgent with the necessary tools.

```python
import os
from rich.console import Console
from rich.prompt import Confirm, Prompt
from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    InputQuestionTool,
    ListDirectoryTool,
    LLMTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReplaceInFileTool,
    RipgrepTool,
    SearchDefinitionNames,
    WriteFileTool,
)

MODEL_NAME = "openrouter/deepseek/deepseek-chat"  # You can also use other models like gpt-4o-mini or claude-3.5-sonnet

if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        SearchDefinitionNames(),
        RipgrepTool(),
        WriteFileTool(),
        ReadFileTool(),
        ReplaceInFileTool(),
        ReadFileBlockTool(),
        ListDirectoryTool(),
        InputQuestionTool(),
        LLMTool(model_name=MODEL_NAME, on_token=console_print_token),
    ],
)
```

### Spinner Functions

To enhance user experience, include spinner functions. These will provide visual feedback during content generation.

```python
spinner = None

def console_spinner_on(event: str, data: Any | None = None) -> None:
    global spinner
    console = Console()
    spinner = console.status(f"Processing: {event}")
    spinner.start()

def console_spinner_off(event: str, data: Any | None = None) -> None:
    global spinner
    if spinner:
        spinner.stop()
```

### Monitoring Events

The framework enables comprehensive event monitoring. This allows you to track task execution stages effectively:

```python
agent.event_emitter.on(
    [
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
        "error_max_iterations_reached",
    ],
    console_print_events,
)

agent.event_emitter.on(event=["task_solve_start"], listener=console_spinner_on)
agent.event_emitter.on(event=["task_solve_end"], listener=console_spinner_off)
agent.event_emitter.on(event=["stream_chunk"], listener=console_print_token)
agent.event_emitter.on(event=["stream_chunk"], listener=console_spinner_off)
```

### User Input Function

Next, create a function to gather user input for the tutorial details, making the process interactive:

```python
def interactive_task_prompt(
    default_topic: str = "Python",
    default_chapters: int = 3,
    default_level: str = "Beginner",
    default_words: int = 500,
    default_target_dir: str = "./tutorial",
) -> dict:
    console = Console()
    console.print("[bold green]Interactive Tutorial Planner[/bold green]")
    console.print("Let's create an awesome tutorial together! 📘", style="italic")

    topic = Prompt.ask("What topic would you like to write about?", default=default_topic)
    chapters = Prompt.ask("How many chapters do you want?", default=str(default_chapters))

    while not (chapters.isdigit() and int(chapters) > 0):
        console.print("[red]Please enter a valid number of chapters (greater than 0).[/red]")
        chapters = Prompt.ask("How many chapters do you want?", default=str(default_chapters))

    level = Prompt.ask("What difficulty level?", default=default_level, choices=["Beginner", "Intermediate", "Advanced"])
    words = Prompt.ask("Target words per chapter?", default=str(default_words))

    while not (words.isdigit() and int(words) > 0):
        console.print("[red]Please enter a valid number of words (greater than 0).[/red]")
        words = Prompt.ask("Target words per chapter?", default=str(default_words))

    target_dir = Prompt.ask("Target directory for the tutorial?", default=default_target_dir)

    console.print("\n[bold]Tutorial Details:[/bold]")
    console.print(f"Topic: [cyan]{topic}[/cyan]")
    console.print(f"Chapters: [cyan]{chapters}[/cyan]")
    console.print(f"Level: [cyan]{level}[/cyan]")
    console.print(f"Words per Chapter: [cyan]{words}[/cyan]")
    console.print(f"Target Directory: [cyan]{target_dir}[/cyan]")

    is_confirmed = Confirm.ask("Are these details correct?")

    if not is_confirmed:
        console.print("[yellow]Tutorial planning cancelled.[/yellow]")
        return {}

    return {"topic": topic, "chapters": int(chapters), "level": level, "words": int(words), "target_dir": target_dir}
```

### Task Preparation Function

This function will create the task description utilizing the previously collected user input:

```python
def preparate_task(
    topic: str = "Python",
    chapters: int = 3,
    level: str = "Beginner",
    words: int = 500,
    target_dir: str = "./tutorial",
) -> str:
    task_details = interactive_task_prompt(
        default_topic=topic,
        default_chapters=chapters,
        default_level=level,
        default_words=words,
        default_target_dir=target_dir,
    )

    if not task_details:
        return ""

    return f"""
# Task 

Write the best possible tutorial on a specific topic.

## Tutorial Specifications

- Topic: {task_details['topic']}
- Number of Chapters: {task_details['chapters']}
- Difficulty Level: {task_details['level']}
- Words per Chapter: {task_details['words']}
- Target Directory: {task_details['target_dir']}

## Step 1: Assess the user's needs and preferences

Evaluate your understanding of the topic to determine if you can advance to step 2. 

If you feel unable to do so, kindly explain to the user the reasons for this.

## Step 2: Generate a tutorial based on the user's needs and preferences

- Generate a detailed outline of the tutorial first.
- Then, create the actual tutorial content based on the outline, one file per chapter. 

Guide for writing a tutorial:

- Use markdown for formatting.
- Make complex concepts understandable by explaining them simply.
- Integrate code snippets to illustrate points effectively.
- Include diagrams if necessary to clarify ideas.
- Use friendly language and emojis to make the tutorial engaging.
- Be clear and concise; begin with WHY, followed by WHAT and HOW.
"""
```

## Executing the Tutorial Generation

To generate the tutorial based on the user’s input, execute the following code:

```python
task_description = preparate_task()

if task_description:
    result = agent.solve_task(task_description, streaming=True)
    print(result)
```

## Conclusion

Congratulations! You've successfully built a functional tutorial writer using the QLAgent ReAct framework. This system can be expanded and tailored to meet specific educational needs, allowing you to produce high-quality content for learners.

### Next Steps

- **Enhance Features**: Consider adding more tools or functionalities based on your requirements.
- **Feedback Loop**: Implement a mechanism to collect user feedback on the generated tutorials for ongoing improvement.
- **Explore Advanced Options**: Think about incorporating multimedia elements or sophisticated AI capabilities to enrich your tutorials.

Happy writing! Your journey toward becoming a tutorial expert has just begun! 🎉📚
