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
#     "rich>=13.0.0"
# ]
# ///

import asyncio
from collections.abc import Callable
import datetime
import base64
from typing import List, Optional
from pydantic import BaseModel, Field

from loguru import logger
from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType
from ..service import event_observer
from quantalogic.tools.image_generation.stable_diffusion import StableDiffusionTool, BedrockStabilityConfig, STABLE_DIFFUSION_CONFIG
from quantalogic.tools.image_generation.dalle_e import LLMImageGenerationTool, DALLE_CONFIG

# Define Pydantic models for structured output
class ImagePromptAnalysis(BaseModel):
    """Structured analysis of image generation prompt."""
    subject_description: str = Field(description="Detailed description of the main subject")
    style_details: str = Field(description="Artistic style and visual approach")
    composition: str = Field(description="Layout and compositional elements")
    lighting: str = Field(description="Lighting and atmosphere details")
    technical_aspects: str = Field(description="Technical specifications like quality and resolution")
    color_palette: List[str] = Field(description="Suggested color scheme")
    negative_elements: List[str] = Field(description="Elements to avoid in the image")

class EnhancedImagePrompt(BaseModel):
    """Enhanced prompt for image generation."""
    main_prompt: str = Field(description="The enhanced main prompt")
    negative_prompt: str = Field(description="The enhanced negative prompt")
    style_preset: str = Field(description="Selected style preset")
    recommended_size: str = Field(description="Recommended image dimensions")
    cfg_scale: float = Field(description="Recommended cfg_scale value")
    steps: int = Field(description="Recommended number of steps")
    model_type: str = Field(description="Type of model to use (stable_diffusion or dalle)", enum=["stable_diffusion", "dalle"])

class ImageGenerationResult(BaseModel):
    """Result of image generation including base64 data."""
    image_path: str = Field(description="Path to the generated image file")
    base64_data: str = Field(description="Base64 encoded image data")

# Add a list of filtered words and validation functions
FILTERED_WORDS = [
    "fighter", "fight", "combat", "violent", "blood", "gore", "weapon", "gun", "knife",
    # Add other filtered words as needed
]

def contains_filtered_words(text: str) -> List[str]:
    """Check if text contains any filtered words and return the list of found words."""
    text_lower = text.lower()
    return [word for word in FILTERED_WORDS if word in text_lower]

def validate_prompt(prompt: str) -> None:
    """Validate that a prompt doesn't contain filtered words."""
    found_words = contains_filtered_words(prompt)
    if found_words:
        raise ValueError(f"Prompt contains filtered words: {', '.join(found_words)}")

# Node: Analyze and Enhance Prompt
@Nodes.structured_llm_node(
    system_prompt="""You are an expert prompt engineer specializing in image generation. 
    Your task is to analyze and enhance image prompts to get the best possible results from Stable Diffusion.""",
    output="prompt_analysis",
    response_model=ImagePromptAnalysis,
    prompt_template="""
Analyze the following image generation request and break it down into structured components.
Consider artistic elements, technical details, and composition.

User's Request: {{user_prompt}}

Provide a detailed analysis covering:
1. Main subject description (be specific about details)
2. Artistic style and visual approach
3. Composition and layout elements
4. Lighting and atmosphere
5. Technical specifications
6. Suggested color palette
7. Elements to avoid (negative prompt elements)

Remember that Stable Diffusion works best with detailed, specific descriptions.
"""
)
async def analyze_image_prompt(user_prompt: str, model: str) -> ImagePromptAnalysis:
    """Analyze and break down the user's image generation request."""
    logger.debug(f"analyze_image_prompt called with model: {model}")
    pass

