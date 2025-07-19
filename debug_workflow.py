#!/usr/bin/env python3
"""
Debug script to test individual nodes and see what's happening
"""

import asyncio
import os
import sys
sys.path.append('quantalogic_flow/examples/linkedin_introduce_content')

from linkedin_introduce_content import *
from quantalogic_flow.flow import Nodes

async def debug_generate_linkedin_post():
    """Test the generate_linkedin_post function directly"""
    
    # Mock content analysis
    content_analysis = ContentAnalysis(
        content_type="Test",
        primary_topic="Testing",
        target_audience=["Developers"],
        key_points=["Test point 1", "Test point 2"],
        title="Test Content"
    )
    
    # Mock viral strategy
    viral_strategy = ViralStrategy(
        hook_type="Question",
        value_proposition="Test value",
        suggested_hashtags=["#Test"],
        engagement_tactics=["Ask question"]
    )
    
    markdown_content = "# Test Content\nThis is a test markdown file for testing the workflow."
    model = "gemini/gemini-2.5-flash"
    intent = "test"
    
    print("=== Testing generate_linkedin_post ===")
    print(f"Content Analysis: {content_analysis}")
    print(f"Viral Strategy: {viral_strategy}")
    print(f"Markdown Content: {markdown_content}")
    print(f"Model: {model}")
    print(f"Intent: {intent}")
    
    try:
        result = await generate_linkedin_post(
            content_analysis=content_analysis,
            viral_strategy=viral_strategy,
            markdown_content=markdown_content,
            model=model,
            intent=intent
        )
        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result) if result else 'None'}")
        print(f"Result preview: {result[:200] if result else 'None'}...")
        return result
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(debug_generate_linkedin_post())
