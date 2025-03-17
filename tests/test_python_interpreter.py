import pytest
import asyncio
from quantalogic.python_interpreter import AsyncExecutionResult, execute_async



@pytest.mark.asyncio
async def test_arithmetic():
    # Test basic arithmetic operations.
    source = """
def compute():
    return 1 + 2 * 3 - 4 / 2
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 1 + 2 * 3 - 4 / 2


@pytest.mark.asyncio
async def test_assignment_and_variable():
    # Test variable assignment and usage.
    source = """
def compute():
    a = 10
    b = a * 2
    return b
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 20


@pytest.mark.asyncio
async def test_function_definition_and_call():
    # Test function definition and invocation.
    source = """
def add(x, y):
    return x + y

def compute():
    return add(3, 4)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 7


@pytest.mark.asyncio
async def test_lambda_function():
    # Test lambda function evaluation.
    source = """
def compute():
    f = lambda x: x * 2
    return f(5)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 10


@pytest.mark.asyncio
async def test_list_comprehension():
    # Test list comprehension.
    source = """
def compute():
    return [x * x for x in [1, 2, 3, 4]]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [1, 4, 9, 16]


@pytest.mark.asyncio
async def test_for_loop():
    # Test for loop execution.
    source = """
def compute():
    s = 0
    for i in [1, 2, 3, 4]:
        s = s + i
    return s
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 10


@pytest.mark.asyncio
async def test_while_loop_with_break_continue():
    # Test while loop with break and continue.
    source = """
def compute():
    s = 0
    i = 0
    while i < 10:
        if i % 2 != 0:
            i = i + 1
            continue
        if i == 4:
            break
        s = s + i
        i = i + 1
    return s
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    # Only even numbers below 4: 0 + 2 = 2
    assert result.result == 2


@pytest.mark.asyncio
async def test_import_allowed_module():
    # Test importing an allowed module.
    source = """
import math

def compute():
    return math.sqrt(16)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=["math"])
    assert result.result == 4.0


@pytest.mark.asyncio
async def test_import_disallowed_module():
    # Test error when importing a disallowed module.
    source = """
import os

def compute():
    return os.getcwd()
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=["math"])
    assert "not allowed" in result.error


@pytest.mark.asyncio
async def test_augmented_assignment():
    # Test augmented assignment.
    source = """
def compute():
    a = 5
    a += 10
    return a
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 15


@pytest.mark.asyncio
async def test_comparison_boolean():
    # Test comparison and boolean operators.
    source = """
def compute():
    return (3 < 4) and (5 >= 5) and (6 != 7)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result is True


@pytest.mark.asyncio
async def test_dictionary_list_tuple():
    # Test dictionary, list, and tuple construction.
    source = """
def compute():
    d = {'a': 1, 'b': 2}
    lst = [d['a'], d['b']]
    tpl = (lst[0], lst[1])
    return tpl
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == (1, 2)


@pytest.mark.asyncio
async def test_if_statement():
    # Test if-else statement.
    source = """
def compute():
    if 10 > 5:
        result = "greater"
    else:
        result = "less"
    return result
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "greater"


@pytest.mark.asyncio
async def test_print_function():
    # print returns None from the function
    source = """
def compute():
    print('hello')
    return None
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result is None


@pytest.mark.asyncio
async def test_import_multiple():
    # Test multiple imports
    source = """
import math
import random

def compute():
    return math.sqrt(9)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=["math", "random"])
    assert result.result == 3.0


@pytest.mark.asyncio
async def test_try_except_handling():
    # Test try-except handling
    source = """
def compute():
    try:
        1/0
    except ZeroDivisionError:
        result = 'caught zero division'
    except Exception:
        result = 'caught other'
    else:
        result = 'no error'
    return result
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "caught zero division"


@pytest.mark.asyncio
async def test_list_slice():
    # Test list slicing
    source = """
def compute():
    lst = [1, 2, 3, 4, 5]
    return lst[1:4]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [2, 3, 4]


@pytest.mark.asyncio
async def test_dict_comprehension():
    # Test dictionary comprehension
    source = """
def compute():
    return {x: x*x for x in range(3)}
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == {0: 0, 1: 1, 2: 4}


@pytest.mark.asyncio
async def test_set_comprehension():
    # Test set comprehension
    source = """
def compute():
    return {x for x in range(5) if x % 2 == 0}
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == {0, 2, 4}


@pytest.mark.asyncio
async def test_nested_list_comprehension():
    # Test nested list comprehension
    source = """