# Node: Generate Enhanced Prompt
@Nodes.structured_llm_node(
    system_prompt="""You are an expert prompt engineer for Stable Diffusion. 
    Your task is to enhance image prompts for optimal results.""",
    output="enhanced_prompt",
    response_model=EnhancedImagePrompt,
    prompt_template="""
Based on the following prompt analysis, create an enhanced version optimized for Stable Diffusion.

Analysis:
- Subject: {{prompt_analysis.subject_description}}
- Style: {{prompt_analysis.style_details}}
- Composition: {{prompt_analysis.composition}}
- Lighting: {{prompt_analysis.lighting}}
- Technical: {{prompt_analysis.technical_aspects}}
- Colors: {{", ".join(prompt_analysis.color_palette)}}
- Avoid: {{", ".join(prompt_analysis.negative_elements)}}

Available Style Presets: {{available_styles}}
Available Sizes: {{available_sizes}}
{% if preferred_style %}Preferred Style: {{preferred_style}}{% endif %}
{% if preferred_size %}Preferred Size: {{preferred_size}}{% endif %}
{% if model_type %}Model Type: {{model_type}}{% endif %}

Create:
1. A detailed main prompt that incorporates all key elements
2. A comprehensive negative prompt
3. {% if preferred_style %}Use the specified style preset: {{preferred_style}}{% else %}Select the most appropriate style preset{% endif %}
4. {% if preferred_size %}Use the specified image dimensions: {{preferred_size}}{% else %}Recommend optimal image dimensions{% endif %}
5. Suggest appropriate cfg_scale (0-35) and steps (10-150)

Remember:
- Be specific and descriptive
- Include technical quality terms
- Maintain artistic coherence
- Consider composition and lighting
"""
)
async def generate_enhanced_prompt(
    prompt_analysis: ImagePromptAnalysis,
    available_styles: List[str],
    available_sizes: List[str],
    preferred_style: Optional[str] = None,
    preferred_size: Optional[str] = None,
    model_type: str = "stable_diffusion",
    model: str = "gemini/gemini-2.0-flash"
) -> EnhancedImagePrompt:
    """Generate an enhanced prompt based on the analysis."""
    logger.debug(f"generate_enhanced_prompt called with model: {model}")
    pass

