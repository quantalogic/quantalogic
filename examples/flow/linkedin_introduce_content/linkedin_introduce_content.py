#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru>=0.7.2",
#     "litellm==1.61.0",
#     "pydantic>=2.0.0",
#     "asyncio",
#     "jinja2>=3.1.0",
#     "quantalogic",
#     "instructor>=0.5.2",
#     "typer>=0.9.0",
#     "rich>=13.0.0",
#     "pyperclip>=1.8.2",
#     "tenacity>=8.0.0"  # Added for retry logic in flow.py
# ]
# ///

import asyncio
import os
from pathlib import Path
from typing import Annotated, List, Optional

import pyperclip
import typer
from loguru import logger
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType

# Initialize Typer app and rich console
app = typer.Typer(help="Convert a markdown file to a viral LinkedIn post")
console = Console()

# Default models
DEFAULT_ANALYSIS_MODEL = "gemini/gemini-2.0-flash"
DEFAULT_WRITING_MODEL = "openrouter/deepseek/deepseek-r1"  # Good for creative writing
DEFAULT_CLEANING_MODEL = "gemini/gemini-2.0-flash"  # Default cleaning model
DEFAULT_FORMATTING_MODEL = "gemini/gemini-2.0-flash"  # Default formatting model

# Define Pydantic models for structured output
class ContentAnalysis(BaseModel):
    content_type: str  # "tutorial", "software_introduction", "case_study", etc.
    primary_topic: str
    target_audience: List[str]
    key_points: List[str]
    title: str

class ViralStrategy(BaseModel):
    hook_type: str  # "question", "statistic", "counter_intuitive", etc.
    value_proposition: str
    suggested_hashtags: List[str]
    engagement_tactics: List[str]

# Node: Read Markdown File
@Nodes.define(output="markdown_content")
async def read_markdown_file(file_path: str) -> str:
    """Read content from a markdown file."""
    try:
        file_path = os.path.expanduser(file_path)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise ValueError(f"File not found: {file_path}")
        
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        
        logger.info(f"Read markdown content from {file_path}, length: {len(content)} characters")
        return content
    except Exception as e:
        logger.error(f"Error reading markdown file {file_path}: {e}")
        raise

# Node: Analyze Content Type and Structure
@Nodes.structured_llm_node(
    system_prompt="You are an expert content analyst specializing in technical and professional content. Your task is to analyze markdown content and extract key information about it.",
    output="content_analysis",
    response_model=ContentAnalysis,
    prompt_template="""
Analyze the following markdown content to determine its type, topic, target audience, key points, and title.

Content types may include:
- Tutorial/How-to guide
- Software/Tool introduction
- Technical concept explanation
- Case study
- Research summary
- Opinion/Thought leadership
- Industry news/Update

Provide a focused analysis that identifies:
1. The primary content type
2. The main topic/subject
3. The intended audience (who would benefit most)
4. 3-5 key points or takeaways
5. An appropriate title (or extract the existing title)

Here's the content:

{{markdown_content}}
"""
)
async def analyze_content(markdown_content: str, model: str, mock: bool = False) -> ContentAnalysis:
    """Analyze markdown content to determine its type and structure."""
    logger.debug(f"analyze_content called with model: {model}, mock: {mock}")
    if mock:
        logger.info("Mocking content analysis due to quota exhaustion or testing")
        return ContentAnalysis(
            content_type="Software/Tool introduction",
            primary_topic="Sample Topic",
            target_audience=["Developers", "Tech Enthusiasts"],
            key_points=["Point 1", "Point 2", "Point 3"],
            title="Sample Title"
        )
    # LLM call handled by decorator, model explicitly passed
    pass

# Node: Determine Viral Strategy
@Nodes.structured_llm_node(
    system_prompt="You are a social media growth strategist who specializes in creating viral LinkedIn content. Your task is to analyze content and determine the best strategy to make it go viral.",
    output="viral_strategy",
    response_model=ViralStrategy,
    prompt_template="""
Based on the following content analysis, determine the best strategy to make a LinkedIn post about this content go viral.

Content Analysis:
- Type: {{content_analysis.content_type}}
- Topic: {{content_analysis.primary_topic}}
- Target Audience: {{content_analysis.target_audience}}
- Key Points: {{content_analysis.key_points}}
- Title: {{content_analysis.title}}

Provide a viral strategy that includes:
1. The best hook type for the introduction (question, surprising statistic, counter-intuitive statement, etc.)
2. A clear value proposition (what will readers gain from engaging with this content)
3. 2-4 relevant hashtags that could increase visibility (without being spammy)
4. 2-3 engagement tactics (e.g., asking a question, requesting opinions, prompting shares)

Your strategy should be tailored to the specific content and audience, optimized for LinkedIn's algorithm and professional audience.
"""
)
async def determine_viral_strategy(content_analysis: ContentAnalysis, model: str) -> ViralStrategy:
    """Determine the best strategy to make this content viral on LinkedIn."""
    logger.debug(f"determine_viral_strategy called with model: {model}")
    pass