def compute():
    return [[i * j for j in range(3)] for i in range(2)]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [[0, 0, 0], [0, 1, 2]]


@pytest.mark.asyncio
async def test_recursive_function_factorial():
    # Test recursive function for factorial
    source = """
def fact(n):
    return 1 if n <= 1 else n * fact(n-1)

def compute():
    return fact(5)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 120


@pytest.mark.asyncio
async def test_class_definition():
    # Test class definition and instance attribute
    source = """
class A:
    def __init__(self, x):
        self.x = x

def compute():
    a = A(10)
    return a.x
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 10


@pytest.mark.asyncio
async def test_with_statement():
    # Test with statement with a custom context manager
    source = """
class Ctx:
    def __enter__(self):
        return 100
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

def compute():
    with Ctx() as x:
        return x
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 100


@pytest.mark.asyncio
async def test_lambda_expression():
    # Test lambda expression
    source = """
def compute():
    f = lambda x: x + 1
    return f(5)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 6


@pytest.mark.asyncio
async def test_generator_expression():
    # Test generator expression
    source = """
def compute():
    gen = (x*x for x in range(4))
    return list(gen)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [0, 1, 4, 9]


@pytest.mark.asyncio
async def test_list_unpacking():
    # Test list unpacking
    source = """
def compute():
    a, b, c = [1, 2, 3]
    return a + b + c
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 6


@pytest.mark.asyncio
async def test_extended_iterable_unpacking():
    # Test extended iterable unpacking
    source = """
def compute():
    a, *b = [1, 2, 3, 4]
    return a + sum(b)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 10


@pytest.mark.asyncio
async def test_f_string():
    # Test f-string
    source = """
def compute():
    name = 'world'
    return f'Hello {name}'
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "Hello world"


@pytest.mark.asyncio
async def test_format_method():
    # Test string format method
    source = """
def compute():
    return 'Hello {}'.format('there')
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "Hello there"


@pytest.mark.asyncio
async def test_simple_conditional_expression():
    # Test conditional expression
    source = """
def compute():
    x = 5
    return 'big' if x > 3 else 'small'
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "big"


@pytest.mark.asyncio
async def test_multiple_statements():
    # Test multiple statements on one line
    source = """
def compute():
    a = 1; b = 2; return a + b
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 3


@pytest.mark.asyncio
async def test_arithmetic_complex():
    # Test complex arithmetic
    source = """
def compute():
    return (2 + 3) * 4 - 5 / 2
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 17.5


@pytest.mark.asyncio
async def test_bool_logic():
    # Test boolean logic
    source = """
def compute():
    return (True and False) or (False or True)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result is True


@pytest.mark.asyncio
async def test_ternary():
    # Test ternary operator
    source = """
def compute():
    x = 10
    return 'even' if x % 2 == 0 else 'odd'
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "even"


@pytest.mark.asyncio
async def test_chained_comparisons():
    # Test chained comparisons
    source = """
def compute():
    return (1 < 2 < 3)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result is True


@pytest.mark.asyncio
async def test_slice_assignment():
    # Test slice assignment
    source = """
def compute():
    lst = [0, 0, 0, 0, 0]
    lst[1:4] = [1, 2, 3]
    return lst
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [0, 1, 2, 3, 0]


@pytest.mark.asyncio
async def test_exception_raising():
    # Test exception raising and catching
    source = """
def f():
    raise ValueError('bad')

def compute():
    try:
        f()
    except ValueError:
        return 'caught'
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "caught"


@pytest.mark.asyncio
async def test_import_error_again():
    # Test import error again
    source = """
import os

def compute():
    return os.getcwd()
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=["math"])
    assert "not allowed" in result.error


@pytest.mark.asyncio
async def test_global_variable():
    # Test global variable
    source = """
a = 5

def foo():
    global a
    a = a + 10

def compute():
    foo()
    return a
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 15


@pytest.mark.asyncio
async def test_nonlocal_variable():
    # Test nonlocal variable
    source = """
def outer():
    a = 5
    def inner():
        nonlocal a
        a += 5
        return a
    return inner()

def compute():
    return outer()
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 10


