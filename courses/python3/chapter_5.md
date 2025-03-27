## Chapter 5: Automation & Scripting with Python

### Why Automate? 🤖

Imagine spending hours manually renaming hundreds of files, sifting through log files for specific errors, or sending personalized emails one by one. Tedious, right? Automation is the superhero that swoops in to rescue you from these repetitive tasks. It not only saves time but also reduces the risk of human error, leading to increased efficiency and productivity. Think of it as building your own digital assistant!

### What We'll Cover 📚

This chapter dives deep into the world of Python automation. We'll explore how to:

*   Manipulate files and directories.
*   Master regular expressions for powerful text processing.
*   Automate system administration tasks.
*   Schedule tasks for recurring execution.
*   Utilize threading and multiprocessing for performance gains.

### How to Automate Like a Pro 🚀

Let's get our hands dirty with some code!

#### 1. File and Directory Manipulation 🗂️

Python's `os` and `shutil` modules are your best friends when it comes to interacting with the file system.

**Example:** Creating a new directory

```python
import os

# Create a directory if it doesn't exist
if not os.path.exists("my_new_directory"):
    os.makedirs("my_new_directory")
    print("Directory created!")
else:
    print("Directory already exists.")
```

**Example:** Copying a file

```python
import shutil

# Copy a file from source to destination
source_file = "my_file.txt"
destination_file = "my_new_directory/my_file_copy.txt"

shutil.copy(source_file, destination_file)
print("File copied!")
```

**Example:** Renaming a file

```python
import os

# Rename a file
old_name = "my_file.txt"
new_name = "renamed_file.txt"

os.rename(old_name, new_name)
print("File renamed!")
```

#### 2. Regular Expressions: Text Processing Powerhouse 🔍

Regular expressions (regex) are sequences of characters that define a search pattern. The `re` module in Python allows you to use regex for searching, replacing, and manipulating text.

**Example:** Finding email addresses in a string

```python
import re

text = "Contact us at support@example.com or sales@another.com for assistance."
emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
print(emails)  # Output: ['support@example.com', 'sales@another.com']
```

**Explanation:**

*   `[a-zA-Z0-9._%+-]+`: Matches one or more alphanumeric characters, dots, underscores, percentage signs, plus or minus signs (common in email usernames).
*   `@`: Matches the "@" symbol.
*   `[a-zA-Z0-9.-]+`: Matches one or more alphanumeric characters, dots, or hyphens (domain name).
*   `\.`: Matches a literal dot (escaped with a backslash).
*   `[a-zA-Z]{2,}`: Matches two or more alphabetic characters (top-level domain).

**Example:** Replacing text using regex

```python
import re

text = "Replace all occurrences of 'apple' with 'orange'."
new_text = re.sub(r"apple", "orange", text)
print(new_text)  # Output: Replace all occurrences of 'orange' with 'orange'.
```

#### 3. System Administration Tasks 🛠️

Automate user management, log analysis, and other system tasks. You'll need appropriate permissions to execute these.

**Example:** Getting CPU usage

```python
import psutil

cpu_usage = psutil.cpu_percent(interval=1) #Get CPU usage every 1 second
print(f"CPU Usage: {cpu_usage}%")
```

**Example:** Getting Memory usage

```python
import psutil

memory = psutil.virtual_memory()
print(f"Total memory: {memory.total}")
print(f"Available memory: {memory.available}")
```

#### 4. Task Scheduling ⏰

Automate tasks using your operating system's built-in scheduler (cron on Linux/macOS, Task Scheduler on Windows). Python scripts can be triggered by these schedulers.

**Example (Conceptual):**

1.  Write a Python script to back up your important files.
2.  On Linux/macOS, use `crontab -e` to edit your cron table and add a line like:

    ```
    0 0 * * * python /path/to/backup_script.py
    ```

    This will run the script every day at midnight.
3. On Windows, use "Task Scheduler" to schedule the script to run at specific times.

#### 5. Threading and Multiprocessing 🧵

For CPU-bound or I/O-bound tasks, use threading or multiprocessing to improve performance.

**Example:** Using threading to download multiple files concurrently

```python
import threading
import requests

def download_file(url, filename):
    response = requests.get(url)
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"Downloaded {filename}")

urls = [
    "https://www.easygifanimator.net/images/samples/video-to-gif-sample.gif",
    "https://upload.wikimedia.org/wikipedia/commons/2/2c/Rotating_earth_%28large%29.gif",
    "https://i.imgur.com/rZXj0Gu.gif"
]

threads = []
for i, url in enumerate(urls):
    filename = f"file_{i}.gif"
    thread = threading.Thread(target=download_file, args=(url, filename))
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()

print("All files downloaded!")
```

### When to Automate? 🤔

*   **Repetitive Tasks:** Anything you do frequently and consistently is a prime candidate.
*   **Time-Consuming Processes:** Tasks that take a significant amount of time to complete manually.
*   **Error-Prone Activities:** Processes where human error is likely to occur.
*   **Scheduled Operations:** Tasks that need to be executed at specific times or intervals.

### Insider Secrets 🤫

*   **Logging:** Use the `logging` module to track the execution of your scripts and identify potential issues.
*   **Error Handling:** Implement robust error handling to prevent your scripts from crashing unexpectedly. Use `try...except` blocks.
*   **Configuration Files:** Store configuration settings (e.g., API keys, file paths) in external configuration files for easy modification.
*   **Virtual Environments:** Use virtual environments to isolate your project dependencies and avoid conflicts.

### Debunking Myths 🚫

*   **Myth:** Automation is only for large enterprises.
    *   **Reality:** Automation can benefit individuals and small businesses as well.
*   **Myth:** You need to be a coding expert to automate tasks.
    *   **Reality:** With Python and the right libraries, you can automate many tasks with basic programming skills.
*   **Myth:** Automation will replace all jobs.
    *   **Reality:** Automation will likely change the nature of many jobs, but it will also create new opportunities.

### Call to Action! 🔥

Your mission, should you choose to accept it, is to automate one task in the next 24 hours. It could be as simple as renaming a batch of files, or as complex as generating a daily report. The key is to take action and apply what you've learned!

### Advanced Automation Project

Create a complete automation solution that solves a problem in a real-world scenario.

#### Project Ideas:

1.  **Automated social media poster:** Automatically posts content to social media platforms using API.
2.  **Automated data backup system:** Backs up important data to a remote server on a regular basis.
3.  **Automated lead scraper:** Scrapes lead data from websites and adds to CRM.

### A Spark of Creativity ✨

Imagine a world where you can focus on the creative and strategic aspects of your work, while Python handles the mundane and repetitive tasks. That's the power of automation. Embrace it, explore it, and let it free you to do what you do best!