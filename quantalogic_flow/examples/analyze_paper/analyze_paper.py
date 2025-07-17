#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "asyncio",
#     "quantalogic-py-zerox",
#     "pdf2image",
#     "pillow",
#     "quantalogic-flow>=0.6.8",
#     "typer>=0.9.0",
#     "rich>=13.0.0",
#     "pyperclip>=1.8.2",
# ]
# ///
# System dependencies:
# - poppler (for pdf2image): brew install poppler (macOS) or apt-get install poppler-utils (Linux)

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Annotated, List, Union

import pyperclip
import typer
from loguru import logger
from pydantic import BaseModel
from pyzerox import zerox
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from quantalogic_flow import Nodes, Workflow


def check_poppler():
    """Check if Poppler is installed for PDF processing."""
    try:
        subprocess.run(["pdftoppm", "-v"], stdout=subprocess.DEVNULL)
    except FileNotFoundError:
        console.print(
            "[bold red]Error:[/] Poppler not found. Install with: \n"
            "  [blue]macOS:[/] brew install poppler\n"
            "  [blue]Linux:[/] sudo apt-get install poppler-utils"
        )
        raise typer.Exit(1)

# Initialize Typer app and rich console
app = typer.Typer(help="Convert a file (PDF, text, or Markdown) to a LinkedIn post using LLMs")
console = Console()

# Default models for different phases (updated to Gemini 2.5)
DEFAULT_TEXT_EXTRACTION_MODEL = "gemini/gemini-2.5-flash"
DEFAULT_CLEANING_MODEL = "gemini/gemini-2.5-flash"
#DEFAULT_WRITING_MODEL = "deepseek/deepseek-reasoner"
#DEFAULT_WRITING_MODEL = "openrouter/openai/gpt-4o-mini"
DEFAULT_WRITING_MODEL = "openrouter/deepseek/deepseek-r1"

# Define a Pydantic model for structured output of title and authors
class PaperInfo(BaseModel):
    title: str
    authors: List[str]

# New Node: Check File Type
@Nodes.define(output="file_type")
async def check_file_type(file_path: str) -> str:
    """Determine the file type based on its extension."""
    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise ValueError(f"File not found: {file_path}")
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    elif ext == ".txt":
        return "text"
    elif ext == ".md":
        return "markdown"
    else:
        logger.error(f"Unsupported file type: {ext}")
        raise ValueError(f"Unsupported file type: {ext}")

# New Node: Read Text or Markdown File
@Nodes.define(output="markdown_content")
async def read_text_or_markdown(file_path: str, file_type: str) -> str:
    """Read content from a text or markdown file."""
    if file_type not in ["text", "markdown"]:
        logger.error(f"Node 'read_text_or_markdown' called with invalid file_type: {file_type}")
        raise ValueError(f"Expected 'text' or 'markdown', got {file_type}")
    try:
        file_path = os.path.expanduser(file_path)
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        logger.info(f"Read {file_type} content from {file_path}, length: {len(content)} characters")
        return content
    except Exception as e:
        logger.error(f"Error reading {file_type} file {file_path}: {e}")
        raise

