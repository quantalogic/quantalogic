import asyncio

from quantalogic.utils.python_interpreter import AsyncExecutionResult, execute_async


async def test_square_calculation() -> None:
    """Test the square calculation using execute_async."""
    # Python code as a string that calculates the square of a number
    square_code = """
async def main():
    # Define a function to calculate square
    def calculate_square(x):
        return x * x

    # Calculate square of 5
    number = 5
    result = calculate_square(number)
    print(f'The square of {number} is {result}.')

    # Return the result explicitly
    return result
    """
    
    # Execute the code asynchronously with a timeout of 5 seconds
    execution_result = await execute_async(
        code=square_code,
        timeout=5.0,
        allowed_modules=['asyncio']
    )
    
    # Print detailed information about the execution result
    print_execution_result(execution_result)
    
    return execution_result


def print_execution_result(result: AsyncExecutionResult) -> None:
    """Print detailed information about an execution result."""
    print("===== Execution Result =====")
    if result.error:
        print(f"❌ Error: {result.error}")
    else:
        print("✅ Execution successful!")
        print(f"Result type: {type(result.result).__name__}")
        print(f"Result value: {result.result}")
    print(f"Execution time: {result.execution_time:.4f} seconds")
    print("============================")


async def main() -> None:
    """Run all tests."""
    await test_square_calculation()


if __name__ == '__main__':
    asyncio.run(main())