# Node: Generate LinkedIn Post
@Nodes.llm_node(
    system_prompt="""You are an expert LinkedIn content creator who specializes in crafting viral posts that drive engagement and shares.
Your posts are known for being authentic, insightful, and providing clear value to readers.
You understand the LinkedIn algorithm favors content that:
1. Creates meaningful conversations through comments
2. Keeps people on the platform (vs. immediately directing to external links)
3. Appeals to professional growth and development
4. Uses an approachable, conversational tone while maintaining professionalism

Your task is to create a compelling LinkedIn post that introduces existing content in a way that maximizes engagement and visibility.""",
    output="linkedin_post",
    prompt_template="""
# Content to Promote
Title: {{content_analysis.title}}
Type: {{content_analysis.content_type}}
Topic: {{content_analysis.primary_topic}}
Target Audience: {{", ".join(content_analysis.target_audience)}}
Key Points:
{% for point in content_analysis.key_points %}
- {{point}}
{% endfor %}

# Viral Strategy
Hook Type: {{viral_strategy.hook_type}}
Value Proposition: {{viral_strategy.value_proposition}}
Hashtags: {{", ".join(viral_strategy.suggested_hashtags)}}
Engagement Tactics:
{% for tactic in viral_strategy.engagement_tactics %}
- {{tactic}}
{% endfor %}

# Content Preview (First 500 chars)
{{markdown_content[:500]}}...

{% if intent %}
# User Intent for Post
{{intent}}
{% endif %}

# LinkedIn Post Requirements
1. Create a scroll-stopping hook using the recommended hook type
2. Present the value proposition clearly in the first 2-3 lines
3. Preview the key points without giving everything away
4. Include a clear call-to-action that encourages engagement
5. Format the post for readability (short paragraphs, emojis as bullets, space between sections)
6. Include 2-3 suggested hashtags at the end
7. Keep the post between 1000-1300 characters for optimal engagement
8. No links in the post body (mention they're in the comments/profile if needed)
9. Use simple, direct language - avoid corporate jargon and buzzwords
10. Include a question or prompt for comments to drive engagement
{% if intent %}
11. Ensure the post aligns with the user's intent: {{intent}}
{% endif %}

Write a LinkedIn post that would make this content go viral.
"""
)
async def generate_linkedin_post(
    content_analysis: ContentAnalysis, 
    viral_strategy: ViralStrategy, 
    markdown_content: str,
    model: str,
    intent: Optional[str] = None
) -> str:
    """Generate a LinkedIn post designed for maximum virality."""
    logger.debug(f"generate_linkedin_post called with model: {model}")
    pass

# Node: Clean LinkedIn Post
@Nodes.llm_node(
    system_prompt="You are an editor who specializes in optimizing social media posts. Your task is to refine a LinkedIn post to maximize readability and engagement.",
    output="cleaned_post",
    prompt_template="""
Review and refine the following LinkedIn post to ensure it's optimized for engagement, readability, and conversion:

{{linkedin_post}}

Guidelines for your optimization:
1. Ensure it starts with a strong hook
2. Use a conversational tone that feels authentic
3. Break up long paragraphs (no more than 1-2 lines per paragraph)
4. Use strategic line breaks between sections
5. Make sure any emojis are used consistently and effectively
6. Include a clear call-to-action
7. Keep hashtags (2-3 maximum) at the end
8. Remove any links from the body (these can be mentioned as "link in comments")
9. Ensure the total length is 1000-1300 characters (current length: {{linkedin_post|length}})
10. Make sure formatting is LinkedIn-friendly (no markdown, etc.)

Return only the cleaned, optimized LinkedIn post with no additional explanation.
"""
)
async def clean_linkedin_post(linkedin_post: str, model: str) -> str:
    """Clean and optimize the LinkedIn post for maximum impact."""
    logger.debug(f"clean_linkedin_post called with model: {model}")
    pass

