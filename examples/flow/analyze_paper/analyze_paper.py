#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru>=0.7.2",              # Logging utility
#     "litellm>=1.0.0",             # LLM integration
#     "pydantic>=2.0.0",            # Data validation and settings
#     "asyncio",                    # Async utilities
#     "jinja2>=3.1.0",              # Templating engine
#     "py-zerox",                   # PDF processing
#     "pdf2image",                  # PDF to image conversion
#     "pillow",                     # Image handling
#     "quantalogic",                # Workflow framework
#     "instructor[litellm]>=0.5.0", # Structured LLM output
#     "typer>=0.9.0",               # Command line interface
#     "rich>=13.0.0"                # Rich text and formatting
# ]
# ///
# System dependencies:
# - poppler (for pdf2image): brew install poppler (macOS) or apt-get install poppler-utils (Linux)

import asyncio
import os
from pathlib import Path
from typing import List, Optional, Union, Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from loguru import logger
from pydantic import BaseModel
from pyzerox import zerox

from quantalogic.flow.flow import Nodes, Workflow

# Initialize Typer app and rich console
app = typer.Typer(help="Convert a PDF to a LinkedIn post using LLMs")
console = Console()

# Default model to use (Gemini Flash 2.0)
DEFAULT_MODEL = "gemini/gemini-2.0-flash"

# Define a Pydantic model for structured output of title and authors
class PaperInfo(BaseModel):
    title: str
    authors: List[str]

# Node 1: Convert PDF to Markdown
@Nodes.define(output="markdown_content")
async def convert_pdf_to_markdown(
    pdf_path: str,
    model: str,
    custom_system_prompt: Optional[str] = None,
    output_dir: Optional[str] = None,
    select_pages: Optional[Union[int, List[int]]] = None
) -> str:
    """Convert a PDF to Markdown using a vision model, preserving original functionality."""
    # Expand tilde in paths
    pdf_path = os.path.expanduser(pdf_path)
    if output_dir:
        output_dir = os.path.expanduser(output_dir)
        
    # Validate the PDF file path
    if not pdf_path:
        logger.error("PDF path is required")
        raise ValueError("PDF path is required")
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise ValueError(f"PDF file not found: {pdf_path}")
    if not pdf_path.lower().endswith(".pdf"):
        logger.error(f"File must be a PDF: {pdf_path}")
        raise ValueError(f"File must be a PDF: {pdf_path}")

    # Set default system prompt if none provided
    if custom_system_prompt is None:
        custom_system_prompt = (
            "Convert the PDF page to a clean, well-formatted Markdown document. "
            "Preserve structure, headings, and any code or mathematical notation. "
            "For images and charts, create a literal description of what is visible. "
            "Return only pure Markdown content, excluding any metadata or non-Markdown elements."
        )

    try:
        logger.info(f"Calling zerox with model: {model}, file: {pdf_path}")
        zerox_result = await zerox(
            file_path=pdf_path,
            model=model,
            system_prompt=custom_system_prompt,
            output_dir=output_dir,
            select_pages=select_pages
        )

        # Handle different possible outputs from zerox
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

# Node 2: Extract First 100 Lines
@Nodes.define(output="first_100_lines")
async def extract_first_100_lines(markdown_content: str) -> str:
    """Extract the first 100 lines from the Markdown content for title and author extraction."""
    try:
        lines = markdown_content.splitlines()
        first_100 = lines[:100]  # Take first 100 lines as per requirement
        result = "\n".join(first_100)
        logger.info(f"Extracted {len(first_100)} lines from Markdown content")
        return result
    except Exception as e:
        logger.error(f"Error extracting first 100 lines: {e}")
        raise

# Node 3: Extract Title and Authors using Structured LLM
@Nodes.structured_llm_node(
    model=DEFAULT_MODEL,  # Use Gemini instead of OpenAI to avoid quota issues
    system_prompt="You are an AI assistant tasked with extracting the title and authors from a research paper's Markdown text.",
    output="paper_info",
    response_model=PaperInfo,
    prompt_template="Extract the title and a list of authors from the following Markdown text. "
                    "The title is typically the first heading or prominent text, and authors are usually listed below it:\n\n{{first_100_lines}}"
)
async def extract_paper_info(first_100_lines: str) -> PaperInfo:
    """Extract title and authors from the first 100 lines using a structured LLM."""
    # The actual extraction is handled by the structured_llm_node decorator
    # This function serves as a placeholder for the node definition
    pass

