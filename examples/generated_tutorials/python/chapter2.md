# Chapter 2: Control Flow and Functions

In this chapter, you will learn how to control the flow of your Python programs using conditional statements and loops. You will also learn how to define and use functions to write reusable and modular code. By the end of this chapter, you will be able to write more complex programs and handle errors gracefully.

---

## **2.1 Conditional Statements**

Conditional statements allow your program to make decisions based on certain conditions. Python provides `if`, `elif`, and `else` statements for this purpose.

### **`if` Statement**
The `if` statement checks a condition and executes a block of code if the condition is `True`.

```python
x = 10
if x > 5:
    print("x is greater than 5")
```

### **`elif` Statement**
The `elif` (else if) statement checks additional conditions if the previous conditions are `False`.

```python
x = 10
if x > 15:
    print("x is greater than 15")
elif x > 5:
    print("x is greater than 5 but less than or equal to 15")
```

### **`else` Statement**
The `else` statement executes a block of code if none of the previous conditions are `True`.

```python
x = 10
if x > 15:
    print("x is greater than 15")
elif x > 5:
    print("x is greater than 5 but less than or equal to 15")
else:
    print("x is 5 or less")
```

### **Nested Conditions**
You can nest `if` statements inside other `if` statements to check multiple conditions.

```python
x = 10
if x > 5:
    if x < 15:
        print("x is between 5 and 15")
```

### **Example: Determine if a Number is Positive, Negative, or Zero**
```python
number = float(input("Enter a number: "))

if number > 0:
    print("The number is positive.")
elif number < 0:
    print("The number is negative.")
else:
    print("The number is zero.")
```

---

## **2.2 Loops**

Loops allow you to repeat a block of code multiple times. Python provides `for` loops and `while` loops for this purpose.

### **`for` Loop**
The `for` loop iterates over a sequence (e.g., a list, string, or range) and executes a block of code for each item in the sequence.

```python
for i in range(5):
    print(i)  # Output: 0 1 2 3 4
```

### **`while` Loop**
The `while` loop repeats a block of code as long as a condition is `True`.

```python
count = 0
while count < 5:
    print(count)
    count += 1  # Output: 0 1 2 3 4
```

### **`break` and `continue` Statements**
- `break`: Exits the loop immediately.
- `continue`: Skips the rest of the code in the loop and moves to the next iteration.

```python
for i in range(10):
    if i == 5:
        break  # Exit the loop when i is 5
    print(i)  # Output: 0 1 2 3 4

for i in range(10):
    if i % 2 == 0:
        continue  # Skip even numbers
    print(i)  # Output: 1 3 5 7 9
```

### **Example: Print the Multiplication Table of a Given Number**
```python
number = int(input("Enter a number: "))

for i in range(1, 11):
    print(f"{number} x {i} = {number * i}")
```

---

## **2.3 Functions**

Functions allow you to encapsulate reusable code into a single block. You can define a function using the `def` keyword.

### **Defining Functions**
```python
def greet(name):
    print(f"Hello, {name}!")

greet("Alice")  # Output: Hello, Alice!
```

### **Parameters and Return Values**
Functions can take parameters and return values using the `return` statement.

```python
def add(a, b):
    return a + b

result = add(3, 5)
print(result)  # Output: 8
```

### **Scope of Variables**
- **Local Variables**: Variables defined inside a function are local to that function.
- **Global Variables**: Variables defined outside a function are global and can be accessed anywhere.

```python
x = 10  # Global variable

def my_function():
    y = 5  # Local variable
    print(x + y)

my_function()  # Output: 15
```

### **Example: Calculate the Factorial of a Number**
```python
def factorial(n):
    if n == 0 or n == 1:
        return 1
    else:
        return n * factorial(n - 1)

result = factorial(5)
print(result)  # Output: 120
```

---

## **2.4 Error Handling**

Error handling allows you to manage unexpected errors in your program using `try`, `except`, and `finally` blocks.

### **`try` and `except`**
The `try` block contains code that might raise an exception, and the `except` block handles the exception.

```python
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Cannot divide by zero!")
```

### **`finally`**
The `finally` block executes code regardless of whether an exception occurred.

```python
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Cannot divide by zero!")
finally:
    print("Execution complete.")
```

### **Common Exceptions**
- `ValueError`: Raised when a function receives an argument of the correct type but inappropriate value.
- `TypeError`: Raised when an operation is performed on an inappropriate type.

### **Example: Safe Division with Error Handling**
```python
try:
    numerator = int(input("Enter the numerator: "))
    denominator = int(input("Enter the denominator: "))
    result = numerator / denominator
    print(f"Result: {result}")
except ZeroDivisionError:
    print("Error: Cannot divide by zero.")
except ValueError:
    print("Error: Invalid input. Please enter integers.")
```

---

## **2.5 Mini Project: Number Guessing Game**

In this mini-project, you will build a number guessing game where the user guesses a randomly generated number. The program will provide hints after each guess.

### **Steps:**
1. Generate a random number between 1 and 100.
2. Ask the user to guess the number.
3. Provide hints like "Too high" or "Too low" based on the user's guess.
4. Repeat until the user guesses the correct number.

### **Code:**
```python
import random

def number_guessing_game():
    number_to_guess = random.randint(1, 100)
    attempts = 0

    while True:
        guess = int(input("Guess the number (between 1 and 100): "))
        attempts += 1

        if guess < number_to_guess:
            print("Too low! Try again.")
        elif guess > number_to_guess:
            print("Too high! Try again.")
        else:
            print(f"Congratulations! You guessed the number in {attempts} attempts.")
            break

number_guessing_game()
```

---

## **Summary**

In this chapter, you learned how to:
- Use conditional statements (`if`, `elif`, `else`) to make decisions in your programs.
- Implement loops (`for`, `while`) to repeat code blocks.
- Define and use functions to write reusable and modular code.
- Handle errors using `try`, `except`, and `finally`.

You also built a **Number Guessing Game** as a mini-project to apply these concepts. In the next chapter, you will explore data structures like lists, tuples, dictionaries, and sets, and learn how to handle files in Python.

--- 

**Next Chapter:** [Chapter 3: Data Structures and File Handling](#)