import pytest
from quantalogic.utils.python_interpreter import interpret_code

def test_arithmetic():
    # Test basic arithmetic operations.
    source = "1 + 2 * 3 - 4 / 2"
    result = interpret_code(source, allowed_modules=[])
    assert result == 1 + 2 * 3 - 4 / 2

def test_assignment_and_variable():
    # Test variable assignment and usage.
    source = "a = 10\nb = a * 2\nb"
    result = interpret_code(source, allowed_modules=[])
    assert result == 20

def test_function_definition_and_call():
    # Test function definition and invocation.
    source = """
def add(x, y):
    return x + y
result = add(3, 4)
result
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 7

def test_lambda_function():
    # Test lambda function evaluation.
    source = "f = lambda x: x * 2\nf(5)"
    result = interpret_code(source, allowed_modules=[])
    assert result == 10

def test_list_comprehension():
    # Test list comprehension.
    source = "[x * x for x in [1,2,3,4]]"
    result = interpret_code(source, allowed_modules=[])
    assert result == [1, 4, 9, 16]

def test_for_loop():
    # Test for loop execution.
    source = """
s = 0
for i in [1,2,3,4]:
    s = s + i
s
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 10

def test_while_loop_with_break_continue():
    # Test while loop with break and continue.
    source = """
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
s
"""
    result = interpret_code(source, allowed_modules=[])
    # Only even numbers below 4: 0 + 2 = 2
    assert result == 2

def test_import_allowed_module():
    # Test importing an allowed module.
    source = "import math\nmath.sqrt(16)"
    result = interpret_code(source, allowed_modules=["math"])
    assert result == 4.0

def test_import_disallowed_module():
    # Test error when importing a disallowed module.
    source = "import os\nos.getcwd()"
    with pytest.raises(Exception) as excinfo:
        interpret_code(source, allowed_modules=["math"])
    assert "not allowed" in str(excinfo.value)

def test_augmented_assignment():
    # Test augmented assignment.
    source = "a = 5\na += 10\na"
    result = interpret_code(source, allowed_modules=[])
    assert result == 15

def test_comparison_boolean():
    # Test comparison and boolean operators.
    source = "result = (3 < 4) and (5 >= 5) and (6 != 7)\nresult"
    result = interpret_code(source, allowed_modules=[])
    assert result is True

def test_dictionary_list_tuple():
    # Test dictionary, list, and tuple construction.
    source = """
d = {'a': 1, 'b': 2}
lst = [d['a'], d['b']]
tpl = (lst[0], lst[1])
tpl
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == (1, 2)

def test_if_statement():
    # Test if-else statement.
    source = """
if 10 > 5:
    result = "greater"
else:
    result = "less"
result
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == "greater"
