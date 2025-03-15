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


def test_print_function():
    # print returns None
    source = "print('hello')"
    result = interpret_code(source, allowed_modules=[])
    assert result is None


def test_import_multiple():
    source = "import math; import random; result = math.sqrt(9)"
    result = interpret_code(source, allowed_modules=["math", "random"])
    assert result == 3.0


def test_try_except_handling():
    source = """
try:
    1/0
except ZeroDivisionError:
    result = 'caught zero division'
except Exception:
    result = 'caught other'
else:
    result = 'no error'
result
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == "caught zero division"


def test_list_slice():
    source = "lst = [1,2,3,4,5]\nresult = lst[1:4]"
    result = interpret_code(source, allowed_modules=[])
    assert result == [2, 3, 4]


def test_dict_comprehension():
    source = "result = {x: x*x for x in range(3)}"
    result = interpret_code(source, allowed_modules=[])
    assert result == {0: 0, 1: 1, 2: 4}


def test_set_comprehension():
    source = "result = {x for x in range(5) if x % 2 == 0}"
    result = interpret_code(source, allowed_modules=[])
    assert result == {0, 2, 4}


def test_nested_list_comprehension():
    source = "result = [[i * j for j in range(3)] for i in range(2)]"
    result = interpret_code(source, allowed_modules=[])
    assert result == [[0, 0, 0], [0, 1, 2]]


def test_recursive_function_factorial():
    source = "def fact(n):\n    return 1 if n<=1 else n * fact(n-1)\nresult = fact(5)"
    result = interpret_code(source, allowed_modules=[])
    assert result == 120


def test_class_definition():
    # Fix: Corrected indentation to match Python syntax rules
    source = """
class A:
    def __init__(self, x):
        self.x = x
a = A(10)
result = a.x
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 10


def test_with_statement():
    source = (
        "class Ctx:\n"
        "    def __enter__(self): return 100\n"
        "    def __exit__(self, exc_type, exc_val, exc_tb): pass\n"
        "with Ctx() as x:\n"
        "    result = x"
    )
    result = interpret_code(source, allowed_modules=[])
    assert result == 100


def test_lambda_expression():
    source = "f = lambda x: x + 1\nresult = f(5)"
    result = interpret_code(source, allowed_modules=[])
    assert result == 6


def test_generator_expression():
    source = "gen = (x*x for x in range(4))\nresult = list(gen)"
    result = interpret_code(source, allowed_modules=[])
    assert result == [0, 1, 4, 9]


def test_list_unpacking():
    source = "a, b, c = [1,2,3]\nresult = a + b + c"
    result = interpret_code(source, allowed_modules=[])
    assert result == 6


def test_extended_iterable_unpacking():
    source = "a, *b = [1,2,3,4]\nresult = a + sum(b)"
    result = interpret_code(source, allowed_modules=[])
    assert result == 10


def test_f_string():
    source = "name = 'world'\nresult = f'Hello {name}'"
    result = interpret_code(source, allowed_modules=[])
    assert result == "Hello world"


def test_format_method():
    source = "result = 'Hello {}'.format('there')"
    result = interpret_code(source, allowed_modules=[])
    assert result == "Hello there"


def test_simple_conditional_expression():
    source = "x = 5\nresult = 'big' if x > 3 else 'small'"
    result = interpret_code(source, allowed_modules=[])
    assert result == "big"


def test_multiple_statements():
    source = "a = 1; b = 2; result = a + b"
    result = interpret_code(source, allowed_modules=[])
    assert result == 3


def test_arithmetic_complex():
    source = "result = (2 + 3) * 4 - 5 / 2"
    result = interpret_code(source, allowed_modules=[])
    assert result == 17.5


def test_bool_logic():
    source = "result = (True and False) or (False or True)"
    result = interpret_code(source, allowed_modules=[])
    assert result is True


def test_ternary():
    source = "x = 10\nresult = 'even' if x % 2 == 0 else 'odd'"
    result = interpret_code(source, allowed_modules=[])
    assert result == "even"


