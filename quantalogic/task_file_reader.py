"""Module for reading task content from files or URLs."""

import requests


def get_task_from_file(source: str) -> str:
    """Get task content from specified file path or URL.

    Args:
        source (str): File path or URL to read task content from

    Returns:
        str: Stripped task content from the file or URL

    Raises:
        FileNotFoundError: If the local file does not exist
        PermissionError: If there are permission issues reading the file
        requests.exceptions.RequestException: If there are issues retrieving URL content
        Exception: For any other unexpected errors
    """
    try:
        # Check if source is a URL
        if source.startswith(("http://", "https://")):
            response = requests.get(source, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.text.strip()

        # If not a URL, treat as a local file path
        with open(source, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File '{source}' not found.")
    except PermissionError:
        raise PermissionError(f"Error: Permission denied when reading '{source}'.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error retrieving URL content: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error: {e}")