# Node: Generate Image
@Nodes.define(output="image_path")
async def generate_image(enhanced_prompt: EnhancedImagePrompt) -> str:
    """Generate image using the enhanced prompt."""
    try:
        # Validate prompts before sending to the model
        try:
            validate_prompt(enhanced_prompt.main_prompt)
            validate_prompt(enhanced_prompt.negative_prompt)
        except ValueError as e:
            logger.error(f"Prompt validation failed: {e}")
            raise

        # Initialize the appropriate image generation tool based on model type
        if enhanced_prompt.model_type == "dalle":
            tool = LLMImageGenerationTool()
            # Convert size format if needed (e.g., "512x512" -> "1024x1024")
            dalle_size = enhanced_prompt.recommended_size
            if dalle_size not in DALLE_CONFIG["sizes"]:
                # Default to closest DALL-E size
                dalle_size = "1024x1024"
            
            result = await tool.async_execute(
                prompt=enhanced_prompt.main_prompt,
                size=dalle_size,
                quality="standard",  # Can be made configurable
                style="vivid"  # Can be made configurable
            )
        else:  # Default to Stable Diffusion
            tool = StableDiffusionTool()
            
            # Parse and validate size
            try:
                width, height = map(int, enhanced_prompt.recommended_size.split('x'))
                # Ensure dimensions are within valid ranges for Stable Diffusion
                width = max(512, min(1024, width - (width % 64)))
                height = max(512, min(1024, height - (height % 64)))
                size = f"{width}x{height}"
            except (ValueError, AttributeError):
                logger.warning(f"Invalid size format: {enhanced_prompt.recommended_size}, defaulting to 1024x1024")
                size = "1024x1024"
            
            # Validate and adjust steps
            steps = max(10, min(150, enhanced_prompt.steps))
            
            # Validate and adjust cfg_scale
            cfg_scale = max(1.0, min(35.0, enhanced_prompt.cfg_scale))
            
            result = await tool.async_execute(
                prompt=enhanced_prompt.main_prompt,
                negative_prompt=enhanced_prompt.negative_prompt,
                style=enhanced_prompt.style_preset,
                size=size,
                cfg_scale=cfg_scale,
                steps=steps
            )
        
        logger.info(f"Image generated successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        raise

# Node: Convert Image to Base64
@Nodes.define(output="generation_result")
async def convert_to_base64(image_path: str) -> ImageGenerationResult:
    """Convert the generated image to base64 format."""
    try:
        with open(image_path, "rb") as image_file:
            base64_data = base64.b64encode(image_file.read()).decode()
            return ImageGenerationResult(
                image_path=image_path,
                base64_data=base64_data
            )
    except Exception as e:
        logger.error(f"Error converting image to base64: {e}")
        raise

# Create the workflow
def create_image_generation_workflow() -> Workflow:
    """Create a workflow for enhanced image generation."""
    workflow = (
        Workflow("analyze_image_prompt")
        .then("generate_enhanced_prompt")
        .then("generate_image")
        .then("convert_to_base64")
    )
    
    # Add input mappings
    workflow.node_input_mappings = {
        "analyze_image_prompt": {
            "model": "analysis_model"
        },
        "generate_enhanced_prompt": {
            "model": "enhancement_model",
            "available_styles": "available_styles",
            "available_sizes": "available_sizes",
            "preferred_style": "preferred_style",
            "preferred_size": "preferred_size",
            "model_type": "model_type"
        }
    }
    
    return workflow

# Example usage
async def generate_image(
    prompt: str = "Create a cyberpunk city at night",
    style: Optional[str] = None,
    size: Optional[str] = None,
    model_type: str = "stable_diffusion",
    analysis_model: str = "gemini/gemini-2.0-flash",
    enhancement_model: str = "gemini/gemini-2.0-flash",
    _handle_event: Optional[Callable[[str, dict], None]] = None,
    task_id: Optional[str] = None
):
    # Validate model type
    if model_type not in ["stable_diffusion", "dalle"]:
        raise ValueError("model_type must be either 'stable_diffusion' or 'dalle'")
    
    # Get available styles and sizes based on model type
    if model_type == "dalle":
        available_styles = DALLE_CONFIG["styles"]
        available_sizes = DALLE_CONFIG["sizes"]
    else:
        available_styles = STABLE_DIFFUSION_CONFIG["styles"]
        available_sizes = [f"{w}x{h}" for w, h in STABLE_DIFFUSION_CONFIG["sizes"]]
    
    # Validate style and size if provided
    if style and style not in available_styles:
        raise ValueError(f"Invalid style. Available styles: {available_styles}")
    if size and size not in available_sizes:
        raise ValueError(f"Invalid size. Available sizes: {available_sizes}")
    
    # Create initial context
    initial_context = {
        "user_prompt": prompt,
        "analysis_model": analysis_model,
        "enhancement_model": enhancement_model,
        "available_styles": available_styles,
        "available_sizes": available_sizes,
        "model_type": model_type
    }
    
    # Add style and size to context if provided
    if style:
        initial_context["preferred_style"] = style
    if size:
        initial_context["preferred_size"] = size
    
    # Create and run workflow
    workflow = create_image_generation_workflow()
    engine = workflow.build() 

    # Add the event observer if _handle_event is provided
    if _handle_event:
        # Create a lambda to bind task_id to the observer
        bound_observer = lambda event: asyncio.create_task(
            event_observer(event, task_id=task_id, _handle_event=_handle_event)
        )
        engine.add_observer(bound_observer)
        
    result = await engine.run(initial_context)
    
    print(f"Generated image path: {result['generation_result'].image_path}")
    print(f"Base64 data length: {len(result['generation_result'].base64_data)}")

    return result

# CLI wrapper for synchronous usage
def cli_generate_image(
    prompt: str = "Create a cyberpunk city at night",
    style: Optional[str] = None,
    size: Optional[str] = None,
    model_type: str = "stable_diffusion",
    analysis_model: str = "gemini/gemini-2.0-flash",
    enhancement_model: str = "gemini/gemini-2.0-flash"
):
    """CLI wrapper for the image generation function."""
    asyncio.run(generate_image(
        prompt=prompt,
        style=style,
        size=size,
        model_type=model_type,
        analysis_model=analysis_model,
        enhancement_model=enhancement_model
    ))

if __name__ == "__main__":
    import typer
    typer.run(cli_generate_image)
