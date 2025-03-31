

import asyncio
from collections.abc import Callable
import datetime
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

import typer
from loguru import logger
from pyzerox import zerox

# Import the flow API (assumes quantalogic/flow/flow.py is in your project structure)
from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType
from ..service import event_observer


def validate_pdf_path(pdf_path: str) -> bool:
    """Validate the PDF file path."""
    if not pdf_path:
        logger.error("PDF path is required")
        return False
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        return False
    if not pdf_path.lower().endswith(".pdf"):
        logger.error(f"File must be a PDF: {pdf_path}")
        return False
    return True

# Node to convert PDF to Markdown
@Nodes.define(output="markdown_content")
async def convert_node(
    pdf_path: str,
    model: str,
    custom_system_prompt: Optional[str] = None,
    output_dir: Optional[str] = None,
    select_pages: Optional[Union[int, list[int]]] = None
) -> str:
    """Convert a PDF to Markdown using a vision model."""
    if not validate_pdf_path(pdf_path):
        raise ValueError("Invalid PDF path")

    try:
        if custom_system_prompt is None:
            custom_system_prompt = (
                "Convert the PDF page to a clean, well-formatted Markdown document. "
                "Preserve structure, headings, and any code or mathematical notation. " 
                "Separate each page with a newline."
                "Include page numbers in the output."
                "Extract only the Arabic language part."
                "Return only pure Markdown content, excluding any metadata or non-Markdown elements."
            )

        logger.info(f"Calling zerox with model: {model}, file: {pdf_path}")
        zerox_result = await zerox(
            file_path=pdf_path,
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

# Node to save Markdown content to a file
@Nodes.define(output="output_path")
async def save_node(markdown_content: str, output_md: str) -> str:
    """Save the Markdown content to the specified file path, overwriting if it exists."""
    try:
        output_path = Path(output_md)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            f.write(markdown_content)
        logger.info(f"Saved Markdown to: {output_path} (overwritten if existed)")
        return str(output_path)
    except Exception as e:
        logger.error(f"Error saving Markdown to {output_md}: {e}")
        raise

# Define the workflow
def create_pdf_to_md_workflow():
    workflow = (
        Workflow("convert_node")
        .sequence("convert_node", "save_node")
    )
    return workflow

async def convert(
    input_pdf: str = typer.Argument(..., help="Path to the input PDF file"),
    output_md: Optional[str] = typer.Argument(None, help="Path to save the output Markdown file (defaults to input_pdf_name.md)"),
    model: str = typer.Option("gemini/gemini-2.0-flash", help="LiteLLM-compatible model name (e.g., 'openai/gpt-4o-mini', 'gemini/gemini-2.0-flash')"),
    system_prompt: Optional[str] = typer.Option(None, help="Custom system prompt for the vision model"),
    _handle_event: Optional[Callable[[str, dict], None]] = None,
    task_id: Optional[str] = None
):
    """
    Convert a PDF file to Markdown using a two-step workflow: convert and save.

    The model name should be in LiteLLM format, e.g., 'openai/gpt-4o-mini', 'gemini/gemini-2.0-flash'.
    If output_md is not specified, it defaults to the input PDF name with a .md extension.
    Existing files at output_md will be overwritten.

    Ensure the appropriate environment variables are set for the chosen model:
    - 'openai/gpt-4o-mini': Set OPENAI_API_KEY
    - 'gemini/gemini-2.0-flash': Set GEMINI_API_KEY
    - 'azure/gpt-4o-mini': Set AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION
    - 'vertex_ai/gemini-1.5-flash-001': Set VERTEX_CREDENTIALS

    Examples:
        uv run pdf_to_md_flow.py convert input.pdf  # Saves to input.md
        uv run pdf_to_md_flow.py convert input.pdf custom_output.md --model openai/gpt-4o-mini
    """
    if not validate_pdf_path(input_pdf):
        typer.echo(f"Error: Invalid PDF path: {input_pdf}", err=True)
        raise typer.Exit(code=1)

    # Default output_md to input_pdf name with .md extension if not provided
    if output_md is None:
        output_md = str(Path(input_pdf).with_suffix(".md"))

    # Create initial context for the workflow
    initial_context = {
        "pdf_path": input_pdf,
        "model": model,
        "custom_system_prompt": system_prompt,
        "output_md": output_md
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        initial_context["output_dir"] = temp_dir
        try:
            # Build and run the workflow
            workflow = create_pdf_to_md_workflow()
            engine = workflow.build() 

            # Add the event observer if _handle_event is provided
            if _handle_event:
                # Create a lambda to bind task_id to the observer
                bound_observer = lambda event: asyncio.create_task(
                    event_observer(event, task_id=task_id, _handle_event=_handle_event)
                )
                engine.add_observer(bound_observer)

            result = await engine.run(initial_context)

            output_path = result.get("output_path")
            if not output_path:
                logger.warning("Warning: No output path generated.")
                raise Exception("No output path generated.")

            logger.info(f"PDF converted to Markdown: {output_path}")
            return result
        except Exception as e:
            logger.error(f"Error during workflow execution: {e}")
            raise

