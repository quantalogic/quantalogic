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
from typing import List, Optional
from pydantic import BaseModel, Field

from loguru import logger
from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType
from ..service import event_observer
from quantalogic.tools.llm_vision_tool import LLMVisionTool, DEFAULT_MODEL_NAME

# Define Pydantic models for structured output
class ImageAnalysisResult(BaseModel):
    """Structured analysis of an image."""
    main_subject: str = Field(description="Main subject or focus of the image")
    description: str = Field(description="Detailed description of the image content")
    objects: List[str] = Field(description="List of identified objects in the image")
    colors: List[str] = Field(description="Dominant colors in the image")
    style: str = Field(description="Visual style or artistic approach")
    composition: str = Field(description="Description of image composition")
    mood: str = Field(description="Overall mood or atmosphere")
    technical_details: str = Field(description="Technical aspects like quality, lighting, etc.")

class VisualElements(BaseModel):
    """Analysis of visual elements in the image."""
    composition_details: str = Field(description="Details about the composition")
    color_harmony: str = Field(description="Assessment of color harmony")
    balance: str = Field(description="Evaluation of visual balance")
    visual_flow: str = Field(description="Analysis of visual flow")
    focal_points: str = Field(description="Description of focal points")

class TechnicalQuality(BaseModel):
    """Technical quality assessment of the image."""
    resolution: str = Field(description="Analysis of image resolution")
    lighting: str = Field(description="Evaluation of lighting")
    focus: str = Field(description="Assessment of focus quality")
    dynamic_range: str = Field(description="Analysis of dynamic range")
    quality_metrics: str = Field(description="Overall quality metrics")

class ArtisticStyle(BaseModel):
    """Evaluation of artistic style."""
    style_classification: str = Field(description="Classification of artistic style")
    technique: str = Field(description="Analysis of techniques used")
    influences: str = Field(description="Identified artistic influences")
    creative_elements: str = Field(description="Description of creative elements")
    effectiveness: str = Field(description="Assessment of style effectiveness")

class ContextualAnalysis(BaseModel):
    """Contextual analysis of the image."""
    purpose: str = Field(description="Assessment of image purpose")
    target_audience: str = Field(description="Identified target audience")
    cultural_context: str = Field(description="Cultural context analysis")
    visual_communication: str = Field(description="Analysis of visual communication")
    impact: str = Field(description="Potential impact assessment")

class DetailedAnalysis(BaseModel):
    """Detailed analysis with specific aspects."""
    visual_elements: VisualElements = Field(description="Analysis of visual elements")
    technical_assessment: TechnicalQuality = Field(description="Technical quality assessment")
    artistic_evaluation: ArtisticStyle = Field(description="Artistic style evaluation")
    contextual_insights: ContextualAnalysis = Field(description="Contextual information and insights")
    recommendations: List[str] = Field(description="Suggestions for improvement")

