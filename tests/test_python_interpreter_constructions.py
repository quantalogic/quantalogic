import pytest


# Test simple if/else construct
def test_if_else():
    x = 10
    if x > 5:
        result = "high"
    else:
        result = "low"
    assert result == "high"


# Test while loop
def test_while_loop():
    i, total = 0, 0
    while i < 5:
        total += i
        i += 1
    assert total == 10


# Test for loop and list comprehension
def test_for_loop_and_comprehension():
    numbers = [i for i in range(5)]
    total = 0
    for num in numbers:
        total += num
    assert total == 10


# Test exception handling using try/except
def test_exception_handling():
    try:
        1 / 0
    except ZeroDivisionError:
        caught = True
    else:
        caught = False
    assert caught is True


# Test lambda function and map
def test_lambda_and_map():
    nums = [1, 2, 3]
    squares = list(map(lambda x: x**2, nums))
    assert squares == [1, 4, 9]


# Test with context manager
def test_context_manager(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    f = d / "example.txt"
    with f.open("w") as file:
        file.write("data")
    assert f.read_text() == "data"


# Test a simple decorator
def decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs) + 1

    return wrapper


@decorator
def add(a: int, b: int) -> int:
    return a + b


def test_decorator():
    assert add(2, 3) == 6


# Test generator expression
def test_generator_expression():
    gen = (i * 2 for i in range(5))
    result = list(gen)
    assert result == [0, 2, 4, 6, 8]


# Test dictionary comprehension and error handling in dict access
def test_dict_comprehension():
    keys = ["a", "b", "c"]
    d = {k: ord(k) for k in keys}
    try:
        dummy = d["z"]
    except KeyError:
        dummy = None
    assert dummy is None


# Enhanced comprehensive test suite below:

# Test set comprehension and membership
def test_set_comprehension():
    evens = {x for x in range(10) if x % 2 == 0}
    assert evens == {0, 2, 4, 6, 8}
    assert 4 in evens
    assert 3 not in evens


# Test class definition and inheritance
def test_class_and_inheritance():
    class Base:
        def __init__(self):
            self.value = 1

    class Derived(Base):
        def increment(self):
            self.value += 1

    obj = Derived()
    obj.increment()
    assert obj.value == 2


# Test nested functions and closures
def test_nested_functions():
    def outer(x):
        def inner(y):
            return x + y
        return inner
    closure = outer(5)
    assert closure(3) == 8


# Test bitwise operations
def test_bitwise_operations():
    a = 5  # 0101 in binary
    b = 3  # 0011 in binary
    assert (a & b) == 1  # 0001
    assert (a | b) == 7  # 0111
    assert (a ^ b) == 6  # 0110
    assert (~a & 0b1111) == 10  # ~0101 = 1010 (within 4 bits)


# Test string formatting and methods
def test_string_operations():
    name = "test"
    formatted = f"hello {name}"
    assert formatted == "hello test"
    assert "TEST" == name.upper()
    assert formatted.split() == ["hello", "test"]


# Test tuple unpacking and slicing
def test_tuple_operations():
    t = (1, 2, 3, 4)
    a, b, *rest = t
    assert a == 1
    assert b == 2
    assert rest == [3, 4]
    assert t[1:3] == (2, 3)


# Test generator function with yield
def test_generator_function():
    def gen():
        for i in range(3):
            yield i * 2
    result = list(gen())
    assert result == [0, 2, 4]


# Test conditional expressions (ternary)
def test_conditional_expression():
    x = 7
    result = "positive" if x > 0 else "non-positive"
    assert result == "positive"


# Test import and module usage (mocked for simplicity)
def test_mock_import():
    # Assuming a safe environment, we'll simulate a module
    class MockMath:
        pi = 3.14
    import sys
    sys.modules['math'] = MockMath
    from math import pi
    assert pi == 3.14


# Test augmented assignments
def test_augmented_assignments():
    x = 10
    x += 5
    x *= 2
    x //= 3
    assert x == 10


# Test complex numbers
def test_complex_numbers():
    c = 1 + 2j
    d = 2 + 3j
    assert c + d == (3 + 5j)
    assert c * d == (-4 + 7j)


# Test chaining comparisons and boolean logic
def test_chained_comparisons():
    x = 5
    assert 3 < x < 7
    assert (x > 0) and (x < 10) or (x == 0)


# Parametrized tests to add 100 different cases covering simple assertions
@pytest.mark.parametrize("i", list(range(100)))
def test_parametrized(i: int):
    # Use various Python constructions in a single test:
    # if/else
    res = "even" if i % 2 == 0 else "odd"
    # list comprehension and lambda
    doubled = list(map(lambda x: x * 2, [i]))
    # for loop and aggregation
    total = 0
    for n in range(i % 10):
        total += n
    # generator expression
    gen_sum = sum(n for n in range(i % 5))
    # set operations
    evens = {n for n in range(i % 10) if n % 2 == 0}
    # dictionary with string formatting
    d = {f"key_{i}": i}
    # bitwise check
    bit_check = i & 1 == 0
    # assertions
    assert isinstance(res, str)
    assert doubled[0] == i * 2
    assert total == sum(range(i % 10))
    assert gen_sum == sum(range(i % 5))
    assert len(evens) == ((i % 10 + 1) // 2)
    assert d[f"key_{i}"] == i
    assert bit_check == (i % 2 == 0)


# Test try/except/else/finally
def test_full_exception_handling():
    result = None
    try:
        x = 1 / 1
    except ZeroDivisionError:
        result = "zero"
    else:
        result = "success"
    finally:
        result += " done"
    assert result == "success done"
