from typing import Union


def get_quantalogic_rules_file_content() -> Union[str, None]:
    """
    Reads the content of the .quantalogicrules file in the current directory.

    Returns:
        Union[str, None]: The content of the .quantalogicrules file if it exists.
                          Returns None if the file does not exist.
                          Raises RuntimeError if an error occurs while reading the file.
    """
    try:
        with open(".quantalogicrules") as file:
            return file.read()
    except FileNotFoundError:
        return None
    except Exception as e:
        raise RuntimeError(f"Error reading .quantalogicrules file: {e}")