# Node 4: Generate LinkedIn Post using LLM
@Nodes.llm_node(
    model=DEFAULT_MODEL,  # Use Gemini instead of OpenAI to avoid quota issues
    system_prompt="You are an AI expert who enjoys sharing interesting papers and articles with a professional audience.",
    output="post_content",
    prompt_template="""
## The task to do
As an AI expert that likes to share interesting papers and articles, write the best possible LinkedIn post to introduce a new research paper "{{paper_info.title}}" from {{paper_info.authors | join(', ') }}.

## Message to convey
Start with an intriguing question to capture attention, applying a psychology framework to maximize engagement and encourage sharing.

Structure the post in:

WHY -> WHAT -> HOW

Explain concepts clearly and simply, as if teaching a curious beginner, without citing any specific teaching methods.

## Recommendations
- Use Markdown formatting, keeping the post under 1300 words.
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
async def generate_linkedin_post(paper_info: PaperInfo) -> str:
    """Generate a LinkedIn post in Markdown based on the paper's title and authors."""
    # The actual generation is handled by the llm_node decorator
    # This function serves as a placeholder for the node definition
    pass

# Define the Workflow
def create_pdf_to_linkedin_workflow() -> Workflow:
    """Create a workflow to convert a PDF to a LinkedIn post."""
    workflow = (
        Workflow("convert_pdf_to_markdown")
        .sequence(
            "convert_pdf_to_markdown",      # Step 1: Convert PDF to Markdown
            "extract_first_100_lines",      # Step 2: Extract first 100 lines
            "extract_paper_info",           # Step 3: Extract title and authors
            "generate_linkedin_post"        # Step 4: Generate LinkedIn post
        )
    )
    return workflow

# Function to Run the Workflow
async def run_workflow(pdf_path: str, model: str, output_dir: Optional[str] = None) -> dict:
    """Execute the workflow with the given PDF path and model."""
    # Expand tilde in paths
    pdf_path = os.path.expanduser(pdf_path)
    if output_dir:
        output_dir = os.path.expanduser(output_dir)
        
    # Validate inputs
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise ValueError(f"PDF file not found: {pdf_path}")

    # Initial context for the workflow
    initial_context = {
        "pdf_path": pdf_path,
        "model": model,  # Model for PDF conversion and LLM tasks
        "output_dir": output_dir if output_dir else str(Path(pdf_path).parent)
    }

    try:
        # Build and run the workflow
        workflow = create_pdf_to_linkedin_workflow()
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

@app.command()
def analyze(
    pdf_path: Annotated[str, typer.Argument(help="Path to the PDF file (supports ~ expansion)")],
    model: Annotated[str, typer.Option(help="LLM model to use")] = DEFAULT_MODEL,
    output_dir: Annotated[Optional[str], typer.Option(help="Directory to save output files (supports ~ expansion)")] = None,
    save: Annotated[bool, typer.Option(help="Save output to a markdown file")] = True,
):
    """
    Convert a PDF paper to a LinkedIn post using an LLM workflow.
    
    This tool processes academic papers in PDF format and generates
    engaging LinkedIn content based on the extracted information.
    """
    try:
        with console.status(f"Processing [bold blue]{pdf_path}[/]..."):
            result = asyncio.run(run_workflow(pdf_path, model, output_dir))
        
        post_content = result["post_content"]
        console.print("\n[bold green]Generated LinkedIn Post:[/]")
        console.print(Panel(Markdown(post_content), border_style="blue"))
        
        if save:
            # Expand tilde in output path
            pdf_path_expanded = os.path.expanduser(pdf_path)
            output_path = Path(pdf_path_expanded).with_suffix(".md")
            with output_path.open("w", encoding="utf-8") as f:
                f.write(post_content)
            console.print(f"[green]Saved LinkedIn post to:[/] {output_path}")
            logger.info(f"Saved LinkedIn post to: {output_path}")
    
    except Exception as e:
        logger.error(f"Failed to run workflow: {e}")
        console.print(f"[bold red]Error:[/] {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()