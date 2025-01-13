"""XML-based tool argument parser.

This module provides functionality for parsing tool arguments from XML-like
input, with support for validation and error handling.
"""

from typing import Self

from loguru import logger
from pydantic import BaseModel, Field

from quantalogic.tools.tool import Tool
from quantalogic.xml_parser import ToleranceXMLParser


class ToolArguments(BaseModel):
    """Model for storing and validating tool arguments.

    This model provides a structured way to store and validate arguments
    extracted from XML input, ensuring they meet the tool's requirements.

    Attributes:
        arguments: Dictionary mapping argument names to their values.
    """

    arguments: dict[str, str] = Field(
        default_factory=dict, description="Dictionary mapping argument names to their values"
    )


class ToolParser:
    """Parser for extracting and validating tool arguments from XML input.

    This class handles the parsing of XML-like input to extract tool arguments,
    validates them against the tool's requirements, and provides error handling
    and logging.

    Attributes:
        tool: The tool instance containing argument specifications.
        xml_parser: Parser for handling XML-like input.
    """

    def __init__(self: Self, tool: Tool) -> None:
        """Initialize the parser with a tool instance.

        Args:
            tool: Tool instance containing argument specifications.
        """
        self.tool = tool
        self.xml_parser = ToleranceXMLParser()

    def parse(self: Self, xml_string: str) -> dict[str, str]:
        """Parse XML string and return validated tool arguments.

        Args:
            xml_string: The XML string containing tool arguments.

        Returns:
            A dictionary mapping argument names to their values.

        Raises:
            ValueError: If required arguments are missing or XML is invalid.
        """
        try:
            if not xml_string:
                error_msg = "Input text must be a non-empty string"
                logger.error(f"Error extracting XML elements: {error_msg}")
                raise ValueError(f"Error extracting XML elements: {error_msg}")

            if not xml_string.strip().startswith("<"):
                error_msg = "Failed to parse XML"
                logger.error(f"Error extracting XML elements: {error_msg}")
                raise ValueError(f"Error extracting XML elements: {error_msg}")

            # Parse XML and extract arguments, preserving CDATA content
            elements = self.xml_parser.extract_elements(xml_string, preserve_cdata=True)
            logger.debug(f"Extracted elements from XML: {elements}")

            arguments = self.tool.get_non_injectable_arguments()

            # Check for required arguments
            for arg in arguments:
                if arg.required and arg.name not in elements:
                    error_msg = f"argument {arg.name} not found"
                    logger.error(f"Error extracting XML elements: {error_msg}")
                    raise ValueError(f"Error extracting XML elements: {error_msg}")

            # Create and validate arguments dictionary
            argument_dict = {arg.name: elements.get(arg.name, "") for arg in arguments}

            # Validate using Pydantic model
            validated_args = ToolArguments(arguments=argument_dict)
            logger.debug(f"Successfully parsed arguments: {validated_args.arguments}")
            return validated_args.arguments

        except ValueError as e:
            if not str(e).startswith("Error extracting XML elements:"):
                error_msg = f"Error extracting XML elements: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            raise
