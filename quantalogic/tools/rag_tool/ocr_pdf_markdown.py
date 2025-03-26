
import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional, Union, List

import typer
from loguru import logger
from pyzerox import zerox

# Import the flow API (assumes quantalogic/flow/flow.py is in your project structure)
from quantalogic.flow.flow import Nodes, Workflow

class PDFToMarkdownConverter:
    """A class to handle PDF to Markdown conversion using vision models."""
    
    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        custom_system_prompt: Optional[str] = None,
        output_dir: Optional[str] = None
    ):
        self.model = model
        self.custom_system_prompt = custom_system_prompt or (
            "Convert the PDF page to a clean, well-formatted Markdown document. "
            "Preserve structure, headings, and any code or mathematical notation. "
            "For the images and chart, create a literal description what is visible. "
            "Return only pure Markdown content, excluding any metadata or non-Markdown elements."
        )
        self.output_dir = output_dir

    @staticmethod
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

    async def convert_pdf(
        self,
        pdf_path: str,
        select_pages: Optional[Union[int, List[int]]] = None
    ) -> str:
        """Convert a PDF to Markdown using a vision model."""
        if not self.validate_pdf_path(pdf_path):
            raise ValueError("Invalid PDF path")

        try:
            logger.info(f"Calling zerox with model: {self.model}, file: {pdf_path}")
            zerox_result = await zerox(
                file_path=pdf_path,
                model=self.model,
                system_prompt=self.custom_system_prompt,
                output_dir=self.output_dir,
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

    async def convert_and_save(
        self,
        pdf_path: str,
        output_md: Optional[str] = None,
        select_pages: Optional[Union[int, List[int]]] = None
    ) -> str:
        """Convert PDF to Markdown and optionally save to file."""
        markdown_content = await self.convert_pdf(pdf_path, select_pages)
        
        if output_md:
            output_path = Path(output_md)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                f.write(markdown_content)
            logger.info(f"Saved Markdown to: {output_path}")
            return str(output_path)
        
        return markdown_content

# Typer CLI app
app = typer.Typer()

@app.command()
def convert(
    input_pdf: str = typer.Argument(..., help="Path to the input PDF file"),
    output_md: Optional[str] = typer.Argument(None, help="Path to save the output Markdown file (defaults to input_pdf_name.md)"),
    model: str = typer.Option("gemini/gemini-2.0-flash", help="LiteLLM-compatible model name"),
    system_prompt: Optional[str] = typer.Option(None, help="Custom system prompt for the vision model")
):
    """Convert a PDF file to Markdown using vision models."""
    if not PDFToMarkdownConverter.validate_pdf_path(input_pdf):
        typer.echo(f"Error: Invalid PDF path: {input_pdf}", err=True)
        raise typer.Exit(code=1)

    if output_md is None:
        output_md = str(Path(input_pdf).with_suffix(".md"))

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            converter = PDFToMarkdownConverter(
                model=model,
                custom_system_prompt=system_prompt,
                output_dir=temp_dir
            )
            output_path = asyncio.run(converter.convert_and_save(input_pdf, output_md))
            typer.echo(f"PDF converted to Markdown: {output_path}")
        except Exception as e:
            typer.echo(f"Error during conversion: {e}", err=True)
            raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