@pytest.mark.asyncio
async def test_comprehension_scope():
    # Test comprehension scope
    source = """
def compute():
    result = [x for x in range(3)]
    try:
        x
    except NameError:
        result2 = True
    return (result, result2)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == ([0, 1, 2], True)


@pytest.mark.asyncio
async def test_order_of_operations():
    # Test order of operations
    source = """
def compute():
    return 2 + 3 * 4
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 14


@pytest.mark.asyncio
async def test_bitwise_operators():
    # Test bitwise operators
    source = """
def compute():
    return (5 & 3) | (8 ^ 2)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 11


@pytest.mark.asyncio
async def test_is_operator():
    # Test is operator
    source = """
def compute():
    a = [1]
    b = a
    return (a is b)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result is True


@pytest.mark.asyncio
async def test_in_operator():
    # Test in operator
    source = """
def compute():
    lst = [1, 2, 3]
    return (2 in lst)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result is True


@pytest.mark.asyncio
async def test_iterators():
    # Test iterators
    source = """
def compute():
    it = iter([1, 2, 3])
    return next(it)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 1


@pytest.mark.asyncio
async def test_list_concatenation():
    # Test list concatenation
    source = """
def compute():
    return [1] + [2, 3]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [1, 2, 3]


@pytest.mark.asyncio
async def test_dictionary_methods():
    # Test dictionary methods
    source = """
def compute():
    d = {'a': 1, 'b': 2}
    return sorted(list(d.keys()))
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == ["a", "b"]


@pytest.mark.asyncio
async def test_string_methods():
    # Test string methods
    source = """
def compute():
    return 'hello'.upper()
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "HELLO"


@pytest.mark.asyncio
async def test_frozenset():
    # Test frozenset
    source = """
def compute():
    return frozenset([1, 2, 2, 3])
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == frozenset({1, 2, 3})


@pytest.mark.asyncio
async def test_tuple_unpacking():
    # Test tuple unpacking
    source = """
def compute():
    a, b = (10, 20)
    return a * b
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 200


@pytest.mark.asyncio
async def test_complex_numbers():
    # Test complex numbers
    source = """
def compute():
    return (1+2j) * (3+4j)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == complex(-5, 10)


@pytest.mark.asyncio
async def test_try_finally():
    # Test try-finally
    source = """
def compute():
    result = None
    try:
        x = 1/0
    except ZeroDivisionError:
        result = 'handled'
    finally:
        pass
    return result
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "handled"


@pytest.mark.asyncio
async def test_multiple_expressions():
    # Test multiple expressions
    source = """
def compute():
    a = 1
    b = 2
    c = 3
    return a + b + c
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 6


@pytest.mark.asyncio
async def test_nested_functions():
    # Test nested functions
    source = """
def outer():
    def inner():
        return 5
    return inner()

def compute():
    return outer()
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 5


@pytest.mark.asyncio
async def test_list_comprehension_with_function_call():
    # Test list comprehension with function call
    source = """
def square(x):
    return x * x

def compute():
    return [square(x) for x in range(4)]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [0, 1, 4, 9]


@pytest.mark.asyncio
async def test_lambda_closure():
    # Test lambda closure
    source = """
def make_adder(n):
    return lambda x: x + n

def compute():
    adder = make_adder(10)
    return adder(5)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 15


@pytest.mark.asyncio
async def test_generator_iterator():
    # Test generator iterator
    source = """
def gen():
    yield 1
    yield 2

def compute():
    return list(gen())
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [1, 2]


@pytest.mark.asyncio
async def test_operator_precedence():
    # Test operator precedence
    source = """
def compute():
    return 2 ** 3 * 4
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 32


@pytest.mark.asyncio
async def test_nested_dictionary():
    # Test nested dictionary
    source = """
def compute():
    return {'a': {'b': 2}}['a']['b']
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 2


@pytest.mark.asyncio
async def test_slice_of_string():
    # Test slice of string
    source = """
def compute():
    return 'hello'[1:4]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "ell"


@pytest.mark.asyncio
async def test_backslash_in_string():
    # Test backslash in string
    source = """
def compute():
    return 'line1\\nline2'
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "line1\nline2"


@pytest.mark.asyncio
async def test_set_operations():
    # Test set operations
    source = """
def compute():
    s1 = {1, 2, 3}
    s2 = {2, 3, 4}
    union = s1 | s2
    intersection = s1 & s2
    difference = s1 - s2
    return (union, intersection, difference)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == ({1, 2, 3, 4}, {2, 3}, {1})


@pytest.mark.asyncio
async def test_class_inheritance():
    # Test class inheritance
    source = """
