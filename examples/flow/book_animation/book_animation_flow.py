#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru>=0.7.2",
#     "litellm>=1.0.0",
#     "pydantic>=2.0.0",
#     "asyncio",
#     "jinja2>=3.1.0",
#     "quantalogic",
#     "instructor>=0.5.2",
#     "typer>=0.9.0",
#     "rich>=13.0.0",
#     "markdown>=3.5.0"
# ]
# ///

import asyncio
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from pathlib import Path

from loguru import logger
from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType
from quantalogic.tools.image_generation.stable_diffusion import StableDiffusionTool
from jinja2 import Environment, FileSystemLoader

# Define Pydantic models for structured output
class ChapterImage(BaseModel):
    """Structure for a chapter illustration."""
    prompt: str = Field(description="Image generation prompt")
    description: str = Field(description="Description of the image")
    path: Optional[str] = Field(description="Path to the generated image")

class Chapter(BaseModel):
    """Structure for a book chapter."""
    title: str = Field(description="Chapter title")
    content: str = Field(description="Chapter content in markdown")
    summary: str = Field(description="Brief chapter summary")
    keywords: List[str] = Field(description="Key themes and topics")
    estimated_read_time: int = Field(description="Estimated reading time in minutes")
    illustrations: List[ChapterImage] = Field(description="Chapter illustrations", default_factory=list)

class BookStructure(BaseModel):
    """Complete book structure with chapters."""
    title: str = Field(description="Book title")
    author: str = Field(description="Book author")
    chapters: List[Chapter] = Field(description="List of chapters")
    theme: str = Field(description="Overall book theme")
    target_audience: str = Field(description="Target audience description")
    genre: str = Field(description="Book genre")

class ChapterGeneration(BaseModel):
    """Generated chapter content."""
    title: str = Field(description="Chapter title")
    content: str = Field(description="Chapter content")
    summary: str = Field(description="Chapter summary")
    keywords: List[str] = Field(description="Key themes")
    image_suggestions: List[str] = Field(description="Suggested image descriptions")

class AnimationStyle(BaseModel):
    """Animation and styling specifications."""
    color_scheme: Dict[str, str] = Field(description="Color palette for the book")
    typography: Dict[str, str] = Field(description="Font specifications")
    transitions: Dict[str, str] = Field(description="Page transition effects")
    animations: Dict[str, Dict] = Field(description="Custom animations for elements")
    layout: str = Field(description="Layout style (e.g., 'classic', 'modern', 'minimal')")

class WebAssets(BaseModel):
    """Generated web assets for the book."""
    html_content: str = Field(description="Main HTML content")
    css_styles: str = Field(description="Custom CSS styles")
    js_animations: str = Field(description="JavaScript animation code")
    tailwind_classes: Dict[str, str] = Field(description="Tailwind CSS class mappings")

# Node: Generate Book Structure
@Nodes.structured_llm_node(
    system_prompt="""You are an expert book writer and content architect.
    Generate engaging book chapters based on the given theme and genre.""",
    output="book_outline",
    response_model=BookStructure,
    prompt_template="""
Create a book structure with the following details:

Theme: {{theme}}
Genre: {{genre}}
Target Audience: {{audience}}

Generate:
1. An engaging book title
2. Author name (if not provided)
3. 3-5 chapters that tell a compelling story
4. Overall theme and atmosphere

Ensure the structure is cohesive and engaging for the target audience.
"""
)
async def generate_book_structure(
    theme: str,
    genre: str,
    audience: str,
    author: Optional[str] = None,
    model: str = "gemini/gemini-2.0-flash"
) -> BookStructure:
    """Generate the initial book structure."""
    logger.debug(f"generate_book_structure called with model: {model}")
    pass

# Node: Generate Chapter Content
@Nodes.structured_llm_node(
    system_prompt="""You are an expert writer specializing in engaging content creation.
    Generate detailed chapter content with appropriate imagery suggestions.""",
    output="chapter_content",
    response_model=ChapterGeneration,
    prompt_template="""
Create detailed content for the following chapter:

Book Context:
Title: {{book.title}}
Theme: {{book.theme}}
Genre: {{book.genre}}

Chapter Details:
Title: {{chapter.title}}

Generate:
1. Engaging chapter content (500-1000 words)
2. Brief chapter summary
3. 5-7 relevant keywords
4. 1-3 suggestions for illustrative images that would enhance the chapter

Ensure content matches the book's theme and genre while being appropriate for the target audience.
"""
)
async def generate_chapter_content(
    book: BookStructure,
    chapter: Chapter,
    model: str = "gemini/gemini-2.0-flash"
) -> ChapterGeneration:
    """Generate detailed content for a chapter."""
    logger.debug(f"generate_chapter_content called with model: {model}")
    pass