# Node: Format LinkedIn Post for Platform
@Nodes.llm_node(
    system_prompt="You are an expert LinkedIn post formatter who ensures content follows LinkedIn's best practices and formatting requirements.",
    output="formatted_post",
    prompt_template="""
Format the following LinkedIn post to make it platform-ready:

{{cleaned_post}}

Formatting requirements:
1. Remove any markdown formatting (bold, italic, etc.) as LinkedIn doesn't support it
2. Replace section headers or dividers with the 👉 emoji
3. Ensure emojis are used effectively but not excessively
4. Maintain line breaks for readability
5. Ensure hashtags remain at the end
6. Preserve the conversational tone and all content
7. Make no changes to the actual message content beyond formatting

Return only the formatted LinkedIn post with no additional explanation.
"""
)
async def format_linkedin_post(cleaned_post: str, model: str) -> str:
    """Format the LinkedIn post to remove markdown and use proper LinkedIn formatting."""
    logger.debug(f"format_linkedin_post called with model: {model}")
    pass

# Node: Save LinkedIn Post
@Nodes.define(output="output_file_path")
async def save_linkedin_post(cleaned_post: str, file_path: str) -> str:
    """Save the LinkedIn post to a file."""
    try:
        file_path_expanded = os.path.expanduser(file_path)
        output_path = Path(file_path_expanded).with_suffix(".linkedin.md")
        with output_path.open("w", encoding="utf-8") as f:
            f.write(cleaned_post)
        logger.info(f"Saved LinkedIn post to: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"Error saving LinkedIn post: {e}")
        raise

# Node: Copy to Clipboard
@Nodes.define(output="clipboard_status")
async def copy_to_clipboard(cleaned_post: str, do_copy: bool) -> str:
    """Copy the final LinkedIn post to clipboard if do_copy is True."""
    if do_copy:
        try:
            pyperclip.copy(cleaned_post)
            logger.info("Copied LinkedIn post to clipboard")
            return "Content copied to clipboard"
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            return f"Failed to copy to clipboard: {str(e)}"
    else:
        logger.info("Clipboard copying skipped as per user preference")
        return "Clipboard copying skipped"

# Create the workflow using fluent API
def create_linkedin_content_workflow() -> Workflow:
    """Create a workflow to convert a markdown file to a viral LinkedIn post."""
    # Create workflow starting with the first node
    workflow = (
        Workflow("read_markdown_file")
        .then("analyze_content")  # Analysis node with dynamically mapped model
        .then("determine_viral_strategy")  # Strategy node with dynamically mapped model
        .then("generate_linkedin_post")  # Generate post with dynamically mapped model
        .then("clean_linkedin_post")  # Clean post with dynamically mapped model
        .then("format_linkedin_post")  # Format post for LinkedIn platform
        .then("save_linkedin_post")  # Save to file
        .then("copy_to_clipboard")  # Copy to clipboard if requested
    )
    
    # Add input mappings for model parameters
    workflow.node_input_mappings = {
        "analyze_content": {"model": "analysis_model", "mock": "mock"},
        "determine_viral_strategy": {"model": "analysis_model"},
        "generate_linkedin_post": {"model": "writing_model", "intent": "intent"},
        "clean_linkedin_post": {"model": "cleaning_model"},
        "format_linkedin_post": {"model": "formatting_model"},
    }
    
    return workflow

# Observer for tracking workflow progress
def progress_observer(event: WorkflowEvent) -> None:
    """Track workflow progress and display feedback."""
    if event.event_type == WorkflowEventType.NODE_STARTED:
        logger.info(f"Starting step: {event.node_name}")
    elif event.event_type == WorkflowEventType.NODE_COMPLETED:
        logger.info(f"Completed step: {event.node_name}")
    elif event.event_type == WorkflowEventType.NODE_FAILED:
        logger.error(f"Failed step: {event.node_name} - {event.exception}")
    elif event.event_type == WorkflowEventType.WORKFLOW_COMPLETED:
        logger.info("LinkedIn post generation workflow completed")

def get_multiline_input(prompt_text: str) -> str:
    """Get multiline input from the user with a nice UX.
    
    User can press Ctrl+D (Unix) or Ctrl+Z (Windows) followed by Enter to finish input.
    """
    console.print(f"\n[bold blue]{prompt_text}[/]")
    console.print("[dim](Enter your text; press Ctrl+D (Unix) or Ctrl+Z+Enter (Windows) when done)[/dim]")
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    return "\n".join(lines)

# Function to Run the Workflow
async def run_workflow(
    file_path: str,
    analysis_model: str,
    writing_model: str,
    cleaning_model: str,
    formatting_model: str,
    copy_to_clipboard_flag: bool = True,
    intent: Optional[str] = None,
    mock_analysis: bool = False
) -> dict:
    """Execute the workflow with the given file path and models."""
    file_path = os.path.expanduser(file_path)
        
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise ValueError(f"File not found: {file_path}")

    # Initial context with model keys for dynamic mapping
    initial_context = {
        "file_path": file_path,
        "analysis_model": analysis_model,
        "writing_model": writing_model,
        "cleaning_model": cleaning_model,
        "formatting_model": formatting_model,
        "do_copy": copy_to_clipboard_flag,
        "intent": intent,
        "mock": mock_analysis
    }

    logger.debug(f"Initial context: {initial_context}")  # Debug to verify defaults

    try:
        workflow = create_linkedin_content_workflow()
        # Add progress observer
        workflow.add_observer(progress_observer)
        engine = workflow.build()
        result = await engine.run(initial_context)
        
        if "formatted_post" not in result or not result["formatted_post"]:
            logger.warning("No LinkedIn post generated.")
            raise ValueError("Workflow completed but no post content was generated.")
        
        logger.info("Workflow completed successfully")
        return result
    except Exception as e:
        logger.error(f"Error during workflow execution: {e}")
        raise

async def display_results(formatted_post: str, output_file_path: str, copy_to_clipboard_flag: bool):
    """Async helper function to display results with animation."""
    console.print("\n[bold green]Generated LinkedIn Post:[/]")
    console.print(Panel(Markdown(formatted_post), border_style="blue"))
    
    if copy_to_clipboard_flag:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            progress.add_task("[cyan]Copying to clipboard...", total=None)
            await asyncio.sleep(1)  # Simulate some processing time for effect
        console.print("[green]✓ Content copied to clipboard![/]")
    else:
        console.print("[yellow]Clipboard copying skipped as per user preference[/]")
    
    console.print(f"[green]✓ LinkedIn post saved to:[/] {output_file_path}")

@app.command()
def create_post(
    file_path: Annotated[str, typer.Argument(help="Path to the markdown file (supports ~ expansion)")],
    analysis_model: Annotated[str, typer.Option(help="LLM model for content analysis")] = DEFAULT_ANALYSIS_MODEL,
    writing_model: Annotated[str, typer.Option(help="LLM model for LinkedIn post writing")] = DEFAULT_WRITING_MODEL,
    cleaning_model: Annotated[str, typer.Option(help="LLM model for cleaning LinkedIn post")] = DEFAULT_CLEANING_MODEL,
    formatting_model: Annotated[str, typer.Option(help="LLM model for formatting LinkedIn post")] = DEFAULT_FORMATTING_MODEL,
    copy_to_clipboard_flag: Annotated[bool, typer.Option("--copy/--no-copy", help="Copy the final post to clipboard")] = True,
    intent: Annotated[Optional[str], typer.Option("--intent", "-i", help="Intent or specific focus for the LinkedIn post")] = None,
    mock_analysis: Annotated[bool, typer.Option("--mock-analysis/--no-mock", help="Mock the analysis step for testing")] = False,
):
    """Generate a viral LinkedIn post from a markdown file containing a tutorial or software introduction."""
    try:
        # Debug model values
        logger.debug(f"CLI Models - Analysis: {analysis_model}, Writing: {writing_model}, Cleaning: {cleaning_model}, Formatting: {formatting_model}")
        
        # If intent not provided, prompt the user for multi-line input
        if intent is None:
            intent = get_multiline_input("What is your intent or specific focus for this LinkedIn post?")
            
            # If user doesn't provide intent after prompting, set to None to avoid empty string
            if not intent.strip():
                intent = None
            else:
                console.print(f"[green]Intent captured[/] ({len(intent)} characters)")
        
        with console.status(f"Processing [bold blue]{file_path}[/]..."):
            result = asyncio.run(run_workflow(
                file_path,
                analysis_model,
                writing_model,
                cleaning_model,
                formatting_model,
                copy_to_clipboard_flag,
                intent,
                mock_analysis
            ))
        
        formatted_post = result["formatted_post"]
        output_file_path = result.get("output_file_path", "Not saved")
        
        # Run the async display function
        asyncio.run(display_results(formatted_post, output_file_path, copy_to_clipboard_flag))
    
    except Exception as e:
        logger.error(f"Failed to run workflow: {e}")
        console.print(f"[bold red]Error:[/] {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()