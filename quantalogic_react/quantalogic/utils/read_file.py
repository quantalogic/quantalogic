"""Reads the content of a file and returns it as a string."""

import os


def read_file(file_path: str, max_size: int = 10 * 1024 * 1024) -> str:
    """Reads the content of a file and returns it as a string.

    This function performs the following steps:
    1. Expands the tilde (~) in the file path to the user's home directory.
    2. Converts a relative path to an absolute path.
    3. Checks the file size before reading to ensure it is not too large.
    4. Reads the file content and returns it as a string.
    5. Handles common file operation errors such as FileNotFoundError, PermissionError, and OSError.

    Parameters:
    file_path (str): The path to the file to be read.

    Returns:
    str: The content of the file as a string.

    Raises:
    FileNotFoundError: If the file does not exist.
    PermissionError: If the file cannot be read due to permission issues.
    OSError: If the file size is too large or other OS-related errors occur.
    """
    try:
        # Expand tilde to user's home directory
        expanded_path = os.path.expanduser(file_path)

        # Convert relative path to absolute path
        absolute_path = os.path.abspath(expanded_path)

        # Check if the file exists
        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"The file '{absolute_path}' does not exist.")

        # Check file size before reading
        file_size = os.path.getsize(absolute_path)
        if file_size > max_size:
            raise OSError(f"File size ({file_size} bytes) exceeds the maximum allowed size ({max_size} bytes).")

        # Read the file content
        with open(absolute_path, encoding="utf-8") as file:
            content = file.read()

        return content

    except FileNotFoundError:
        raise FileNotFoundError(f"The file '{absolute_path}' does not exist.")
    except PermissionError:
        raise PermissionError(f"Permission denied: Unable to read the file '{absolute_path}'.")
    except OSError as e:
        raise OSError(f"An error occurred while reading the file: {e}")
