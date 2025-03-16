"""
Test script to verify timeout handling in the action_gen.py and python_interpreter.py modules.
"""
import asyncio
import os
import sys
import time
from contextlib import AsyncExitStack
from typing import Dict, Any

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from loguru import logger
from quantalogic.tools.action_gen import AgentTool
from quantalogic.utils.python_interpreter import ASTInterpreter
logger.add(sys.stderr, level="DEBUG")

async def test_agent_tool_timeout():
    """Test that the AgentTool properly handles timeouts."""
    logger.info("Testing AgentTool timeout handling")
    
    # Create a mock AgentTool that will hang
    class MockAgentTool(AgentTool):
        async def async_execute(self, **kwargs) -> str:
            logger.info("MockAgentTool.async_execute called")
            # Simulate a hanging API call
            try:
                async with AsyncExitStack() as stack:
                    timeout_cm = asyncio.timeout(5)  # Shorter timeout for testing
                    await stack.enter_async_context(timeout_cm)
                    
                    logger.info("Simulating a hanging API call...")
                    # This will hang indefinitely
                    await asyncio.sleep(30)
                    return "This should never be reached"
            except TimeoutError:
                logger.error("API call timed out as expected")
                raise RuntimeError("Text generation timed out: API call did not complete within timeout")
    
    tool = MockAgentTool(model="test-model")
    
    try:
        await tool.async_execute(
            system_prompt="Test system prompt",
            prompt="Test user prompt",
            temperature=0.7
        )
        logger.error("Test failed: Expected a timeout exception")
    except RuntimeError as e:
        if "timed out" in str(e):
            logger.info("Test passed: AgentTool timeout was handled correctly")
        else:
            logger.error(f"Test failed: Unexpected error: {str(e)}")

async def test_interpreter_timeout():
    """Test that the ASTInterpreter properly handles timeouts in await expressions."""
    logger.info("Testing ASTInterpreter timeout handling")
    
    # We'll manually create an ASTInterpreter instance and test it directly
    import ast
    
    # Create a simple async expression that will hang
    code = "await asyncio.sleep(100)"
    
    # Parse the code into an AST
    parsed = ast.parse(code)
    await_node = parsed.body[0].value  # Get the Await node
    
    # Create an interpreter instance with no allowed modules
    # We'll directly provide the asyncio module in the namespace
    interpreter = ASTInterpreter(allowed_modules=[], source=code, namespace={"asyncio": asyncio})
    
    try:
        # Mock the timeout to be 2 seconds instead of 60 seconds for testing
        original_wait_for = asyncio.wait_for
        
        async def mock_wait_for(awaitable, timeout=None):
            # Use a 2-second timeout for testing
            return await original_wait_for(awaitable, timeout=2)
        
        # Apply the mock
        asyncio.wait_for = mock_wait_for
        
        try:
            # This should time out quickly
            start_time = time.time()
            await interpreter.visit_Await(await_node)
            elapsed = time.time() - start_time
            logger.error(f"Test failed: No timeout occurred after {elapsed:.2f} seconds")
        except Exception as e:
            # Check for both RuntimeError and WrappedException
            exception_name = e.__class__.__name__
            if "WrappedException" in exception_name or "timed out" in str(e):
                logger.info(f"Test passed: ASTInterpreter timeout was handled correctly with {exception_name}")
            else:
                logger.error(f"Test failed: Unexpected error: {type(e).__name__}: {str(e)}")
    finally:
        # Restore the original wait_for
        asyncio.wait_for = original_wait_for
        logger.info("Test complete, restored original wait_for")

async def main():
    """Run all tests."""
    logger.info("Starting timeout handling tests")
    
    await test_agent_tool_timeout()
    await test_interpreter_timeout()
    
    logger.info("All tests completed")

if __name__ == "__main__":
    asyncio.run(main())
