

#!/usr/bin/env python
# A simple workflow example for story generation with external Jinja2 template

from pathlib import Path

from quantalogic.flow import Nodes, Workflow

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
                prompt_template="Write chapter {chapter_num} for this story outline: {outline}. Style: {style}.",
                output="chapter", **DEFAULT_LLM_PARAMS)
def generate_chapter(outline, chapter_num, style):
    """Generate a single chapter based on the outline."""
    return {}

@Nodes.define(output="updated_context")
async def update_progress(**context):
    """Update the progress of chapter generation."""
    chapters = context.get('chapters', [])
    completed_chapters = context.get('completed_chapters', 0)
    chapter = context.get('chapter', {})
    updated_chapters = chapters.copy()
    updated_chapters.append(chapter)
    updated_context = {
        **context,
        "chapters": updated_chapters,
        "completed_chapters": completed_chapters + 1
    }
    return updated_context

@Nodes.define(output="continue_generating")
async def check_if_complete(completed_chapters=0, num_chapters=0, **kwargs):
    """Check if all chapters have been generated."""
    return completed_chapters < num_chapters

# Define the workflow
workflow = (
    Workflow("generate_outline")
    .then("generate_chapter")
    .then("update_progress")
    .then("check_if_complete")
    .then("generate_chapter", condition=lambda ctx: ctx.get("continue_generating", False))
    .then("update_progress")
    .then("check_if_complete")
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
            print("Completed chapters: {result.get('completed_chapters', 0)}")
            return result
        except Exception as e:
            print(f"\nWorkflow failed with error: {e}")
            raise

    anyio.run(main)

  