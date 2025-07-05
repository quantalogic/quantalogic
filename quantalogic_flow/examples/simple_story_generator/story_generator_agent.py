#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "anyio",
#     "quantalogic-flow>=0.6.6",
#     "jinja2"
# ]
# ///

from typing import List

import anyio

from quantalogic_flow.flow import Nodes, Workflow

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
async def validate_input(genre: str, num_chapters: int):
    """Validate input parameters."""
    if not (1 <= num_chapters <= 20 and genre.lower() in ["science fiction", "fantasy", "mystery", "romance"]):
        raise ValueError("Invalid input: num_chapters must be 1-20, genre must be one of science fiction, fantasy, mystery, romance")
    return "Input validated"

@Nodes.llm_node(
    system_prompt="You are a creative writer specializing in story titles.",
    prompt_template="Generate a creative title for a {{ genre }} story. Output only the title.",
    output="title",
    **DEFAULT_LLM_PARAMS
)
async def generate_title(genre: str):
    """Generate a title based on the genre."""
    pass

@Nodes.llm_node(
    system_prompt="You are an expert in story structuring and outlining.",
    prompt_template="Create a detailed outline for a {{ genre }} story titled '{{ title }}' with {{ num_chapters }} chapters. Only the outline in markdown, no comments.",
    output="outline",
    **DEFAULT_LLM_PARAMS
)
async def generate_outline(genre: str, title: str, num_chapters: int):
    """Generate a chapter outline for the story."""
    pass

@Nodes.llm_node(
    system_prompt="You are a skilled storyteller with a knack for vivid descriptions.",
    prompt_template="Write chapter {{ completed_chapters + 1 }} of {{ num_chapters }} for the story '{{ title }}'. Outline: {{ outline }}. Style: {{ style }}. Output only the chapter content, markdown format",
    output="chapter",
    **DEFAULT_LLM_PARAMS
)
async def generate_chapter(title: str, outline: str, completed_chapters: int, num_chapters: int, style: str):
    """Generate content for a specific chapter."""
    pass

@Nodes.define(output=None)
async def update_progress(chapters: List[str], chapter: str, completed_chapters: int):
    """Update the chapter list and completion count."""
    updated_chapters = chapters + [chapter]
    return {"chapters": updated_chapters, "completed_chapters": completed_chapters + 1}

@Nodes.define(output="manuscript")
async def compile_book(title: str, outline: str, chapters: List[str]):
    """Compile the full manuscript from title, outline, and chapters."""
    return f"Title: {title}\n\nOutline:\n{outline}\n\n" + "\n\n".join(
        f"Chapter {i}:\n{chap}" for i, chap in enumerate(chapters, 1)
    )

@Nodes.llm_node(
    system_prompt="You are a meticulous editor reviewing manuscripts for quality.",
    prompt_template="Review this manuscript for coherence, grammar, and quality:\n\n{{ manuscript }}",
    output="quality_check_result",
    **DEFAULT_LLM_PARAMS
)
async def quality_check(manuscript: str):
    """Perform a quality check on the compiled manuscript."""
    pass

# Define the workflow
def create_story_workflow():
    """Create and return the story generation workflow for testing purposes."""
    workflow = (
        Workflow("validate_input")
        .then("generate_title")
        .then("generate_outline")
        .start_loop()
        .node("generate_chapter")
        .node("update_progress")
        .end_loop(
            condition=lambda ctx: ctx["completed_chapters"] >= ctx["num_chapters"],
            next_node="compile_book"
        )
        .then("quality_check")
    )
    
    def story_observer(event_type, data=None):
        """Observer function to log workflow events."""
        print(f"Event: {event_type} - Data: {data}")
    
    # Add an observer to the workflow
    workflow.add_observer(story_observer)
    return workflow

# Default workflow for direct execution
workflow = create_story_workflow()

if __name__ == "__main__":
    async def main():
        initial_context = {
            "genre": "science fiction",
            "num_chapters": 3,
            "chapters": [],
            "completed_chapters": 0,
            "style": "descriptive"
        }
        try:
            engine = workflow.build()
            result = await engine.run(initial_context)
            print("\nWorkflow completed successfully!")
            print(f"Quality check result: {result.get('quality_check_result')}")
            return result
        except Exception as e:
            print(f"\nWorkflow failed with error: {e}")
            raise
    
    anyio.run(main)