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


# Parametrized tests to add 100 different cases covering simple assertions.
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
    assert isinstance(res, str)
    assert doubled[0] == i * 2
    # Check that total is computed correctly
    assert total == sum(range(i % 10))
    assert gen_sum == sum(range(i % 5))