class Base:
    def __init__(self):
        self.x = 1

class Derived(Base):
    def __init__(self):
        super().__init__()
        self.y = 2

    def method(self):
        self.x += 2
        self.y += 1
        return (self.x, self.y)

def compute():
    obj = Derived()
    return obj.method()
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == (3, 3)


@pytest.mark.asyncio
async def test_decorator():
    # Test decorator
    source = """
def deco(func):
    def wrapper(*args):
        return func(*args) + 1
    return wrapper

@deco
def add(a, b):
    return a + b

def compute():
    return add(2, 3)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 6


@pytest.mark.asyncio
async def test_nested_generator():
    # Test nested generator
    source = """
def nested_gen():
    for i in range(2):
        yield from (x * i for x in range(3))

def compute():
    return list(nested_gen())
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [0, 0, 0, 0, 1, 2]


@pytest.mark.asyncio
async def test_extended_slice():
    # Test extended slice
    source = """
def compute():
    lst = [0, 1, 2, 3, 4, 5]
    return lst[::2]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [0, 2, 4]


@pytest.mark.asyncio
async def test_string_formatting_multiple():
    # Test multiple string formatting
    source = """
def compute():
    a = 5
    b = 'test'
    return f'{a} is {b}'
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "5 is test"


@pytest.mark.asyncio
async def test_bitwise_shift():
    # Test bitwise shift
    source = """
def compute():
    return (4 << 2) >> 1
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 8  # 4 << 2 = 16, 16 >> 1 = 8


@pytest.mark.asyncio
async def test_complex_arithmetic():
    # Test complex arithmetic
    source = """
def compute():
    return (2 + 3j) + (1 - 2j) * 2
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == (4 - 1j)


@pytest.mark.asyncio
async def test_try_except_finally():
    # Test try-except-finally
    source = """
def compute():
    result = None
    try:
        x = 1 / 0
    except ZeroDivisionError:
        result = "error"
    finally:
        if result is None:
            result = "finally"
    return result
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "error"


@pytest.mark.asyncio
async def test_multi_line_expression():
    # Test multi-line expression
    source = """
def compute():
    return (1 + 2 +
            3 * 4 -
            5)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 10


@pytest.mark.asyncio
async def test_default_arguments():
    # Test default arguments
    source = """
def func(x, y=10):
    return x + y

def compute():
    return func(5)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 15


@pytest.mark.asyncio
async def test_keyword_arguments():
    # Test keyword arguments
    source = """
def func(a, b):
    return a - b

def compute():
    return func(b=3, a=10)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 7


@pytest.mark.asyncio
async def test_star_args():
    # Test star args
    source = """
def sum_all(*args):
    return sum(args)

def compute():
    return sum_all(1, 2, 3, 4)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 10


@pytest.mark.asyncio
async def test_kwargs():
    # Test kwargs
    source = """
def build_dict(**kwargs):
    return kwargs

def compute():
    return build_dict(x=1, y=2)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == {"x": 1, "y": 2}


@pytest.mark.asyncio
async def test_mixed_args():
    # Test mixed args
    source = """
def mixed(a, b=2, *args, **kwargs):
    return a + b + sum(args) + kwargs.get('x', 0)

def compute():
    return mixed(1, 3, 4, 5, x=6)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 19  # 1 + 3 + (4 + 5) + 6


@pytest.mark.asyncio
async def test_list_methods():
    # Test list methods
    source = """
def compute():
    lst = [1, 2, 3]
    lst.append(4)
    lst.pop(0)
    return lst
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [2, 3, 4]


@pytest.mark.asyncio
async def test_string_concatenation():
    # Test string concatenation
    source = """
def compute():
    return 'a' + 'b' * 3
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "abbb"


@pytest.mark.asyncio
async def test_none_comparison():
    # Test None comparison
    source = """
def compute():
    a = None
    return a is None
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result is True


@pytest.mark.asyncio
async def test_boolean_short_circuit():
    # Test boolean short-circuit
    source = """
def risky():
    raise ValueError

def compute():
    return False and risky()
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result is False  # risky() should not be called


@pytest.mark.asyncio
async def test_nested_if():
    # Test nested if
    source = """
