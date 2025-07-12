#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "anyio",
#     "quantalogic-flow>=0.6.8",
#     "jinja2"
# ]
# ///

# A simple workflow example for story generation with external Jinja2 template

from pathlib import Path
from typing import List

from quantalogic_flow.flow import Nodes, Workflow

# Global variables
MODEL = "gemini/gemini-2.0-flash"
DEFAULT_LLM_PARAMS = {
    "model": MODEL,
    "temperature": 0.7,
    "max_tokens": 1000,
}

# Define the path to the external template file
TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_FILE = TEMPLATE_DIR / "story_outline.j2"

@Nodes.llm_node(system_prompt="You are a creative writer skilled at generating stories.",
                prompt_file=str(TEMPLATE_FILE),  # Use prompt_file to load the external template
                output="outline", **DEFAULT_LLM_PARAMS)
def generate_outline(genre, num_chapters):
    """Generate a story outline based on genre and number of chapters using an external Jinja2 template."""
    return {}

@Nodes.llm_node(system_prompt="You are a creative writer.",
                prompt_template="Write chapter {{ completed_chapters + 1 }} for this story outline: {{ outline }}. Style: {{ style }}.",
                output="chapter", **DEFAULT_LLM_PARAMS)
def generate_chapter(outline, completed_chapters, style):
    """Generate a single chapter based on the outline."""
    return {}

@Nodes.define(output=None)
async def update_progress(chapters: List[str], chapter: str, completed_chapters: int):
    """Update the progress of chapter generation."""
    updated_chapters = chapters + [chapter]
    return {"chapters": updated_chapters, "completed_chapters": completed_chapters + 1}

@Nodes.define(output="final_result")
async def workflow_complete(chapters: List[str]):
    """Mark the workflow as complete and return the final chapters."""
    return {"final_chapters": chapters}

# Define the workflow
workflow = (
    Workflow("generate_outline")
    .start_loop()
    .node("generate_chapter")
    .node("update_progress")
    .end_loop(
        condition=lambda ctx: ctx["completed_chapters"] >= ctx["num_chapters"],
        next_node="workflow_complete"
    )
)

def story_observer(event_type, data=None):
    """Observer function to log workflow events."""
    print(f"Event: {event_type} - Data: {data}")

# Add an observer to the workflow
workflow.add_observer(story_observer)

if __name__ == "__main__":
    import anyio

    async def main():
        # Set up initial context
        initial_context = {
            "genre": "science fiction",
            "num_chapters": 3,
            "chapters": [],
            "completed_chapters": 0,
            "style": "descriptive"
        }

        try:
            # Build the workflow engine
            engine = workflow.build()

            # Run the workflow
            result = await engine.run(initial_context)

            print("\nWorkflow completed successfully!")
            print(f"Completed chapters: {result.get('completed_chapters', 0)}")
            return result
        except Exception as e:
            print(f"\nWorkflow failed with error: {e}")
            raise

    anyio.run(main)