# Node: Initial Image Analysis
@Nodes.structured_llm_node(
    system_prompt="""You are an expert in visual analysis, capable of providing detailed insights about images.
    Your analysis should be comprehensive yet precise, covering both technical and artistic aspects.""",
    output="initial_analysis",
    response_model=ImageAnalysisResult,
    prompt_template="""
Analyze the provided image in detail, considering:
1. Main subject and overall content
2. Objects and elements present
3. Color composition
4. Visual style and artistic approach
5. Composition and layout
6. Mood and atmosphere
7. Technical aspects

Image Context: {{image_context}}
"""
)
async def analyze_image(image_url: str, image_context: str, model: str) -> ImageAnalysisResult:
    """Perform initial analysis of the image."""
    logger.debug(f"analyze_image called with model: {model}")
    
    # Initialize the vision tool
    vision_tool = LLMVisionTool(model_name=model)
    
    # Create system prompt for comprehensive analysis
    system_prompt = """You are an expert in visual analysis, capable of providing detailed insights about images.
    Analyze the image comprehensively, covering technical and artistic aspects. 
    Structure your response to match the required output format."""
    
    # Create the analysis prompt
    analysis_prompt = f"""Please analyze this image in detail and provide a structured response covering:
    1. Identify and describe the main subject
    2. Provide a detailed description of the image content
    3. List all notable objects and elements
    4. Identify dominant colors
    5. Describe the visual style and artistic approach
    6. Analyze the composition and layout
    7. Assess the overall mood and atmosphere
    8. Note technical aspects like quality and lighting

    Additional Context: {image_context}
    
    Format your response to exactly match the required structure."""
    
    try:
        # Execute the vision tool
        response = await vision_tool.async_execute(
            system_prompt=system_prompt,
            prompt=analysis_prompt,
            image_url=image_url,
            temperature="0.7"
        )
        
        # Parse the response into structured format
        try:
            # Extract information from the response text
            # This is a simple parsing example - in production you might want to use a more robust approach
            lines = response.split('\n')
            result = {}
            current_key = None
            
            for line in lines:
                line = line.strip()
                if line.lower().startswith('main subject:'):
                    result['main_subject'] = line.split(':', 1)[1].strip()
                elif line.lower().startswith('description:'):
                    result['description'] = line.split(':', 1)[1].strip()
                elif line.lower().startswith('objects:'):
                    objects_text = line.split(':', 1)[1].strip()
                    result['objects'] = [obj.strip() for obj in objects_text.split(',')]
                elif line.lower().startswith('colors:'):
                    colors_text = line.split(':', 1)[1].strip()
                    result['colors'] = [color.strip() for color in colors_text.split(',')]
                elif line.lower().startswith('style:'):
                    result['style'] = line.split(':', 1)[1].strip()
                elif line.lower().startswith('composition:'):
                    result['composition'] = line.split(':', 1)[1].strip()
                elif line.lower().startswith('mood:'):
                    result['mood'] = line.split(':', 1)[1].strip()
                elif line.lower().startswith('technical details:'):
                    result['technical_details'] = line.split(':', 1)[1].strip()
            
            # Create ImageAnalysisResult instance
            return ImageAnalysisResult(
                main_subject=result.get('main_subject', 'Not specified'),
                description=result.get('description', 'Not specified'),
                objects=result.get('objects', []),
                colors=result.get('colors', []),
                style=result.get('style', 'Not specified'),
                composition=result.get('composition', 'Not specified'),
                mood=result.get('mood', 'Not specified'),
                technical_details=result.get('technical_details', 'Not specified')
            )
            
        except Exception as e:
            logger.error(f"Error parsing vision tool response: {e}")
            raise ValueError(f"Failed to parse vision tool response: {e}")
            
    except Exception as e:
        logger.error(f"Error executing vision tool: {e}")
        raise

