import asyncio

from quantalogic.python_interpreter import AsyncExecutionResult, execute_async


async def test_square_calculation() -> None:
    """Test the square calculation using execute_async with entry_point."""
    # Python code as a string that defines multiple functions
    square_code = """
def calculate_square(x):
    return x * x

async def async_square(x, delay=0.1):
    await asyncio.sleep(delay)
    return x * x
"""
    
    # Test synchronous function with entry_point
    sync_result = await execute_async(
        code=square_code,
        entry_point="calculate_square",
        args=(5,),
        timeout=5.0,
        allowed_modules=['asyncio']
    )
    print("Synchronous Square Test:")
    print_execution_result(sync_result)
    
    # Test asynchronous function with entry_point
    async_result = await execute_async(
        code=square_code,
        entry_point="async_square",
        args=(5,),
        kwargs={"delay": 0.2},
        timeout=5.0,
        allowed_modules=['asyncio']
    )
    print("Asynchronous Square Test:")
    print_execution_result(async_result)


async def test_arithmetic_operations() -> None:
    """Test arithmetic operations with multiple arguments."""
    # Python code with a function taking multiple arguments
    arithmetic_code = """
def add_and_multiply(a, b, c=2):
    return (a + b) * c

async def async_add_and_multiply(a, b, c=2, delay=0.1):
    await asyncio.sleep(delay)
    return (a + b) * c
"""
    
    # Test synchronous function
    sync_result = await execute_async(
        code=arithmetic_code,
        entry_point="add_and_multiply",
        args=(3, 4),
        kwargs={"c": 5},
        timeout=5.0,
        allowed_modules=['asyncio']
    )
    print("Synchronous Add and Multiply Test:")
    print_execution_result(sync_result)
    
    # Test asynchronous function
    async_result = await execute_async(
        code=arithmetic_code,
        entry_point="async_add_and_multiply",
        args=(3, 4),
        kwargs={"c": 5, "delay": 0.15},
        timeout=5.0,
        allowed_modules=['asyncio']
    )
    print("Asynchronous Add and Multiply Test:")
    print_execution_result(async_result)


async def test_module_execution() -> None:
    """Test execution of the entire module without an entry_point."""
    # Python code that runs top-level statements
    module_code = """
x = 1 + 2
y = x * 3
result = y
"""
    
    # Execute without specifying an entry_point
    result = await execute_async(
        code=module_code,
        timeout=5.0,
        allowed_modules=['asyncio']
    )
    print("Module Execution Test (no entry_point):")
    print_execution_result(result)


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
    await test_arithmetic_operations()
    await test_module_execution()


if __name__ == '__main__':
    asyncio.run(main())