# Node 1: Convert PDF to Markdown
@Nodes.define(output="markdown_content")
async def convert_pdf_to_markdown(
    file_path: str,
    model: str,
    custom_system_prompt: str | None = None,
    output_dir: str | None = None,
    select_pages: Union[int, List[int]] | None = None
) -> str:
    """Convert a PDF to Markdown using a vision model."""
    file_path = os.path.expanduser(file_path)
    if output_dir:
        output_dir = os.path.expanduser(output_dir)
        
    if not file_path:
        logger.error("File path is required")
        raise ValueError("File path is required")
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise ValueError(f"File not found: {file_path}")
    if not file_path.lower().endswith(".pdf"):
        logger.error(f"File must be a PDF: {file_path}")
        raise ValueError(f"File must be a PDF: {file_path}")

    if custom_system_prompt is None:
        custom_system_prompt = (
            "Convert the PDF page to a clean, well-formatted Markdown document. "
            "Preserve structure, headings, and any code or mathematical notation. "
            "For images and charts, create a literal description of what is visible. "
            "Return only pure Markdown content, excluding any metadata or non-Markdown elements."
        )

    try:
        logger.info(f"Calling zerox with model: {model}, file: {file_path}")
        zerox_result = await zerox(
            file_path=file_path,
            model=model,
            system_prompt=custom_system_prompt,
            output_dir=output_dir,
            select_pages=select_pages
        )

        markdown_content = ""
        if hasattr(zerox_result, 'pages') and zerox_result.pages:
            markdown_content = "\n\n".join(
                page.content for page in zerox_result.pages
                if hasattr(page, 'content') and page.content
            )
        elif isinstance(zerox_result, str):
            markdown_content = zerox_result
        elif hasattr(zerox_result, 'markdown'):
            markdown_content = zerox_result.markdown
        elif hasattr(zerox_result, 'text'):
            markdown_content = zerox_result.text
        else:
            markdown_content = str(zerox_result)
            logger.warning("Unexpected zerox_result type; converted to string.")

        if not markdown_content.strip():
            logger.warning("Generated Markdown content is empty.")
            return ""

        logger.info(f"Extracted Markdown content length: {len(markdown_content)} characters")
        return markdown_content
    except Exception as e:
        logger.error(f"Error converting PDF to Markdown: {e}")
        raise

