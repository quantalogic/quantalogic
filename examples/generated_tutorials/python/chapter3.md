# **Chapter 3: Data Structures and File Handling**

---

## **Learning Objectives**
- Learn about lists, tuples, dictionaries, and sets.  
- Understand how to manipulate and iterate over data structures.  
- Explore file handling for reading and writing data.  

---

## **Sections**

### **1. Lists**
Lists are one of the most versatile and commonly used data structures in Python. They are ordered, mutable (can be changed), and allow duplicate elements.

#### **Creating and Accessing List Elements**
```python
# Creating a list
fruits = ["apple", "banana", "cherry"]

# Accessing elements by index
print(fruits[0])  # Output: apple
print(fruits[-1]) # Output: cherry (negative indexing)
```

#### **List Methods**
Python provides several built-in methods to manipulate lists:
- `append()`: Adds an element to the end of the list.
- `remove()`: Removes the first occurrence of a value.
- `sort()`: Sorts the list in ascending order.
- `reverse()`: Reverses the order of the list.

```python
fruits.append("orange")  # Adds "orange" to the list
fruits.remove("banana")  # Removes "banana"
fruits.sort()            # Sorts the list alphabetically
print(fruits)            # Output: ['apple', 'cherry', 'orange']
```

#### **List Comprehensions**
List comprehensions provide a concise way to create lists. They are often used to apply an operation to each item in a sequence.

```python
# Create a list of squares of numbers from 1 to 5
squares = [x**2 for x in range(1, 6)]
print(squares)  # Output: [1, 4, 9, 16, 25]
```

#### **Example: Find the Largest Number in a List**
```python
numbers = [10, 20, 4, 45, 99]
largest = max(numbers)
print(f"The largest number is: {largest}")  # Output: The largest number is: 99
```

---

### **2. Tuples and Sets**
Tuples and sets are two other important data structures in Python.

#### **Tuples**
Tuples are similar to lists but are immutable (cannot be changed after creation). They are often used for fixed collections of items.

```python
# Creating a tuple
coordinates = (10, 20)

# Accessing elements
print(coordinates[0])  # Output: 10

# Tuples are immutable
# coordinates[0] = 15  # This will raise an error
```

#### **Sets**
Sets are unordered collections of unique elements. They are useful for operations like removing duplicates or checking membership.

```python
# Creating a set
unique_numbers = {1, 2, 3, 3, 4}
print(unique_numbers)  # Output: {1, 2, 3, 4} (duplicates are removed)

# Adding and removing elements
unique_numbers.add(5)
unique_numbers.remove(2)
print(unique_numbers)  # Output: {1, 3, 4, 5}
```

#### **Example: Remove Duplicates from a List Using a Set**
```python
numbers = [1, 2, 2, 3, 4, 4, 5]
unique_numbers = list(set(numbers))
print(unique_numbers)  # Output: [1, 2, 3, 4, 5]
```

---

### **3. Dictionaries**
Dictionaries store data as key-value pairs. They are unordered, mutable, and do not allow duplicate keys.

#### **Key-Value Pairs and Dictionary Methods**
```python
# Creating a dictionary
student = {"name": "Alice", "age": 21, "grade": "A"}

# Accessing values
print(student["name"])  # Output: Alice

# Adding or updating values
student["age"] = 22
student["city"] = "New York"

# Dictionary methods
print(student.keys())   # Output: dict_keys(['name', 'age', 'grade', 'city'])
print(student.values()) # Output: dict_values(['Alice', 22, 'A', 'New York'])
```

#### **Iterating Over Dictionaries**
You can loop through a dictionary using its keys, values, or items (key-value pairs).

```python
for key, value in student.items():
    print(f"{key}: {value}")
# Output:
# name: Alice
# age: 22
# grade: A
# city: New York
```

#### **Example: Store and Retrieve Student Grades**
```python
grades = {"Alice": 85, "Bob": 90, "Charlie": 78}

# Add a new student
grades["Diana"] = 88

# Retrieve a grade
print(grades["Bob"])  # Output: 90
```

