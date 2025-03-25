import pytest
from quantalogic.utils.python_interpreter import execute_async

@pytest.mark.asyncio
async def test_simple_async_function():
    code = "async def foo(): return 42\nawait foo()"
    result = await execute_async(code)
    assert result.result == 42

@pytest.mark.asyncio
async def test_async_with_timeout():
    code = "import asyncio\nasync def delayed(): await asyncio.sleep(2)\nawait delayed()"
    result = await execute_async(code, timeout=1, allowed_modules=['asyncio'])
    assert result.error == 'TimeoutError: '

@pytest.mark.asyncio
async def test_async_generator():
    code = "async def gen(): yield 1; yield 2\n[i async for i in gen()]"
    result = await execute_async(code, allowed_modules=['asyncio'])
    assert result.result == [1, 2]

@pytest.mark.asyncio
async def test_async_exception_handling():
    code = "async def err(): raise ValueError('test')\nawait err()"
    result = await execute_async(code)
    assert 'ValueError: test' in result.error