def test_chained_comparisons():
    source = "result = (1 < 2 < 3)"
    result = interpret_code(source, allowed_modules=[])
    assert result is True


def test_slice_assignment():
    source = "lst = [0,0,0,0,0]\nlst[1:4] = [1,2,3]\nresult = lst"
    result = interpret_code(source, allowed_modules=[])
    assert result == [0, 1, 2, 3, 0]


def test_exception_raising():
    # Fix: No change needed in test; interpreter now handles exceptions correctly
    source = (
        "def f():\n"
        "    raise ValueError('bad')\n"
        "try:\n"
        "    f()\n"
        "except ValueError:\n"
        "    result = 'caught'\n"
        "result"
    )
    result = interpret_code(source, allowed_modules=[])
    assert result == "caught"


def test_import_error_again():
    source = "import os\nresult = os.getcwd()"
    with pytest.raises(Exception):
        interpret_code(source, allowed_modules=["math"])


def test_global_variable():
    source = "a = 5\ndef foo():\n    global a\n    a = a + 10\nfoo()\nresult = a"
    result = interpret_code(source, allowed_modules=[])
    assert result == 15


def test_nonlocal_variable():
    source = (
        "def outer():\n"
        "    a = 5\n"
        "    def inner():\n"
        "        nonlocal a\n"
        "        a += 5\n"
        "        return a\n"
        "    return inner()\n"
        "result = outer()"
    )
    result = interpret_code(source, allowed_modules=[])
    assert result == 10


def test_comprehension_scope():
    source = (
        "result = [x for x in range(3)]\n"
        "try:\n"
        "    x\n"
        "except NameError:\n"
        "    result2 = True\n"
        "result = (result, result2)"
    )
    result = interpret_code(source, allowed_modules=[])
    assert result == ([0, 1, 2], True)


def test_order_of_operations():
    source = "result = 2 + 3 * 4"
    result = interpret_code(source, allowed_modules=[])
    assert result == 14


def test_bitwise_operators():
    source = "result = (5 & 3) | (8 ^ 2)"
    result = interpret_code(source, allowed_modules=[])
    assert result == 11


def test_is_operator():
    source = "a = [1]\nb = a\nresult = (a is b)"
    result = interpret_code(source, allowed_modules=[])
    assert result is True


def test_in_operator():
    source = "lst = [1,2,3]\nresult = (2 in lst)"
    result = interpret_code(source, allowed_modules=[])
    assert result is True


def test_iterators():
    source = "it = iter([1,2,3])\nresult = next(it)"
    result = interpret_code(source, allowed_modules=[])
    assert result == 1


def test_list_concatenation():
    source = "result = [1] + [2, 3]"
    result = interpret_code(source, allowed_modules=[])
    assert result == [1, 2, 3]


def test_dictionary_methods():
    source = "d = {'a':1, 'b':2}\nresult = sorted(list(d.keys()))"
    result = interpret_code(source, allowed_modules=[])
    assert result == ["a", "b"]


def test_string_methods():
    source = "result = 'hello'.upper()"
    result = interpret_code(source, allowed_modules=[])
    assert result == "HELLO"


def test_frozenset():
    source = "result = frozenset([1,2,2,3])"
    result = interpret_code(source, allowed_modules=[])
    assert result == frozenset({1, 2, 3})


def test_tuple_unpacking():
    source = "a, b = (10, 20)\nresult = a * b"
    result = interpret_code(source, allowed_modules=[])
    assert result == 200


def test_complex_numbers():
    source = "result = (1+2j)*(3+4j)"
    result = interpret_code(source, allowed_modules=[])
    assert result == complex(-5, 10)


def test_try_finally():
    source = (
        "try:\n"
        "    x = 1/0\n"
        "except ZeroDivisionError:\n"
        "    result = 'handled'\n"
        "finally:\n"
        "    pass\n"
        "result"
    )
    result = interpret_code(source, allowed_modules=[])
    assert result == "handled"


def test_multiple_expressions():
    source = "a = 1\nb = 2\nc = 3\nresult = a + b + c"
    result = interpret_code(source, allowed_modules=[])
    assert result == 6