---

### **4. File Handling**
File handling is essential for reading from and writing to files. Python provides built-in functions to work with files.

#### **Opening, Reading, and Writing Files**
```python
# Writing to a file
with open("example.txt", "w") as file:
    file.write("Hello, World!")

# Reading from a file
with open("example.txt", "r") as file:
    content = file.read()
    print(content)  # Output: Hello, World!
```

#### **Using `with` for File Operations**
The `with` statement ensures that the file is properly closed after its suite finishes, even if an exception is raised.

#### **Handling CSV Files**
CSV (Comma-Separated Values) files are commonly used for storing tabular data. Python's `csv` module makes it easy to work with CSV files.

```python
import csv

# Writing to a CSV file
with open("students.csv", "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Name", "Age", "Grade"])
    writer.writerow(["Alice", 21, "A"])
    writer.writerow(["Bob", 22, "B"])

# Reading from a CSV file
with open("students.csv", "r") as file:
    reader = csv.reader(file)
    for row in reader:
        print(row)
# Output:
# ['Name', 'Age', 'Grade']
# ['Alice', '21', 'A']
# ['Bob', '22', 'B']
```

#### **Example: Count the Number of Words in a Text File**
```python
with open("example.txt", "r") as file:
    content = file.read()
    words = content.split()
    print(f"Number of words: {len(words)}")
```

---

### **5. Mini Project: To-Do List Application**
Build a simple to-do list application where users can add, view, and delete tasks. Tasks should be saved to and loaded from a file.

#### **Code Example**
```python
def load_tasks():
    try:
        with open("tasks.txt", "r") as file:
            tasks = file.readlines()
        return [task.strip() for task in tasks]
    except FileNotFoundError:
        return []

def save_tasks(tasks):
    with open("tasks.txt", "w") as file:
        for task in tasks:
            file.write(task + "\n")

def add_task(tasks):
    task = input("Enter a new task: ")
    tasks.append(task)
    save_tasks(tasks)
    print("Task added!")

def view_tasks(tasks):
    if not tasks:
        print("No tasks found.")
    else:
        print("Your tasks:")
        for i, task in enumerate(tasks, 1):
            print(f"{i}. {task}")

def delete_task(tasks):
    view_tasks(tasks)
    try:
        task_num = int(input("Enter the task number to delete: "))
        if 1 <= task_num <= len(tasks):
            tasks.pop(task_num - 1)
            save_tasks(tasks)
            print("Task deleted!")
        else:
            print("Invalid task number.")
    except ValueError:
        print("Please enter a valid number.")

def main():
    tasks = load_tasks()
    while True:
        print("\nTo-Do List Application")
        print("1. Add Task")
        print("2. View Tasks")
        print("3. Delete Task")
        print("4. Exit")
        choice = input("Choose an option: ")
        if choice == "1":
            add_task(tasks)
        elif choice == "2":
            view_tasks(tasks)
        elif choice == "3":
            delete_task(tasks)
        elif choice == "4":
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
```

#### **How It Works**
1. **Load Tasks**: Tasks are loaded from a file (`tasks.txt`) when the program starts.
2. **Save Tasks**: Tasks are saved to the file whenever they are added or deleted.
3. **Add Task**: Users can add a new task, which is appended to the list and saved.
4. **View Tasks**: Users can view all tasks in the list.
5. **Delete Task**: Users can delete a task by specifying its number.
6. **Exit**: The program exits when the user chooses to quit.

---

## **Conclusion**
In this chapter, you learned about Python's core data structures (lists, tuples, sets, and dictionaries) and how to manipulate them. You also explored file handling, including reading from and writing to files, and worked with CSV files. Finally, you built a to-do list application to apply these concepts in a practical project.

In the next chapter, you'll dive into more advanced topics like Object-Oriented Programming (OOP) and working with external libraries. Keep practicing and experimenting with the concepts covered so far!