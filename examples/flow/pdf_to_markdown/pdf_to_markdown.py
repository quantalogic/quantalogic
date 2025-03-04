#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "asyncio",
#     "jinja2",  
#     "py-zerox @ git+https://github.com/getomni-ai/zerox.git",  # Install directly from GitHub
#     "pdf2image",  # Required for PDF to image conversion
#     "pillow"  # Image processing library
# ]
# ///

# System dependencies:
# - poppler (for pdf2image): brew install poppler (macOS) or apt-get install poppler-utils (Linux)

import asyncio
import os
from typing import Optional, Union

from loguru import logger

# Note: The PyPI package 'py-zerox' has issues with imports.
# The GitHub version is recommended: https://github.com/getomni-ai/zerox/issues/47
from pyzerox import zerox

### Model Setup (Use only Vision Models) Refer: https://docs.litellm.ai/docs/providers ###

## placeholder for additional model kwargs which might be required for some models
kwargs = {}

## system prompt to use for the vision model
custom_system_prompt = None

# to override
# custom_system_prompt = "For the below PDF page, do something..something..." ## example


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


async def convert_pdf_to_markdown(
    pdf_path: str, 
    model: str = "gpt-4o-mini", 
    custom_system_prompt: Optional[str] = None, 
    output_dir: Optional[str] = "./output_test",
    select_pages: Optional[Union[int, list[int]]] = None,
    **kwargs
) -> str:
    """
    Convert a PDF to Markdown using Vision Language Models.

    Args:
        pdf_path (str): Path to the PDF file
        model (str): Vision model to use for conversion
        custom_system_prompt (str, optional): Custom system prompt for the model
        output_dir (str, optional): Directory to save markdown files
        select_pages (int or list[int], optional): Specific pages to convert
        **kwargs: Additional arguments for the zerox function

    Returns:
        str: Pure Markdown content of the PDF
    """
    if not validate_pdf_path(pdf_path):
        raise ValueError("Invalid PDF path")

    # Remove model from kwargs if present to avoid duplicate argument
    kwargs.pop('model', None)
    kwargs.pop('file_path', None)
    kwargs.pop('output_dir', None)

    try:
        # Explicitly set a default system prompt if none is provided
        if custom_system_prompt is None:
            custom_system_prompt = (
                "Convert the PDF page to a clean, well-formatted Markdown document. "
                "Preserve structure, headings, and any code or mathematical notation. "
                "Return only pure Markdown content, excluding any metadata or non-Markdown elements."
            )

        # Perform PDF to markdown conversion
        logger.info(f"Calling zerox with model: {model}, file: {pdf_path}")
        zerox_result = await zerox(
            file_path=pdf_path, 
            model=model, 
            system_prompt=custom_system_prompt,
            output_dir=output_dir,
            select_pages=select_pages,
            **kwargs
        )

        # Log the raw result for debugging
        logger.debug(f"zerox_result type: {type(zerox_result)}, content: {zerox_result}")

        # Extract Markdown content from ZeroxOutput
        markdown_content = ""
        if hasattr(zerox_result, 'pages') and zerox_result.pages:
            # Combine content from all pages
            logger.info(f"Found {len(zerox_result.pages)} pages in ZeroxOutput")
            markdown_content = "\n\n".join(
                page.content for page in zerox_result.pages 
                if hasattr(page, 'content') and page.content
            )
        elif isinstance(zerox_result, str):
            logger.info("zerox_result is a string")
            markdown_content = zerox_result
        elif hasattr(zerox_result, 'markdown'):
            logger.info("zerox_result has markdown attribute")
            markdown_content = zerox_result.markdown
        elif hasattr(zerox_result, 'text'):
            logger.info("zerox_result has text attribute")
            markdown_content = zerox_result.text
        else:
            # Fallback: convert to string and log a warning
            markdown_content = str(zerox_result)
            logger.warning("Unexpected zerox_result type; converted to string as fallback.")

        # Validate the extracted content
        if not markdown_content.strip():
            logger.warning("Generated Markdown content is empty.")
            return ""
        
        logger.info(f"Extracted Markdown content length: {len(markdown_content)} characters")
        return markdown_content

    except Exception as e:
        logger.error(f"Error converting PDF to Markdown: {e}")
        raise


async def main():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Example PDF path relative to this script's location
    pdf_path = os.path.join(script_dir, "code_symb_planer_2503.01700v1.pdf")
    
    # Define output directory relative to this script's location
    output_dir = os.path.join(script_dir, "output")

    # Example model configurations
    model_configs = {
        "openai": {
            "model": "gpt-4o-mini", 
            "api_key": os.getenv("OPENAI_API_KEY", "")
        },
        "azure": {
            "model": "azure/gpt-4o-mini",
            "api_key": os.getenv("AZURE_API_KEY", ""),
            "api_base": os.getenv("AZURE_API_BASE", ""),
            "api_version": os.getenv("AZURE_API_VERSION", ""),
        },
        "vertex_ai": {
            "model": "vertex_ai/gemini-1.5-flash-001",
            "vertex_credentials": os.getenv("VERTEX_CREDENTIALS", ""),
        },
        "gemini": {
            "model": "gemini/gemini-2.0-flash", 
            "api_key": os.getenv("GEMINI_API_KEY", "")
        },
    }

    # Select the model configuration you want to use
    selected_config = model_configs["gemini"]
    
    try:
        markdown_result = await convert_pdf_to_markdown(
            pdf_path, 
            model=selected_config["model"], 
            custom_system_prompt=(
                "Convert the entire PDF to a clean, well-structured Markdown document. "
                "Preserve the original formatting, headings, and any code blocks or mathematical equations. "
                "Return only pure Markdown content suitable for a standalone file, excluding any metadata."
            ),
            select_pages=None,  # Convert all pages
            output_dir=output_dir,
            **{k: v for k, v in selected_config.items() if k != 'model'}
        )

        # Validate markdown result
        if not markdown_result:
            logger.warning("No markdown content was generated.")
            return

        # Save the markdown content to a file
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "output.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_result)

        logger.success(f"PDF converted to Markdown: {output_path}")
        logger.info(f"Generated markdown length: {len(markdown_result)} characters")

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        # Optional: log the full traceback
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())