def compute():
    x = 10
    if x > 5:
        if x < 15:
            result = "in range"
        else:
            result = "too big"
    else:
        result = "too small"
    return result
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "in range"


@pytest.mark.asyncio
async def test_loop_with_else():
    # Test loop with else
    source = """
def compute():
    result = 0
    for i in range(3):
        result += i
    else:
        result += 10
    return result
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 13  # 0 + 1 + 2 + 10


@pytest.mark.asyncio
async def test_break_in_loop_with_else():
    # Test break in loop with else
    source = """
def compute():
    result = 0
    for i in range(5):
        if i == 2:
            break
        result += i
    else:
        result += 10
    return result
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 1  # 0 + 1, breaks before else


@pytest.mark.asyncio
async def test_property_decorator():
    # Test property decorator
    source = """
class A:
    def __init__(self):
        self._x = 5
    @property
    def x(self):
        return self._x

def compute():
    a = A()
    return a.x
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 5


@pytest.mark.asyncio
async def test_static_method():
    # Test static method
    source = """
class A:
    @staticmethod
    def add(x, y):
        return x + y

def compute():
    return A.add(3, 4)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 7


@pytest.mark.asyncio
async def test_class_method():
    # Test class method
    source = """
class A:
    @classmethod
    def get(cls):
        return 42

def compute():
    return A.get()
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 42


@pytest.mark.asyncio
async def test_type_hint_ignored():
    # Test type hints ignored
    source = """
def add(a: int, b: str) -> float:
    return a + b  # Type hints ignored in execution

def compute():
    return add(3, 4)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 7


@pytest.mark.asyncio
async def test_list_del():
    # Test list deletion
    source = """
def compute():
    lst = [1, 2, 3, 4]
    del lst[1]
    return lst
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [1, 3, 4]


@pytest.mark.asyncio
async def test_dict_del():
    # Test dictionary deletion
    source = """
def compute():
    d = {'a': 1, 'b': 2}
    del d['a']
    return d
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == {'b': 2}


@pytest.mark.asyncio
async def test_augmented_assignments_all():
    # Test all augmented assignments
    source = """
def compute():
    x = 10
    x += 5
    x -= 2
    x *= 3
    x //= 2
    x %= 5
    return x
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 4  # (((10 + 5) - 2) * 3) // 2 % 5


@pytest.mark.asyncio
async def test_empty_structures():
    # Test empty structures
    source = """
def compute():
    a = []
    b = {}
    c = set()
    d = ()
    return (len(a), len(b), len(c), len(d))
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == (0, 0, 0, 0)


@pytest.mark.asyncio
async def test_multi_level_nesting():
    # Test multi-level nesting
    source = """
def compute():
    return {'a': [1, {'b': (2, 3)}]}['a'][1]['b'][1]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 3


@pytest.mark.asyncio
async def test_identity_vs_equality():
    # Test identity vs equality
    source = """
def compute():
    a = [1, 2]
    b = [1, 2]
    return (a == b, a is b)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == (True, False)


@pytest.mark.asyncio
async def test_exception_with_message():
    # Test exception with message
    source = """
def compute():
    try:
        raise ValueError("test error")
    except ValueError as e:
        return str(e)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == "test error"


@pytest.mark.asyncio
async def test_generator_with_condition():
    # Test generator with condition
    source = """
def compute():
    gen = (x for x in range(5) if x % 2 == 0)
    return list(gen)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [0, 2, 4]


@pytest.mark.asyncio
async def test_slice_with_negative_indices():
    # Test slice with negative indices
    source = """
def compute():
    lst = [0, 1, 2, 3, 4]
    return lst[-3:-1]
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == [2, 3]


@pytest.mark.asyncio
async def test_multiple_assignments():
    # Test multiple assignments
    source = """
def compute():
    a = b = c = 5
    return a + b + c
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == 15


@pytest.mark.asyncio
async def test_swap_variables():
    # Test swap variables
    source = """
def compute():
    a = 1
    b = 2
    a, b = b, a
    return (a, b)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=[])
    assert result.result == (2, 1)


# Example of an async test case
@pytest.mark.asyncio
async def test_async_function():
    # Test an async function
    source = """
import asyncio

async def async_compute(x, delay=0.1):
    await asyncio.sleep(delay)
    return x * 2

def compute():
    return async_compute(5)
"""
    result = await execute_async(source, entry_point="compute", allowed_modules=["asyncio"])
    assert result.result == 10
