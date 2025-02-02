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
from pydantic import Field, model_validator

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.utils.python_interpreter import interpret_code

# Configure Loguru
logger.remove()  # Remove any default handler
logger.add(lambda msg: print(msg, end=""), level="DEBUG")


class SafePythonInterpreterTool(Tool):
    """
    A tool to safely execute Python code while only allowing a specific set
    of modules as defined in `allowed_modules`.
    """
    # Allowed modules must be provided during initialization.
    allowed_modules: List[str] = Field(
        ...,
        description="List of Python module names allowed for code execution."
    )
    # Additional fields to support the Tool API.
    code: str | None = None  # Provided at runtime via kwargs.
    time_limit: int = Field(
        default=60,
        description="Maximum execution time (in seconds) for running the Python code."
    )
    # Define tool arguments so that they appear in the tool's markdown description.
    arguments: list[ToolArgument] = [
        ToolArgument(
            name="code",
            arg_type="string",
            description="The Python source code to be executed.",
            required=True,
            example="""
import math
import numpy as np

def transform_array(x):
    sqrt_vals = [math.sqrt(val) for val in x]
    sin_vals = [math.sin(val) for val in sqrt_vals]
    return sin_vals

array_input = np.array([1, 4, 9, 16, 25])
result = transform_array(array_input)
result
            """.strip()
        ),
        ToolArgument(
            name="time_limit",
            arg_type="int",
            description="The execution timeout (in seconds).",
            required=False,
            default="60",
            example="60"
        )
    ]
    name: Literal["safe_python_interpreter"] = "safe_python_interpreter"
    description: str | None = None

    @model_validator(mode="after")
    def set_description(self) -> Self:
        desc = (
            f"Safe Python interpreter tool. It interprets Python code with a restricted set "
            f"of allowed modules. Only the following modules are available: {', '.join(self.allowed_modules)}. "
            "This tool prevents usage of any modules or functions outside those allowed."
        )
        # Bypass Pydantic's validation assignment mechanism.
        object.__setattr__(self, "description", desc)
        logger.debug(f"SafePythonInterpreterTool initialized with modules: {self.allowed_modules}")
        logger.debug(f"Tool description: {desc}")
        return self

    def execute(self, **kwargs) -> str:
        """
        Executes the provided Python code using the `interpret_code` function with a restricted
        set of allowed modules. This method uses keyword arguments to support the Tool API.

        Expected kwargs:
            code (str): The Python source code to be executed.
            time_limit (int, optional): Maximum execution time in seconds (default is 60).

        Raises:
            ValueError: If the provided code is empty.
            RuntimeError: If the code execution exceeds the defined time limit.
            Exception: For any errors during code execution.

        Returns:
            str: The string representation of the result of the executed code.
        """
        code = kwargs.get("code")
        time_limit = kwargs.get("time_limit", self.time_limit)

        if not code or not code.strip():
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
            except concurrent.futures.TimeoutError:
                error_msg = f"Code execution exceeded time limit of {time_limit} seconds."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            except Exception as e:
                logger.error(f"Execution failed: {e}")
                raise

        return str(result)


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
        # Call execute with keyword arguments as expected.
        output = interpreter_tool.execute(code=code, time_limit=60)
        print("Interpreter Output:")
        print(output)
    except Exception as e:
        print(f"An error occurred during interpretation: {e}")