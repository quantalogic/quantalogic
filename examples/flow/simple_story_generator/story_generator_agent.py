#!/usr/bin/env python
# A simple workflow example for story generation

from quantalogic.flow import Nodes, Workflow

# Global variables
MODEL = "gemini/gemini-2.0-flash"
DEFAULT_LLM_PARAMS = {
    "model": MODEL,
    "temperature": 0.7,
    "max_tokens": 1000,
}

@Nodes.llm_node(system_prompt="You are a creative writer skilled at generating stories.", 
                prompt_template="Create a story outline for a {genre} story with {num_chapters} chapters.", 
                output="outline", **DEFAULT_LLM_PARAMS)
def generate_outline(genre, num_chapters):
    """Generate a story outline based on genre and number of chapters."""
    return {}

@Nodes.llm_node(system_prompt="You are a creative writer.", 
                prompt_template="Write chapter {chapter_num} for this story outline: {outline}. Style: {style}.", 
                output="chapter", **DEFAULT_LLM_PARAMS)
def generate_chapter(outline, chapter_num, style):
    """Generate a single chapter based on the outline."""
    return {}

@Nodes.define(output="updated_context")
async def update_progress(**context):
    """Update the progress of chapter generation.
    
    Takes the entire context dictionary and handles missing keys gracefully.
    """
    # Get the values with defaults if not present
    chapters = context.get('chapters', [])
    completed_chapters = context.get('completed_chapters', 0)
    chapter = context.get('chapter', {})
    
    # Create a new list to avoid modifying the original
    updated_chapters = chapters.copy()
    updated_chapters.append(chapter)
    
    # Create updated context with all original values preserved
    updated_context = {
        **context,  # Keep all other context values
        "chapters": updated_chapters,
        "completed_chapters": completed_chapters + 1
    }
    
    # Return the updated context
    return updated_context

@Nodes.define(output="continue_generating")
async def check_if_complete(completed_chapters=0, num_chapters=0, **kwargs):
    """Check if all chapters have been generated.
    
    Args:
        completed_chapters: Number of chapters completed so far
        num_chapters: Total number of chapters to generate
        kwargs: Additional context parameters
        
    Returns:
        bool: True if we should continue generating chapters, False otherwise
    """
    # Check if we should continue
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
    """Observer function to log workflow events.
    
    Args:
        event_type: The type of event (workflow_started, node_started, etc.)
        data: The event data (optional)
    """
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