# Node: Save Markdown Content
@Nodes.define(output="markdown_file_path")
async def save_markdown_content(markdown_content: str, file_path: str) -> str:
    """Save the extracted markdown content to a file."""
    try:
        file_path_expanded = os.path.expanduser(file_path)
        output_path = Path(file_path_expanded).with_suffix(".extracted.md")
        with output_path.open("w", encoding="utf-8") as f:
            f.write(markdown_content)
        logger.info(f"Saved extracted markdown content to: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"Error saving markdown content: {e}")
        raise

# Node: Extract First 100 Lines
@Nodes.define(output="first_100_lines")
async def extract_first_100_lines(markdown_content: str) -> str:
    """Extract the first 100 lines from the Markdown content."""
    try:
        lines = markdown_content.splitlines()
        first_100 = lines[:100]
        result = "\n".join(first_100)
        logger.info(f"Extracted {len(first_100)} lines from Markdown content")
        return result
    except Exception as e:
        logger.error(f"Error extracting first 100 lines: {e}")
        raise

# Node: Extract Title and Authors using Structured LLM
@Nodes.structured_llm_node(
    system_prompt="You are an AI assistant tasked with extracting the title and authors from a research paper's Markdown text.",
    output="paper_info",
    response_model=PaperInfo,
    prompt_template="Extract the title and a list of authors from the following Markdown text. "
                    "The title is typically the first heading or prominent text, and authors are usually listed below it:\n\n{{first_100_lines}}"
)
async def extract_paper_info(first_100_lines: str) -> PaperInfo:
    """Extract title and authors from the first 100 lines."""
    pass

# Node: Extract Title String
@Nodes.define(output="title_str")
async def extract_title_str(paper_info: PaperInfo) -> str:
    """Extract title string from PaperInfo object."""
    try:
        title_str = paper_info.title
        logger.info(f"Extracted title: '{title_str}'")
        return title_str
    except Exception as e:
        logger.error(f"Error extracting title: {e}")
        raise

# Node: Extract Authors String
@Nodes.define(output="authors_str")
async def extract_authors_str(paper_info: PaperInfo) -> str:
    """Extract authors string from PaperInfo object."""
    try:
        authors_str = ", ".join(paper_info.authors)
        logger.info(f"Extracted authors: '{authors_str}'")
        return authors_str
    except Exception as e:
        logger.error(f"Error extracting authors: {e}")
        raise

# Node: Generate LinkedIn Post using LLM
@Nodes.llm_node(
    system_prompt="You are an AI expert who enjoys sharing interesting papers and articles with a professional audience.",
    output="draft_post_content",
    prompt_template="""
## The task to do
As an AI expert that likes to share interesting papers and articles, write the best possible LinkedIn post to introduce a new research paper "{{title_str}}" from {{authors_str}}. Use the full Markdown content of the paper provided below to inform your post.

## Paper Content
{{markdown_content}}

## Message to convey
Start with an intriguing question to capture attention, applying a psychology framework to maximize engagement and encourage sharing.

Structure the post in:

WHY -> WHAT -> HOW

Explain concepts clearly and simply, as if teaching a curious beginner, without citing any specific teaching methods.
Use the Richard Feynman technique to ensure clarity and understanding. Never cite Feynman explicitly.

## Recommendations
- Use Markdown formatting, keeping the post arround or under {{max_character_count}} characters.
- Follow best practices for tutorials: short paragraphs, bullet points, and subheadings.
- Maintain a professional tone.
- Avoid emojis, bold, or italic text.
- Use 👉 to introduce sections.
- Focus on substance over hype. Avoid clichéd phrases like 'revolution', 'path forward', 'new frontier', 'real-world impact', 'future of', 'step forward', 'groundbreaking', or 'game-changer'. Use clear, concise, original language instead.
- Keep it non-jargony, precise, engaging, and pleasant to read.
- Avoid clichéd openings like "In the realm of..." or "In the rapidly evolving field...".
- Suggest a compelling title for the post.
"""
)
async def generate_linkedin_post(title_str: str, authors_str: str, markdown_content: str, max_character_count: int) -> str:
    """Generate a LinkedIn post in Markdown using title, authors, full markdown content, and maximum character count."""
    pass

# Node: Save Draft LinkedIn Post
@Nodes.define(output="draft_post_file_path")
async def save_draft_post_content(draft_post_content: str, file_path: str) -> str:
    """Save the draft LinkedIn post content to a markdown file."""
    try:
        file_path_expanded = os.path.expanduser(file_path)
        output_path = Path(file_path_expanded).with_suffix(".draft.md")
        with output_path.open("w", encoding="utf-8") as f:
            f.write(draft_post_content)
        logger.info(f"Saved draft LinkedIn post to: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"Error saving draft post content: {e}")
        raise

# Node: Format LinkedIn Post for publishing
@Nodes.llm_node(
    system_prompt="You are an expert LinkedIn post formatter who prepares content for direct publishing.",
    output="post_content",
    prompt_template="""
Format the following draft LinkedIn post for direct publishing:

{{draft_post_content}}

Instructions:
1. Remove any draft indicators, meta-comments, or markdown formatting symbols like ## or **.
2. Start directly with the title.
3. Ensure the formatting is clean and ready for LinkedIn publishing.
4. Keep all the valuable content but remove anything that suggests this is a draft or template.
5. Maintain the 👉 emoji for section introductions.
6. Output only the ready-to-publish content with no additional comments.
7. Preserve paragraph breaks and bullet points in a LinkedIn-friendly format.
8. Ensure no Hashtags or links are included in the post.
"""
)
async def format_linkedin_post(draft_post_content: str) -> str:
    """Clean and format the LinkedIn post for publishing."""
    pass

# Node: Clean Markdown Syntax with Regex
@Nodes.define(output="cleaned_post_content")
async def clean_markdown_syntax(post_content: str) -> str:
    """Clean any remaining markdown syntax from the post content using regex."""
    import re
    try:
        # Remove bold syntax
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', post_content)
        # Remove italic syntax (both * and _)
        cleaned = re.sub(r'\*(.*?)\*', r'\1', cleaned)
        cleaned = re.sub(r'_(.*?)_', r'\1', cleaned)
        # Remove header syntax
        cleaned = re.sub(r'^#+\s+', '', cleaned, flags=re.MULTILINE)
        # Remove horizontal rules
        cleaned = re.sub(r'^\s*[-*_]{3,}\s*$', '\n', cleaned, flags=re.MULTILINE)
        # Remove code blocks
        cleaned = re.sub(r'```[^\n]*\n(.*?)\n```', r'\1', cleaned, flags=re.DOTALL)
        # Remove inline code
        cleaned = re.sub(r'`([^`]*)`', r'\1', cleaned)
        # Remove blockquotes
        cleaned = re.sub(r'^>\s+', '', cleaned, flags=re.MULTILINE)
        # Remove link syntax but keep text
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
        # Remove HTML tags
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        
        logger.info("Successfully cleaned Markdown syntax from post content")
        return cleaned.strip()
    except Exception as e:
        logger.error(f"Error cleaning Markdown syntax: {e}")
        # Return original content if there's an error
        return post_content

# Node: Copy to Clipboard (Conditional)
@Nodes.define(output="clipboard_status")
async def copy_to_clipboard(post_content: str, do_copy: bool) -> str:
    """Copy the final LinkedIn post content to clipboard if do_copy is True."""
    if do_copy:
        try:
            pyperclip.copy(post_content)
            logger.info("Copied LinkedIn post content to clipboard")
            return "Content copied to clipboard"
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            raise
    else:
        logger.info("Clipboard copying skipped as per user preference")
        return "Clipboard copying skipped"

# Define the Updated Workflow with Fluent API
def create_file_to_linkedin_workflow() -> Workflow:
    """Create a workflow to convert a file (PDF, text, or Markdown) to a LinkedIn post."""
    wf = Workflow("check_file_type")
    
    # Register all nodes with input mappings for dynamic model passing
    wf.node("check_file_type")
    wf.node("convert_pdf_to_markdown", inputs_mapping={"model": "text_extraction_model"})
    wf.node("read_text_or_markdown")
    wf.node("save_markdown_content")
    wf.node("extract_first_100_lines")
    wf.node("extract_paper_info", inputs_mapping={"model": "cleaning_model"})
    wf.node("extract_title_str")
    wf.node("extract_authors_str")
    wf.node("generate_linkedin_post", inputs_mapping={"model": "writing_model"})
    wf.node("save_draft_post_content")
    wf.node("format_linkedin_post", inputs_mapping={"model": "cleaning_model"})
    wf.node("clean_markdown_syntax")
    wf.node("copy_to_clipboard")
    
    # Reset current node to the start node after registration
    wf.current_node = "check_file_type"
    
    # Define the workflow structure using fluent API
    # Branch based on file type from check_file_type
    (wf.branch([
        ("convert_pdf_to_markdown", lambda ctx: ctx["file_type"] == "pdf"),
        ("read_text_or_markdown", lambda ctx: ctx["file_type"] in ["text", "markdown"])
    ], default="convert_pdf_to_markdown")
    )
    
    # Set up explicit transitions for convergence
    wf.transitions["convert_pdf_to_markdown"] = [("save_markdown_content", None)]
    wf.transitions["read_text_or_markdown"] = [("save_markdown_content", None)]
    
    # Set current node to the convergence point and continue with fluent API
    wf.current_node = "save_markdown_content"
    
    # Define the linear processing sequence using fluent API
    (wf.then("extract_first_100_lines")
     .then("extract_paper_info")
     .then("extract_title_str")
     .then("extract_authors_str")
     .then("generate_linkedin_post")
     .then("save_draft_post_content")
     .then("format_linkedin_post")
     .then("clean_markdown_syntax")
     .then("copy_to_clipboard")
    )
    
    return wf

# Function to Run the Workflow
async def run_workflow(
    file_path: str,
    text_extraction_model: str,
    cleaning_model: str,
    writing_model: str,
    output_dir: str | None = None,
    copy_to_clipboard_flag: bool = True,
    max_character_count: int = 3000
) -> dict:
    """Execute the workflow with the given file path and models."""
    file_path = os.path.expanduser(file_path)
    if output_dir:
        output_dir = os.path.expanduser(output_dir)
        
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise ValueError(f"File not found: {file_path}")

    # Initial context with model keys for dynamic mapping
    initial_context = {
        "file_path": file_path,
        "model": text_extraction_model,  # Kept for compatibility, though redundant
        "text_extraction_model": text_extraction_model,
        "cleaning_model": cleaning_model,
        "writing_model": writing_model,
        "output_dir": output_dir if output_dir else str(Path(file_path).parent),
        "do_copy": copy_to_clipboard_flag,
        "max_character_count": max_character_count
    }

    try:
        workflow = create_file_to_linkedin_workflow()
        engine = workflow.build()
        result = await engine.run(initial_context)
        
        if "post_content" not in result or not result["post_content"]:
            logger.warning("No LinkedIn post content generated.")
            raise ValueError("Workflow completed but no post content was generated.")
        
        logger.info("Workflow completed successfully")
        return result
    except Exception as e:
        logger.error(f"Error during workflow execution: {e}")
        raise

async def display_results(post_content: str, markdown_file_path: str, draft_post_file_path: str, copy_to_clipboard_flag: bool):
    """Async helper function to display results with animation."""
    console.print("\n[bold green]Generated LinkedIn Post:[/]")
    console.print(Panel(Markdown(post_content), border_style="blue"))
    
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
    
    console.print(f"[green]✓ Extracted markdown saved to:[/] {markdown_file_path}")
    console.print(f"[green]✓ Draft LinkedIn post saved to:[/] {draft_post_file_path}")

@app.command()
def analyze(
    file_path: Annotated[str, typer.Argument(help="Path to the file (PDF, .txt, or .md; supports ~ expansion)")],
    text_extraction_model: Annotated[str, typer.Option(help="LLM model for PDF text extraction")] = DEFAULT_TEXT_EXTRACTION_MODEL,
    cleaning_model: Annotated[str, typer.Option(help="LLM model for title/author extraction")] = DEFAULT_CLEANING_MODEL,
    writing_model: Annotated[str, typer.Option(help="LLM model for article writing and formatting")] = DEFAULT_WRITING_MODEL,
    output_dir: Annotated[str | None, typer.Option(help="Directory to save output files (supports ~ expansion)")] = None,
    save: Annotated[bool, typer.Option(help="Save output to a markdown file")] = True,
    copy_to_clipboard_flag: Annotated[bool, typer.Option(help="Copy the final post to clipboard")] = True,
    max_character_count: Annotated[int, typer.Option(help="Maximum character count for the LinkedIn post")] = 3000
):
    """Convert a file (PDF, text, or Markdown) to a LinkedIn post using an LLM workflow."""
    try:
        with console.status(f"Processing [bold blue]{file_path}[/]..."):
            result = asyncio.run(run_workflow(
                file_path,
                text_extraction_model,
                cleaning_model,
                writing_model,
                output_dir,
                copy_to_clipboard_flag,
                max_character_count
            ))
        
        post_content = result["post_content"]
        markdown_file_path = result.get("markdown_file_path", "Not saved")
        draft_post_file_path = result.get("draft_post_file_path", "Not saved")
        
        # Run the async display function
        asyncio.run(display_results(post_content, markdown_file_path, draft_post_file_path, copy_to_clipboard_flag))
        
        if save:
            file_path_expanded = os.path.expanduser(file_path)
            output_path = Path(file_path_expanded).with_suffix(".md")
            with output_path.open("w", encoding="utf-8") as f:
                f.write(post_content)
            console.print(f"[green]✓ Final LinkedIn post saved to:[/] {output_path}")
            logger.info(f"Saved LinkedIn post to: {output_path}")
    
    except Exception as e:
        logger.error(f"Failed to run workflow: {e}")
        console.print(f"[bold red]Error:[/] {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
