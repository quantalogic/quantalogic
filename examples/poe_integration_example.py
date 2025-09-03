"""
POE API Integration Example for Quantalogic Flow

This example demonstrates how to use POE API models in Quantalogic Flow workflows.
POE provides access to Claude, Gemini, Grok, and other frontier models through a unified API.

Setup:
1. Get your POE API key from https://poe.com/api_key
2. Set the environment variable: export POE_API_KEY="your-poe-api-key"
3. Run this example to see POE integration in action
"""

import asyncio
import os
from typing import Dict, Any

from quantalogic_flow.flow import Workflow, Nodes


# Example 1: Basic POE Usage
@Nodes.llm_node(
    model="poe/Claude-Sonnet-4",
    system_prompt="You are Claude, a helpful AI assistant accessible through POE API.",
    prompt_template="Analyze this text and provide insights: {{ text }}",
    output="claude_analysis",
    temperature=0.7
)
async def analyze_with_claude(text: str):
    """Analyze text using Claude through POE API."""
    pass  # LLM decorator handles the implementation


# Example 2: Dynamic Model Selection
@Nodes.llm_node(
    model=lambda ctx: f"poe/{ctx['model_name']}",
    system_prompt="You are an AI assistant providing analysis.",
    prompt_template="{{ task }}: {{ content }}",
    output="dynamic_analysis",
    temperature=0.8
)
async def dynamic_poe_analysis(task: str, content: str, model_name: str):
    """Use different POE models dynamically based on the task."""
    pass


# Example 3: Multiple POE Models in Workflow
@Nodes.llm_node(
    model="poe/Gemini-2.0-Flash",
    system_prompt="You are Google's Gemini, providing technical analysis.",
    prompt_template="Provide a technical summary of: {{ content }}",
    output="gemini_summary"
)
async def summarize_with_gemini(content: str):
    """Summarize content using Gemini through POE."""
    pass


@Nodes.llm_node(
    model="poe/Grok-4",
    system_prompt="You are Grok, providing creative and witty responses.",
    prompt_template="Provide a creative perspective on: {{ summary }}",
    output="grok_perspective"
)
async def creative_perspective_with_grok(summary: str):
    """Get creative perspective using Grok through POE."""
    pass


# Example 4: Structured Output with POE
from pydantic import BaseModel


class ContentAnalysis(BaseModel):
    """Structured analysis result."""
    main_topic: str
    key_points: list[str]
    sentiment: str
    confidence_score: float


@Nodes.structured_llm_node(
    model="poe/Claude-Opus-4.1",
    system_prompt="You are Claude Opus, providing structured analysis.",
    prompt_template="Analyze this content: {{ text }}",
    response_model=ContentAnalysis,
    output="structured_analysis"
)
async def structured_analysis_with_claude(text: str):
    """Get structured analysis using Claude Opus through POE."""
    pass


async def demonstrate_basic_usage():
    """Demonstrate basic POE usage."""
    print("🔮 Basic POE Usage Example")
    print("=" * 50)
    
    # Check if POE API key is available
    if not os.getenv("POE_API_KEY"):
        print("⚠️  POE_API_KEY not found. Please set it to run this example.")
        print("   export POE_API_KEY='your-poe-api-key'")
        return
    
    try:
        # Create a simple workflow
        workflow = Workflow().add(
            analyze_with_claude,
            text="Artificial intelligence is transforming how we work and live."
        )
        
        result = await workflow.build().run({})
        print(f"✅ Claude Analysis: {result.get('claude_analysis', 'No result')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


async def demonstrate_dynamic_models():
    """Demonstrate dynamic model selection."""
    print("\n🎯 Dynamic Model Selection Example")
    print("=" * 50)
    
    if not os.getenv("POE_API_KEY"):
        print("⚠️  POE_API_KEY not found.")
        return
    
    models_to_test = [
        ("Claude-Sonnet-4", "Analyze"),
        ("Gemini-2.0-Flash", "Summarize"), 
        ("Grok-4", "Explain creatively")
    ]
    
    for model_name, task in models_to_test:
        try:
            workflow = Workflow().add(
                dynamic_poe_analysis,
                task=task,
                content="The future of renewable energy looks promising.",
                model_name=model_name
            )
            
            result = await workflow.build().run({})
            analysis = result.get('dynamic_analysis', 'No result')
            print(f"✅ {model_name}: {analysis[:100]}...")
            
        except Exception as e:
            print(f"❌ Error with {model_name}: {e}")


async def demonstrate_multi_model_workflow():
    """Demonstrate multiple POE models in a single workflow."""
    print("\n🔄 Multi-Model Workflow Example")
    print("=" * 50)
    
    if not os.getenv("POE_API_KEY"):
        print("⚠️  POE_API_KEY not found.")
        return
    
    try:
        # Create workflow with multiple POE models
        content = """
        Machine learning has evolved rapidly, with transformer architectures 
        revolutionizing natural language processing. From BERT to GPT to modern 
        multimodal models, we've seen unprecedented capabilities emerge.
        """
        
        workflow = (Workflow()
                   .add(summarize_with_gemini, content=content)
                   .add(creative_perspective_with_grok, summary="gemini_summary"))
        
        result = await workflow.build().run({})
        
        print(f"📋 Gemini Summary: {result.get('gemini_summary', 'No result')}")
        print(f"🎭 Grok Perspective: {result.get('grok_perspective', 'No result')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


async def demonstrate_structured_output():
    """Demonstrate structured output with POE."""
    print("\n📊 Structured Output Example")
    print("=" * 50)
    
    if not os.getenv("POE_API_KEY"):
        print("⚠️  POE_API_KEY not found.")
        return
    
    try:
        workflow = Workflow().add(
            structured_analysis_with_claude,
            text="Climate change represents one of the most pressing challenges of our time."
        )
        
        result = await workflow.build().run({})
        analysis = result.get('structured_analysis')
        
        if analysis:
            print(f"📊 Structured Analysis:")
            print(f"   Topic: {analysis.main_topic}")
            print(f"   Key Points: {analysis.key_points}")
            print(f"   Sentiment: {analysis.sentiment}")
            print(f"   Confidence: {analysis.confidence_score}")
        else:
            print("No structured analysis result")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def show_available_models():
    """Show available POE models."""
    print("🔮 Available POE Models")
    print("=" * 50)
    
    models = {
        "Claude Models": [
            "poe/Claude-Sonnet-4",
            "poe/Claude-Opus-4.1", 
            "poe/Claude-Haiku-3.5"
        ],
        "Gemini Models": [
            "poe/Gemini-2.0-Flash",
            "poe/Gemini-1.5-Pro"
        ],
        "Grok Models": [
            "poe/Grok-4",
            "poe/Grok-3"
        ],
        "Other Models": [
            "poe/GPT-4o",
            "poe/o3-mini",
            "poe/DeepSeek-R1"
        ]
    }
    
    for category, model_list in models.items():
        print(f"\n{category}:")
        for model in model_list:
            print(f"  • {model}")


async def main():
    """Run all POE integration examples."""
    print("🚀 POE API Integration Examples")
    print("=" * 60)
    
    # Show available models
    show_available_models()
    
    # Run examples
    await demonstrate_basic_usage()
    await demonstrate_dynamic_models()
    await demonstrate_multi_model_workflow()
    await demonstrate_structured_output()
    
    print("\n✨ POE Integration Demo Complete!")
    print("\nNext Steps:")
    print("1. Get your POE API key: https://poe.com/api_key")
    print("2. Set POE_API_KEY environment variable")
    print("3. Explore different POE models in your workflows")


if __name__ == "__main__":
    asyncio.run(main())