# Node: Detailed Analysis
@Nodes.structured_llm_node(
    system_prompt="""You are a visual analysis expert providing in-depth evaluation of images.
    Focus on technical quality, artistic merit, and practical implications.""",
    output="detailed_analysis",
    response_model=DetailedAnalysis,
    prompt_template="""
Based on the initial analysis, provide a detailed evaluation:

Initial Analysis:
- Main Subject: {{initial_analysis.main_subject}}
- Description: {{initial_analysis.description}}
- Objects: {{", ".join(initial_analysis.objects)}}
- Colors: {{", ".join(initial_analysis.colors)}}
- Style: {{initial_analysis.style}}
- Composition: {{initial_analysis.composition}}
- Mood: {{initial_analysis.mood}}
- Technical Details: {{initial_analysis.technical_details}}

Additional Context: {{analysis_context}}

Please provide a detailed analysis in the following structure:

1. Visual Elements Analysis:
- Composition Details: [Details about the composition]
- Color Harmony: [Assessment of color harmony]
- Balance: [Evaluation of visual balance]
- Visual Flow: [Analysis of visual flow]
- Focal Points: [Description of focal points]

2. Technical Quality Assessment:
- Resolution: [Analysis of image resolution]
- Lighting: [Evaluation of lighting]
- Focus: [Assessment of focus quality]
- Dynamic Range: [Analysis of dynamic range]
- Quality Metrics: [Overall quality metrics]

3. Artistic Style Evaluation:
- Style Classification: [Classification of artistic style]
- Technique: [Analysis of techniques used]
- Influences: [Identified artistic influences]
- Creative Elements: [Description of creative elements]
- Effectiveness: [Assessment of style effectiveness]

4. Contextual Analysis:
- Purpose: [Assessment of image purpose]
- Target Audience: [Identified target audience]
- Cultural Context: [Cultural context analysis]
- Visual Communication: [Analysis of visual communication]
- Impact: [Potential impact assessment]

5. Improvement Recommendations:
- List specific suggestions for enhancement, one per line starting with a dash (-)

Please ensure each section follows the exact structure with the specified keys."""
)
async def detailed_analysis(
    initial_analysis: ImageAnalysisResult,
    analysis_context: str,
    model: str
) -> DetailedAnalysis:
    """Generate detailed analysis based on initial findings."""
    logger.debug(f"detailed_analysis called with model: {model}")
    
    # Initialize the vision tool
    vision_tool = LLMVisionTool(model_name=model)
    
    # Create system prompt for detailed analysis
    system_prompt = """You are a visual analysis expert providing in-depth evaluation of images.
    Focus on technical quality, artistic merit, and practical implications.
    Your response must be structured exactly according to the specified format, with clear section headers and key-value pairs."""
    
    # Create the analysis prompt using the initial analysis
    analysis_prompt = f"""Based on the initial analysis, provide a detailed evaluation with the following structure:

    Initial Analysis Summary:
    - Main Subject: {initial_analysis.main_subject}
    - Description: {initial_analysis.description}
    - Objects: {', '.join(initial_analysis.objects)}
    - Colors: {', '.join(initial_analysis.colors)}
    - Style: {initial_analysis.style}
    - Composition: {initial_analysis.composition}
    - Mood: {initial_analysis.mood}
    - Technical Details: {initial_analysis.technical_details}

    Additional Context: {analysis_context}

    Please provide a detailed analysis in the following structure:

    1. Visual Elements Analysis:
    - Composition Details: [Details about the composition]
    - Color Harmony: [Assessment of color harmony]
    - Balance: [Evaluation of visual balance]
    - Visual Flow: [Analysis of visual flow]
    - Focal Points: [Description of focal points]

    2. Technical Quality Assessment:
    - Resolution: [Analysis of image resolution]
    - Lighting: [Evaluation of lighting]
    - Focus: [Assessment of focus quality]
    - Dynamic Range: [Analysis of dynamic range]
    - Quality Metrics: [Overall quality metrics]

    3. Artistic Style Evaluation:
    - Style Classification: [Classification of artistic style]
    - Technique: [Analysis of techniques used]
    - Influences: [Identified artistic influences]
    - Creative Elements: [Description of creative elements]
    - Effectiveness: [Assessment of style effectiveness]

    4. Contextual Analysis:
    - Purpose: [Assessment of image purpose]
    - Target Audience: [Identified target audience]
    - Cultural Context: [Cultural context analysis]
    - Visual Communication: [Analysis of visual communication]
    - Impact: [Potential impact assessment]

    5. Improvement Recommendations:
    - List specific suggestions for enhancement, one per line starting with a dash (-)

    Please ensure each section follows the exact structure with the specified keys."""
    
    try:
        # Execute the vision tool
        response = await vision_tool.async_execute(
            system_prompt=system_prompt,
            prompt=analysis_prompt,
            image_url="",  # We don't need the image URL for the second stage
            temperature="0.7"
        )
        
        # Parse the response into structured format
        try:
            # Initialize dictionaries for each section
            visual_elements_data = {}
            technical_assessment_data = {}
            artistic_evaluation_data = {}
            contextual_insights_data = {}
            recommendations = []
            
            # Split the response into sections
            sections = response.split('\n\n')
            current_section = None
            
            for section in sections:
                section = section.strip()
                if not section:
                    continue
                
                # Identify the section
                if '1. Visual Elements Analysis:' in section:
                    current_section = 'visual'
                elif '2. Technical Quality Assessment:' in section:
                    current_section = 'technical'
                elif '3. Artistic Style Evaluation:' in section:
                    current_section = 'artistic'
                elif '4. Contextual Analysis:' in section:
                    current_section = 'contextual'
                elif '5. Improvement Recommendations:' in section:
                    current_section = 'recommendations'
                    # Extract recommendations
                    for line in section.split('\n'):
                        if line.strip().startswith('-'):
                            recommendations.append(line.strip('- ').strip())
                else:
                    # Process key-value pairs for the current section
                    for line in section.split('\n'):
                        if ':' in line:
                            key, value = [part.strip() for part in line.split(':', 1)]
                            key = key.strip('- ').lower().replace(' ', '_')
                            
                            if current_section == 'visual':
                                visual_elements_data[key] = value
                            elif current_section == 'technical':
                                technical_assessment_data[key] = value
                            elif current_section == 'artistic':
                                artistic_evaluation_data[key] = value
                            elif current_section == 'contextual':
                                contextual_insights_data[key] = value
            
            # Create the structured analysis objects
            visual_elements = VisualElements(
                composition_details=visual_elements_data.get('composition_details', 'Not specified'),
                color_harmony=visual_elements_data.get('color_harmony', 'Not specified'),
                balance=visual_elements_data.get('balance', 'Not specified'),
                visual_flow=visual_elements_data.get('visual_flow', 'Not specified'),
                focal_points=visual_elements_data.get('focal_points', 'Not specified')
            )
            
            technical_assessment = TechnicalQuality(
                resolution=technical_assessment_data.get('resolution', 'Not specified'),
                lighting=technical_assessment_data.get('lighting', 'Not specified'),
                focus=technical_assessment_data.get('focus', 'Not specified'),
                dynamic_range=technical_assessment_data.get('dynamic_range', 'Not specified'),
                quality_metrics=technical_assessment_data.get('quality_metrics', 'Not specified')
            )
            
            artistic_evaluation = ArtisticStyle(
                style_classification=artistic_evaluation_data.get('style_classification', 'Not specified'),
                technique=artistic_evaluation_data.get('technique', 'Not specified'),
                influences=artistic_evaluation_data.get('influences', 'Not specified'),
                creative_elements=artistic_evaluation_data.get('creative_elements', 'Not specified'),
                effectiveness=artistic_evaluation_data.get('effectiveness', 'Not specified')
            )
            
            contextual_insights = ContextualAnalysis(
                purpose=contextual_insights_data.get('purpose', 'Not specified'),
                target_audience=contextual_insights_data.get('target_audience', 'Not specified'),
                cultural_context=contextual_insights_data.get('cultural_context', 'Not specified'),
                visual_communication=contextual_insights_data.get('visual_communication', 'Not specified'),
                impact=contextual_insights_data.get('impact', 'Not specified')
            )
            
            # Create the final DetailedAnalysis instance
            return DetailedAnalysis(
                visual_elements=visual_elements,
                technical_assessment=technical_assessment,
                artistic_evaluation=artistic_evaluation,
                contextual_insights=contextual_insights,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error parsing detailed analysis response: {e}")
            raise ValueError(f"Failed to parse detailed analysis response: {e}")
            
    except Exception as e:
        logger.error(f"Error executing vision tool for detailed analysis: {e}")
        raise

# Create the workflow
def create_image_analysis_workflow() -> Workflow:
    """Create a workflow for comprehensive image analysis."""
    workflow = (
        Workflow("analyze_image")
        .then("detailed_analysis")
    )
    
    # Add input mappings
    workflow.node_input_mappings = {
        "analyze_image": {
            "model": "vision_model"
        },
        "detailed_analysis": {
            "model": "analysis_model"
        }
    }
    
    return workflow

# Main analysis function
async def analyze_image_workflow(
    image_url: str,
    image_context: str = "",
    analysis_context: str = "",
    vision_model: str = DEFAULT_MODEL_NAME,
    analysis_model: str = "gemini/gemini-2.0-flash",
    _handle_event: Optional[Callable[[str, dict], None]] = None,
    task_id: Optional[str] = None
):
    """Run the complete image analysis workflow."""
    
    # Create initial context
    initial_context = {
        "image_url": image_url,
        "image_context": image_context,
        "analysis_context": analysis_context,
        "vision_model": vision_model,
        "analysis_model": analysis_model
    }
    
    # Create and run workflow
    workflow = create_image_analysis_workflow()
    engine = workflow.build()

    # Add the event observer if _handle_event is provided
    if _handle_event:
        bound_observer = lambda event: asyncio.create_task(
            event_observer(event, task_id=task_id, _handle_event=_handle_event)
        )
        engine.add_observer(bound_observer)
    
    result = await engine.run(initial_context)
    
    logger.info("Image analysis completed successfully")
    return result

# CLI wrapper for synchronous usage
def cli_analyze_image(
    image_url: str,
    image_context: str = "",
    analysis_context: str = "",
    vision_model: str = DEFAULT_MODEL_NAME,
    analysis_model: str = "gemini/gemini-2.0-flash"
):
    """CLI wrapper for the image analysis function."""
    asyncio.run(analyze_image_workflow(
        image_url=image_url,
        image_context=image_context,
        analysis_context=analysis_context,
        vision_model=vision_model,
        analysis_model=analysis_model
    ))

if __name__ == "__main__":
    # Example usage with a local image
    local_image_path = "file:///home/yarab/Bureau/trash_agents_tests/f1/generated_images/sd_20250331_115658.png"
    print("\nAnalyzing local image:", local_image_path)
    
    # Test with direct asyncio call for more detailed output
    async def run_test():
        result = await analyze_image_workflow(
            image_url=local_image_path,
            image_context="This is a generated image from Stable Diffusion",
            analysis_context="Please focus on the artistic style and composition",
            vision_model=DEFAULT_MODEL_NAME,
            analysis_model="gemini/gemini-2.0-flash"
        )
        print("\nInitial Analysis:")
        print(result["initial_analysis"].model_dump_json(indent=2))
        print("\nDetailed Analysis:")
        print(result["detailed_analysis"].model_dump_json(indent=2))

    asyncio.run(run_test())
    
    # Alternatively, you can use the CLI interface:
    # import typer
    # typer.run(cli_analyze_image)