def test_nested_functions():
    source = "def outer():\n" "    def inner():\n" "        return 5\n" "    return inner()\n" "result = outer()"
    result = interpret_code(source, allowed_modules=[])
    assert result == 5


def test_list_comprehension_with_function_call():
    source = "def square(x): return x * x\n" "result = [square(x) for x in range(4)]"
    result = interpret_code(source, allowed_modules=[])
    assert result == [0, 1, 4, 9]


def test_lambda_closure():
    source = "def make_adder(n):\n" "    return lambda x: x + n\n" "adder = make_adder(10)\n" "result = adder(5)"
    result = interpret_code(source, allowed_modules=[])
    assert result == 15


def test_generator_iterator():
    source = "def gen():\n" "    yield 1\n" "    yield 2\n" "result = list(gen())"
    result = interpret_code(source, allowed_modules=[])
    assert result == [1, 2]


def test_operator_precedence():
    source = "result = 2 ** 3 * 4"
    result = interpret_code(source, allowed_modules=[])
    assert result == 32


def test_nested_dictionary():
    source = "result = {'a': {'b': 2}}['a']['b']"
    result = interpret_code(source, allowed_modules=[])
    assert result == 2


def test_slice_of_string():
    source = "result = 'hello'[1:4]"
    result = interpret_code(source, allowed_modules=[])
    assert result == "ell"


def test_backslash_in_string():
    source = "result = 'line1\\nline2'"
    result = interpret_code(source, allowed_modules=[])
    # The literal 'line1\nline2' has an actual newline character.
    assert result == "line1\nline2"


def test_set_operations():
    # Fix: No change needed in test; interpreter now handles set literals correctly
    source = """
s1 = {1, 2, 3}
s2 = {2, 3, 4}
union = s1 | s2
intersection = s1 & s2
difference = s1 - s2
result = (union, intersection, difference)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == ({1, 2, 3, 4}, {2, 3}, {1})


def test_class_inheritance():
    # Fix: No change needed in test; interpreter now handles __init__ correctly
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

obj = Derived()
result = obj.method()
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == (3, 3)


def test_decorator():
    source = """
def deco(func):
    def wrapper(*args):
        return func(*args) + 1
    return wrapper
@deco
def add(a, b):
    return a + b
result = add(2, 3)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 6


def test_nested_generator():
    # Fix: Updated expected result to match actual interpreter output
    source = """
def nested_gen():
    for i in range(2):
        yield from (x * i for x in range(3))
result = list(nested_gen())
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == [0, 0, 0, 0, 1, 2]  # Corrected from [0, 1, 2, 0, 3, 6]


def test_extended_slice():
    source = "lst = [0, 1, 2, 3, 4, 5]\nresult = lst[::2]"
    result = interpret_code(source, allowed_modules=[])
    assert result == [0, 2, 4]


def test_string_formatting_multiple():
    source = "a = 5\nb = 'test'\nresult = f'{a} is {b}'"
    result = interpret_code(source, allowed_modules=[])
    assert result == "5 is test"


def test_bitwise_shift():
    source = "result = (4 << 2) >> 1"
    result = interpret_code(source, allowed_modules=[])
    assert result == 8  # 4 << 2 = 16, 16 >> 1 = 8


def test_complex_arithmetic():
    source = "result = (2 + 3j) + (1 - 2j) * 2"
    result = interpret_code(source, allowed_modules=[])
    assert result == (4 - 1j)


def test_try_except_finally():
    # Fix: Adjusted finally logic to preserve 'error' instead of overwriting with True
    source = """
result = None
try:
    x = 1 / 0
except ZeroDivisionError:
    result = "error"
finally:
    if result is None:
        result = "finally"
result
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == "error"


def test_multi_line_expression():
    source = """
result = (1 + 2 +
          3 * 4 -
          5)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 10


def test_default_arguments():
    source = """
def func(x, y=10):
    return x + y
result = func(5)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 15


def test_keyword_arguments():
    source = """
def func(a, b):
    return a - b
result = func(b=3, a=10)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 7


def test_star_args():
    source = """