# Node: Generate Chapter Images
@Nodes.define(output="chapter_with_images")
async def generate_chapter_images(
    chapter_content: ChapterGeneration,
    book: BookStructure
) -> Chapter:
    """Generate images for a chapter using Stable Diffusion."""
    try:
        sd_tool = StableDiffusionTool()
        illustrations = []
        
        # Generate 1-3 images based on suggestions
        for i, suggestion in enumerate(chapter_content.image_suggestions[:3]):
            prompt = f"Illustration for book '{book.title}', chapter '{chapter_content.title}': {suggestion}"
            
            try:
                image_path = await sd_tool.async_execute(
                    prompt=prompt,
                    negative_prompt="text, watermark, signature, blurry, low quality",
                    style="book_illustration",
                    size="1024x1024",
                    cfg_scale=7.5,
                    steps=30
                )
                
                illustrations.append(ChapterImage(
                    prompt=prompt,
                    description=suggestion,
                    path=image_path
                ))
            except Exception as e:
                logger.error(f"Error generating image {i+1} for chapter: {e}")
                continue
        
        return Chapter(
            title=chapter_content.title,
            content=chapter_content.content,
            summary=chapter_content.summary,
            keywords=chapter_content.keywords,
            estimated_read_time=len(chapter_content.content.split()) // 200,  # Rough estimate
            illustrations=illustrations
        )
    except Exception as e:
        logger.error(f"Error in generate_chapter_images: {e}")
        raise

# Node: Generate Animation Style
@Nodes.structured_llm_node(
    system_prompt="""You are a web design expert specializing in animated books.
    Create engaging and appropriate animation styles for digital books.""",
    output="animation_style",
    response_model=AnimationStyle,
    prompt_template="""
Design an animation and styling system for the following book:

Book Details:
Title: {{book_structure.title}}
Theme: {{book_structure.theme}}
Audience: {{book_structure.target_audience}}

Create:
1. A cohesive color scheme
2. Typography specifications
3. Page transition effects
4. Element animations
5. Overall layout style

Consider:
- Reading comfort
- Visual appeal
- Performance optimization
- Accessibility requirements
"""
)
async def generate_animation_style(
    book_structure: BookStructure,
    model: str = "gemini/gemini-2.0-flash"
) -> AnimationStyle:
    """Generate animation and styling specifications."""
    logger.debug(f"generate_animation_style called with model: {model}")
    pass

# Node: Generate Web Assets
@Nodes.define(output="web_assets")
async def generate_web_assets(
    book_structure: BookStructure,
    animation_style: AnimationStyle
) -> WebAssets:
    """Generate web assets using Tailwind CSS and custom animations."""
    try:
        # Initialize Jinja2 environment
        env = Environment(loader=FileSystemLoader("templates"))
        
        # Generate HTML content
        html_template = env.get_template("book_template.html")
        html_content = html_template.render(
            book=book_structure,
            style=animation_style
        )
        
        # Generate CSS styles
        css_template = env.get_template("animations.css")
        css_styles = css_template.render(
            animations=animation_style.animations,
            colors=animation_style.color_scheme
        )
        
        # Generate JavaScript animations
        js_template = env.get_template("book_animations.js")
        js_animations = js_template.render(
            transitions=animation_style.transitions
        )
        
        # Create Tailwind class mappings
        tailwind_classes = {
            "container": "container mx-auto px-4",
            "chapter": "my-8 p-6 bg-white rounded-lg shadow-lg",
            "title": f"text-4xl font-{animation_style.typography['heading']} mb-4",
            "content": f"prose lg:prose-xl font-{animation_style.typography['body']}"
        }
        
        return WebAssets(
            html_content=html_content,
            css_styles=css_styles,
            js_animations=js_animations,
            tailwind_classes=tailwind_classes
        )
    except Exception as e:
        logger.error(f"Error generating web assets: {e}")
        raise

# Create the workflow
def create_book_generation_workflow() -> Workflow:
    """Create a workflow for complete book generation with illustrations."""
    workflow = (
        Workflow("generate_book_structure")
        .then_for_each(
            "chapters",
            Workflow("generate_chapter_content")
            .then("generate_chapter_images")
        )
        .then("generate_animation_style")
        .then("generate_web_assets")
    )
    
    # Add input mappings
    workflow.node_input_mappings = {
        "generate_book_structure": {
            "model": "structure_model"
        },
        "generate_chapter_content": {
            "model": "content_model"
        },
        "generate_animation_style": {
            "model": "style_model"
        }
    }
    
    return workflow

# Example usage
async def main(
    theme: str = "Adventure and Discovery",
    genre: str = "Science Fiction",
    audience: str = "Young Adults",
    author: Optional[str] = None,
    output_dir: str = "output",
    structure_model: str = "gemini/gemini-2.0-flash",
    content_model: str = "gemini/gemini-2.0-flash",
    style_model: str = "gemini/gemini-2.0-flash"
):
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create initial context
    initial_context = {
        "theme": theme,
        "genre": genre,
        "audience": audience,
        "author": author,
        "structure_model": structure_model,
        "content_model": content_model,
        "style_model": style_model
    }
    
    # Create and run workflow
    workflow = create_book_generation_workflow()
    engine = workflow.build()
    result = await engine.run(initial_context)
    
    # Save generated assets
    web_assets = result['web_assets']
    (output_path / 'index.html').write_text(web_assets.html_content)
    (output_path / 'styles.css').write_text(web_assets.css_styles)
    (output_path / 'animations.js').write_text(web_assets.js_animations)
    
    print(f"Generated animated book website with illustrations at: {output_path}")
    return result['book_structure']  # Return the complete book structure

if __name__ == "__main__":
    import typer
    typer.run(main)
