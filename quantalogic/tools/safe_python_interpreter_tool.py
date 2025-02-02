"""
Module: safe_python_interpreter_tool.py

Description:
    A tool to safely interpret Python code using a restricted set of allowed modules.
    This version uses Pydantic V2 for configuration and validation and Loguru for logging.
    The allowed modules are provided during initialization, and the tool's description
    is dynamically generated based on that list.
"""

from __future__ import annotations

import concurrent.futures
from typing import Any, List, Literal, Self

from loguru import logger
from pydantic import BaseModel, Field, model_validator

# Import the safe interpreter function.
from quantalogic.utils.python_interpreter import interpret_code

# Configure Loguru (if needed, you can set up format, rotation, etc.)
logger.remove()  # Remove any default handler
logger.add(lambda msg: print(msg, end=""), level="DEBUG")


class SafePythonInterpreterTool(BaseModel):
    """
    A tool to safely execute Python code while only allowing a specific set
    of modules as defined in `allowed_modules`.
    """
    allowed_modules: List[str] = Field(
        ...,
        description="List of Python module names allowed for code execution."
    )
    name: Literal["safe_python_interpreter"] = "safe_python_interpreter"
    description: str | None = None

    @model_validator(mode="after")
    def set_description(self) -> Self:
        desc = (
            f"Safe Python interpreter tool. It interprets Python code with a restricted set "
            f"of allowed modules. Only the following modules are available: {', '.join(self.allowed_modules)}. "
            "This tool prevents usage of any modules or functions outside those allowed."
        )
        self.description = desc
        logger.debug(f"SafePythonInterpreterTool initialized with modules: {self.allowed_modules}")
        logger.debug(f"Tool description: {self.description}")
        return self

    def execute(self, code: str, time_limit: int = 60) -> Any:
        """
        Executes the provided Python code using the `interpret_code` function with a restricted
        set of allowed modules.

        Args:
            code (str): The Python source code to be executed.
            time_limit (int, optional): Maximum execution time in seconds. Defaults to 60.

        Returns:
            Any: The result of the executed code.

        Raises:
            ValueError: If the provided code is empty.
            RuntimeError: If code execution exceeds the defined time limit.
            Exception: For any errors during code execution.
        """
        if not code.strip():
            error_msg = "The provided Python code is empty."
            logger.error(error_msg)
            raise ValueError(error_msg)

        def run_interpreter() -> Any:
            logger.debug("Starting interpretation of code.")
            try:
                result = interpret_code(code, self.allowed_modules)
                logger.debug("Code interpreted successfully.")
                return result
            except Exception as e:
                logger.error(f"Error during interpretation: {e}")
                raise

        # Enforce a timeout using ThreadPoolExecutor.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_interpreter)
            try:
                result = future.result(timeout=time_limit)
                return result
            except concurrent.futures.TimeoutError:
                error_msg = f"Code execution exceeded time limit of {time_limit} seconds."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            except Exception as e:
                logger.error(f"Execution failed: {e}")
                raise


# ------------------------------------------
# Example usage:
# ------------------------------------------
if __name__ == "__main__":
    # Define the allowed modules. For this example, we allow only 'math' and 'numpy'.
    allowed_modules = ["math", "numpy"]

    # Initialize the tool using Pydantic.
    interpreter_tool = SafePythonInterpreterTool(allowed_modules=allowed_modules)

    # Print tool description.
    print("Tool Description:")
    print(interpreter_tool.description)

    # Define Python code that uses both allowed modules.
    code = """
import math
import numpy as np

def transform_array(x):
    # Apply square root to each element of the array
    sqrt_vals = [math.sqrt(val) for val in x]
    # Apply sine to each resulting value
    sin_vals = [math.sin(val) for val in sqrt_vals]
    return sin_vals

array_input = np.array([1, 4, 9, 16, 25])
result = transform_array(array_input)
result
    """

    try:
        output = interpreter_tool.execute(code, time_limit=60)
        print("Interpreter Output:")
        print(output)
    except Exception as e:
        print(f"An error occurred during interpretation: {e}")