#!/usr/bin/env python3
"""
POE API Test Example for Quantalogic Flow

This example demonstrates how to use POE models with quantalogic_flow.
Make sure to set your POE_API_KEY environment variable.

Usage:
    export POE_API_KEY="your-poe-api-key"
    python poe_test.py
"""

import asyncio
import os

from pydantic import BaseModel

from quantalogic_flow.flow import Nodes, Workflow


class Answer(BaseModel):
    answer: str
    confidence: float
    reasoning: str


@Nodes.structured_llm_node(
    system_prompt="You are an expert at answering questions accurately.",
    prompt_template="Answer this question with confidence and reasoning: {{ question }}",
    output="structured_answer",
    response_model=Answer,
    model="poe/Grok-4",  # Using POE's Grok model
    temperature=0.3,
    max_tokens=300
)
async def ask_poe_structured(question: str):
    """Ask a question using POE's Grok model with structured output."""
    pass


async def main():
    """Main test function."""
    if not os.getenv("POE_API_KEY"):
        print("❌ Please set POE_API_KEY environment variable")
        print("Get your API key from: https://poe.com/api_key")
        return

    print("🚀 Testing POE API integration with Quantalogic Flow")
    print("=" * 60)

    # Test 1: Simple POE LLM call
    print("\n📝 Test 1: Simple POE LLM call")
    try:
        workflow1 = Workflow().add(ask_poe, question="What is the capital of France?")
        result1 = await workflow1.build().run({})
        print(f"✅ Success: {result1.get('response', 'No response')[:100]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 2: Structured POE LLM call
    print("\n📝 Test 2: Structured POE LLM call")
    try:
        workflow2 = Workflow().add(ask_poe_structured, question="What is 2 + 2?")
        result2 = await workflow2.build().run({})
        structured_answer = result2.get('structured_answer')
        if structured_answer:
            print(f"✅ Answer: {structured_answer.answer}")
            print(f"✅ Confidence: {structured_answer.confidence}")
            print(f"✅ Reasoning: {structured_answer.reasoning[:100]}...")
        else:
            print("❌ No structured answer received")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n🎉 POE API integration test completed!")


if __name__ == "__main__":
    asyncio.run(main())
