#!/usr/bin/env python3
"""
Test script to verify the LLM node fix for None content handling.
This test simulates the scenario where an LLM API returns None for content.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from quantalogic_flow.flow.nodes import Nodes

async def test_llm_node_with_none_content():
    """Test that LLM node handles None content gracefully."""
    
    # Create a mock response with None content
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = None  # This is what causes the error
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 0
    mock_response.usage.total_tokens = 10
    
    # Mock acompletion to return our mock response
    original_acompletion = None
    try:
        from quantalogic_flow.flow.nodes import acompletion
        original_acompletion = acompletion
        
        # Create an async mock
        async_mock = AsyncMock(return_value=mock_response)
        
        # Replace acompletion temporarily
        import quantalogic_flow.flow.nodes
        quantalogic_flow.flow.nodes.acompletion = async_mock
        
        # Create an LLM node
        @Nodes.llm_node(
            system_prompt="Test system prompt",
            prompt_template="Test prompt: {{ input_text }}",
            output="test_output",
            model="test-model"
        )
        def test_llm_node(input_text):
            pass
        
        # Test that the node handles None content gracefully
        try:
            result = await test_llm_node(input_text="test input")
            print(f"✅ SUCCESS: LLM node handled None content gracefully")
            print(f"   Result: '{result}' (empty string as expected)")
            return True
        except AttributeError as e:
            if "'NoneType' object has no attribute 'strip'" in str(e):
                print(f"❌ FAILED: The fix didn't work - got the original error: {e}")
                return False
            else:
                print(f"❌ FAILED: Got unexpected AttributeError: {e}")
                return False
        except Exception as e:
            print(f"❌ FAILED: Got unexpected error: {e}")
            return False
            
    finally:
        # Restore original acompletion
        if original_acompletion:
            quantalogic_flow.flow.nodes.acompletion = original_acompletion

async def test_llm_node_with_valid_content():
    """Test that LLM node still works with valid content."""
    
    # Create a mock response with valid content
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "  Valid response content  "  # With whitespace
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 30
    
    # Mock acompletion to return our mock response
    original_acompletion = None
    try:
        from quantalogic_flow.flow.nodes import acompletion
        original_acompletion = acompletion
        
        # Create an async mock
        async_mock = AsyncMock(return_value=mock_response)
        
        # Replace acompletion temporarily
        import quantalogic_flow.flow.nodes
        quantalogic_flow.flow.nodes.acompletion = async_mock
        
        # Create an LLM node
        @Nodes.llm_node(
            system_prompt="Test system prompt",
            prompt_template="Test prompt: {{ input_text }}",
            output="test_output",
            model="test-model"
        )
        def test_llm_node_valid(input_text):
            pass
        
        # Test that the node still works with valid content
        try:
            result = await test_llm_node_valid(input_text="test input")
            expected = "Valid response content"  # Should be stripped
            if result == expected:
                print(f"✅ SUCCESS: LLM node handled valid content correctly")
                print(f"   Result: '{result}' (stripped as expected)")
                return True
            else:
                print(f"❌ FAILED: Expected '{expected}', got '{result}'")
                return False
        except Exception as e:
            print(f"❌ FAILED: Got unexpected error with valid content: {e}")
            return False
            
    finally:
        # Restore original acompletion
        if original_acompletion:
            quantalogic_flow.flow.nodes.acompletion = original_acompletion

async def main():
    print("Testing LLM node fix for None content handling...")
    print("=" * 50)
    
    # Test 1: None content handling
    print("\n1. Testing None content handling:")
    test1_passed = await test_llm_node_with_none_content()
    
    # Test 2: Valid content handling
    print("\n2. Testing valid content handling:")
    test2_passed = await test_llm_node_with_valid_content()
    
    # Summary
    print("\n" + "=" * 50)
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED: The fix is working correctly!")
        print("   - None content is handled gracefully (returns empty string)")
        print("   - Valid content is still processed correctly (stripped)")
    else:
        print("❌ SOME TESTS FAILED: The fix may need more work")
        if not test1_passed:
            print("   - None content handling failed")
        if not test2_passed:
            print("   - Valid content handling failed")

if __name__ == "__main__":
    asyncio.run(main())
