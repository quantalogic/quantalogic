#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "anyio",
#     "quantalogic_flow>=0.6.5",
#     "jinja2"  # Added for Jinja2 templating support
# ]
# ///
from typing import List

import anyio
from loguru import logger

from quantalogic_flow import Nodes, Workflow

MODEL = "gemini/gemini-2.0-flash"
DEFAULT_LLM_PARAMS = {
    "model": MODEL,
    "temperature": 0.7,
    "max_tokens": 2000,
    "top_p": 1.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
}


@Nodes.validate_node(output="validation_result")
async def validate_input(genre: str, num_chapters: int) -> str:
    """Validate input parameters."""
    if not (1 <= num_chapters <= 20 and genre.lower() in ["science fiction", "fantasy", "mystery", "romance"]):
        raise ValueError(
            "Invalid input: num_chapters must be 1-20, genre must be one of science fiction, fantasy, mystery, romance"
        )
    return "Input validated"


@Nodes.llm_node(
    **DEFAULT_LLM_PARAMS,
    system_prompt="You are a creative writer specializing in story titles.",
    prompt_template="Generate a creative title for a {{ genre }} story. Output only the title.",
    output="title",
)
async def generate_title(genre: str) -> str:
    """Generate a title based on the genre (handled by llm_node)."""
    pass  # Logic handled by llm_node decorator


@Nodes.llm_node(
    **DEFAULT_LLM_PARAMS,
    system_prompt="You are an expert in story structuring and outlining.",
    prompt_template="Create a detailed outline for a {{ genre }} story titled '{{ title }}' with {{ num_chapters }} chapters. Only the outline in markdown, no comments.",
    output="outline",
)
async def generate_outline(genre: str, title: str, num_chapters: int) -> str:
    """Generate a chapter outline for the story (handled by llm_node)."""
    pass  # Logic handled by llm_node decorator


@Nodes.llm_node(
    **DEFAULT_LLM_PARAMS,
    system_prompt="You are a skilled storyteller with a knack for vivid descriptions.",
    prompt_template="Write chapter {{ completed_chapters + 1 }} of {{ num_chapters }} for the story '{{ title }}'. Outline: {{ outline }}. Style: {{ style }}. Output only the chapter content, markdown format",
    output="chapter_content",
)
async def generate_chapter(
    title: str, outline: str, completed_chapters: int, num_chapters: int, style: str = "descriptive"
) -> str:
    """Generate content for a specific chapter (handled by llm_node with Jinja2 templating)."""
    pass  # Logic handled by llm_node decorator


@Nodes.define(output="completed_chapters")
async def update_chapter_progress(chapters: List[str], chapter_content: str, completed_chapters: int) -> int:
    """Update the chapter list and completion count."""
    chapters.append(chapter_content)
    return completed_chapters + 1


@Nodes.define(output="manuscript")
async def compile_book(title: str, outline: str, chapters: List[str]) -> str:
    """Compile the full manuscript from title, outline, and chapters."""
    return f"Title: {title}\n\nOutline:\n{outline}\n\n" + "\n\n".join(
        f"Chapter {i}:\n{chap}" for i, chap in enumerate(chapters, 1)
    )


@Nodes.llm_node(
    **DEFAULT_LLM_PARAMS,
    system_prompt="You are a meticulous editor reviewing manuscripts for quality.",
    prompt_template="Review this manuscript for coherence, grammar, and quality:\n\n{{ manuscript }}",
    output="quality_check_result",
)
async def quality_check(manuscript: str) -> str:
    """Perform a quality check on the compiled manuscript (handled by llm_node)."""
    pass  # Logic handled by llm_node decorator


@Nodes.define()
async def end(quality_check_result: str) -> None:
    """Log the end of the workflow."""
    logger.info(f"Story generation completed. Quality check: {quality_check_result}")


# Define the workflow using simplified syntax with automatic node registration
workflow = (
    Workflow("validate_input")
    .then("generate_title")
    .then("generate_outline")
    .then("generate_chapter")
    .then("update_chapter_progress")
    .then("generate_chapter", condition=lambda ctx: ctx["completed_chapters"] < ctx["num_chapters"])
    .then("compile_book", condition=lambda ctx: ctx["completed_chapters"] >= ctx["num_chapters"])
    .then("quality_check")
    .then("end")
)


async def main():
    """Main function to run the story generation workflow."""
    initial_context = {
        "genre": "science fiction",
        "num_chapters": 3,
        "chapters": [],
        "completed_chapters": 0,
        "style": "descriptive",
    }
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")


if __name__ == "__main__":
    anyio.run(main)