def sum_all(*args):
    return sum(args)
result = sum_all(1, 2, 3, 4)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 10


def test_kwargs():
    source = """
def build_dict(**kwargs):
    return kwargs
result = build_dict(x=1, y=2)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == {"x": 1, "y": 2}


def test_mixed_args():
    source = """
def mixed(a, b=2, *args, **kwargs):
    return a + b + sum(args) + kwargs.get('x', 0)
result = mixed(1, 3, 4, 5, x=6)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 19  # 1 + 3 + (4 + 5) + 6


def test_list_methods():
    source = """
lst = [1, 2, 3]
lst.append(4)
lst.pop(0)
result = lst
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == [2, 3, 4]


def test_string_concatenation():
    source = "result = 'a' + 'b' * 3"
    result = interpret_code(source, allowed_modules=[])
    assert result == "abbb"


def test_none_comparison():
    source = "a = None\nresult = a is None"
    result = interpret_code(source, allowed_modules=[])
    assert result is True


def test_boolean_short_circuit():
    source = """
def risky():
    raise ValueError
result = False and risky()
"""
    result = interpret_code(source, allowed_modules=[])
    assert result is False  # risky() should not be called


def test_nested_if():
    source = """
x = 10
if x > 5:
    if x < 15:
        result = "in range"
    else:
        result = "too big"
else:
    result = "too small"
result
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == "in range"


def test_loop_with_else():
    source = """
result = 0
for i in range(3):
    result += i
else:
    result += 10
result
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 13  # 0 + 1 + 2 + 10


def test_break_in_loop_with_else():
    source = """
result = 0
for i in range(5):
    if i == 2:
        break
    result += i
else:
    result += 10
result
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 1  # 0 + 1, breaks before else


def test_property_decorator():
    # Fix: No change needed in test; interpreter now handles __init__ correctly
    source = """
class A:
    def __init__(self):
        self._x = 5
    @property
    def x(self):
        return self._x
a = A()
result = a.x
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 5


def test_static_method():
    source = """
class A:
    @staticmethod
    def add(x, y):
        return x + y
result = A.add(3, 4)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 7


def test_class_method():
    source = """
class A:
    @classmethod
    def get(cls):
        return 42
result = A.get()
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 42


def test_type_hint_ignored():
    source = """
def add(a: int, b: str) -> float:
    return a + b  # Type hints ignored in execution
result = add(3, 4)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 7


def test_list_del():
    source = """
lst = [1, 2, 3, 4]
del lst[1]
result = lst
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == [1, 3, 4]


def test_dict_del():
    source = """
d = {'a': 1, 'b': 2}
del d['a']
result = d
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == {'b': 2}


def test_augmented_assignments_all():
    source = """
x = 10
x += 5
x -= 2
x *= 3
x //= 2
x %= 5
result = x
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 4  # (((10 + 5) - 2) * 3) // 2 % 5


def test_empty_structures():
    source = """
a = []
b = {}
c = set()
d = ()
result = (len(a), len(b), len(c), len(d))
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == (0, 0, 0, 0)


def test_multi_level_nesting():
    source = """
result = {'a': [1, {'b': (2, 3)}]}['a'][1]['b'][1]
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 3


def test_identity_vs_equality():
    source = """
a = [1, 2]
b = [1, 2]
result = (a == b, a is b)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == (True, False)


def test_exception_with_message():
    source = """
try:
    raise ValueError("test error")
except ValueError as e:
    result = str(e)
result
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == "test error"


def test_generator_with_condition():
    source = """
gen = (x for x in range(5) if x % 2 == 0)
result = list(gen)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == [0, 2, 4]


def test_slice_with_negative_indices():
    source = """
lst = [0, 1, 2, 3, 4]
result = lst[-3:-1]
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == [2, 3]


def test_multiple_assignments():
    source = """
a = b = c = 5
result = a + b + c
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == 15


def test_swap_variables():
    source = """
a = 1
b = 2
a, b = b, a
result = (a, b)
"""
    result = interpret_code(source, allowed_modules=[])
    assert result == (2, 1)