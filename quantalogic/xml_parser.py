"""XML parsing utilities for extracting and processing XML-like elements.

This module provides tools for parsing and extracting XML-like elements from text,
with support for handling malformed XML and CDATA sections.
"""

import html
import re
from collections import defaultdict

try:
    from typing import Self  # Python 3.11+
except ImportError:
    from typing_extensions import Self  # Python 3.10 compatibility

from loguru import logger
from pydantic import BaseModel, Field, model_validator


class XMLElement(BaseModel):
    """Represents a parsed XML element with its structural and content details.

    This model captures the essential information of an XML element,
    including its name, content, raw representation, and positional
    information within the original XML document.

    Attributes:
        name: The name of the XML element (tag name).
        content: The textual content of the XML element.
        raw: The complete raw string representation of the XML element.
        start_pos: Starting character position in the original document.
        end_pos: Ending character position in the original document.
        cdata_sections: List of CDATA sections within the element.
    """

    name: str = Field(..., description="The name of the XML element (tag name)")
    content: str = Field(..., description="The textual content of the XML element")
    raw: str = Field(..., description="The complete raw string representation")
    start_pos: int = Field(..., description="Starting character position", ge=0)
    end_pos: int = Field(..., description="Ending character position", gt=0)
    cdata_sections: list[str] = Field(default_factory=list, description="List of CDATA sections within the element")

    @model_validator(mode="after")
    def validate_positions(self) -> Self:
        """Validate that end_pos is greater than start_pos."""
        if self.end_pos <= self.start_pos:
            raise ValueError("end_pos must be greater than start_pos")
        return self


class ToleranceXMLParser:
    """A flexible XML-like parser for malformed and non-standard XML elements.

    This parser extracts XML-like elements from text, supporting various
    edge cases such as incomplete tags and CDATA sections.
    """

    # Default mappings for element name normalization
    DEFAULT_NAME_MAP = {"o": "output", "i": "input", "opt": "optional"}

    def __init__(self: Self) -> None:
        """Initialize the parser with regex patterns for matching XML-like elements."""
        # Pattern for matching individual XML elements with better whitespace handling
        self.element_pattern = re.compile(r"<\s*([^/>]+?)\s*>(.*?)(?:</\s*\1\s*>|<\s*\1\s*>)", re.DOTALL)
        # Pattern for matching CDATA sections
        self.cdata_pattern = re.compile(r"<!\[CDATA\[(.*?)]]>", re.DOTALL)
        logger.debug("Initialized ToleranceXMLParser with regex patterns")

    def _validate_input(self, text: str) -> None:
        """Validate input text before processing.

        Args:
            text: Input text to validate.

        Raises:
            ValueError: If input text is invalid.
        """
        if not text or not isinstance(text, str):
            raise ValueError("Input text must be a non-empty string")
        if len(text.strip()) == 0:
            raise ValueError("Input text cannot be whitespace only")

    def _extract_and_remove_cdata(self: Self, content: str, preserve_cdata: bool = False) -> tuple[str, list[str]]:
        """Extract CDATA sections from content.

        Args:
            content: Input text to extract CDATA sections from.
            preserve_cdata: If True, preserve CDATA content in place.
                          If False, remove CDATA sections and return them separately.

        Returns:
            A tuple containing:
                - The original content with CDATA sections handled
                - List of extracted CDATA contents
        """
        cdata_sections: list[str] = []

        def replace_cdata(match: re.Match[str]) -> str:
            cdata_content = match.group(1)
            cdata_sections.append(cdata_content)
            return cdata_content if preserve_cdata else match.group(0)

        # Extract CDATA sections but keep the original content intact
        cleaned_content = self.cdata_pattern.sub(replace_cdata, content)
        return cleaned_content, cdata_sections

    def _clean_content(self: Self, content: str) -> str:
        """Clean XML content while preserving exact original formatting.

        Args:
            content: Raw XML content to clean.

        Returns:
            Content with unescaped HTML entities, preserving all original formatting.
        """
        # Only unescape HTML entities, preserve everything else exactly as is
        return html.unescape(content)

    def _map_element_name(self: Self, name: str) -> str:
        """Map element names to their canonical form.

        Args:
            name: Raw element name from XML.

        Returns:
            Canonical element name.
        """
        return self.DEFAULT_NAME_MAP.get(name.strip(), name.strip())

    def _build_element_pattern(self, element_name: str) -> re.Pattern[str]:
        """Build regex pattern for finding specific XML elements.

        Args:
            element_name: Name of the element to match.

        Returns:
            Compiled regex pattern for matching the element.
        """
        non_cdata = r"(?:(?!<!\[CDATA\[|]]>).)*?"
        cdata_section = r"(?:<!\[CDATA\[.*?]]>)?"
        content_pattern = f"({non_cdata}{cdata_section}{non_cdata})"
        closing_pattern = "(?:</\1>|<\1>)"

        return re.compile(f"<{element_name}>{content_pattern}{closing_pattern}", re.DOTALL)

    def _find_all_elements(self, text: str) -> list[tuple[str, str]]:
        """Find all XML elements in text.

        Args:
            text: Input text to search.

        Returns:
            List of tuples containing element names and their content.
        """
        return [(match.group(1), match.group(2) or "") for match in self.element_pattern.finditer(text)]

    def _process_element_content(self, content: str, preserve_cdata: bool) -> str:
        """Process content of a single element.

        Args:
            content: Raw element content.
            preserve_cdata: Whether to preserve CDATA sections.

        Returns:
            Processed content string.
        """
        content, cdata_sections = self._extract_and_remove_cdata(content, preserve_cdata)
        content = self._clean_content(content)

        # If content is empty but we have CDATA sections and we're not preserving them
        if not content.strip() and cdata_sections and not preserve_cdata:
            return cdata_sections[0]
        return content

    def _process_elements(self, elements: list[tuple[str, str]], preserve_cdata: bool) -> dict[str, str]:
        """Process found elements and handle CDATA sections.

        Args:
            elements: List of element name and content tuples.
            preserve_cdata: Whether to preserve CDATA sections.

        Returns:
            Dictionary mapping element names to their processed content.
        """
        result: dict[str, str] = defaultdict(str)
        for name, content in elements:
            name = self._map_element_name(name)
            result[name] = self._process_element_content(content, preserve_cdata)

            # Handle nested elements
            nested_elements = self._find_all_elements(content)
            nested_results = self._process_elements(nested_elements, preserve_cdata)
            result.update(nested_results)

        return dict(result)

    def _extract_element_content(self: Self, text: str, preserve_cdata: bool = False) -> dict[str, str]:
        """Extract content from nested XML elements.

        Args:
            text: Input text containing XML elements.
            preserve_cdata: If True, preserve CDATA content in place.

        Returns:
            Dictionary mapping element names to their content values.
        """
        elements = self._find_all_elements(text)
        return self._process_elements(elements, preserve_cdata)

    def extract_elements(
        self: Self,
        text: str,
        element_names: list[str] | None = None,
        preserve_cdata: bool = False,
    ) -> dict[str, str]:
        """Extract XML-like elements from text, grouped by element names.

        Args:
            text: Input text containing XML-like elements.
            element_names: Optional list of element names to extract.
                If None, extracts all elements.
            preserve_cdata: If True, preserve CDATA content in place.
                          If False, remove CDATA sections.

        Returns:
            Dictionary mapping element names to their content values.
            For elements with multiple instances, only the last value is kept.

        Raises:
            ValueError: If the input text is invalid or contains malformed XML.
        """
        try:
            self._validate_input(text)
            logger.debug(f"Extracting elements: {element_names or 'all'}")

            # Extract all elements and their content
            elements = self._extract_element_content(text, preserve_cdata)

            # Filter elements if specific names were requested
            if element_names is not None:
                elements = {name: content for name, content in elements.items() if name in element_names}

            logger.debug(f"Successfully extracted {len(elements)} elements")
            return elements

        except Exception as e:
            error_msg = f"Error extracting XML elements: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def find_elements(self: Self, text: str, element_name: str) -> list[XMLElement]:
        """Find all instances of a specific XML element in the text.

        Args:
            text: Input text to search for elements.
            element_name: Name of the element to find.

        Returns:
            List of XMLElement instances for each found element.

        Raises:
            ValueError: If the input text is invalid or contains malformed XML.
        """
        try:
            self._validate_input(text)
            elements: list[XMLElement] = []
            pattern = self._build_element_pattern(element_name)

            for match in pattern.finditer(text):
                content = match.group(1)
                cleaned_content, cdata_sections = self._extract_and_remove_cdata(content)
                cleaned_content = self._clean_content(cleaned_content)

                element = XMLElement(
                    name=element_name,
                    content=cleaned_content,
                    raw=match.group(0),
                    start_pos=match.start(),
                    end_pos=match.end(),
                    cdata_sections=cdata_sections,
                )
                elements.append(element)

            return elements

        except Exception as e:
            error_msg = f"Error extracting XML elements: {str(e)}"
            error_msg = error_msg + f"\n{text}\n"
            logger.error(error_msg)
            raise ValueError(error_msg)


if __name__ == "__main__":
    xml_content = """
<action>
    <task_complete>
        <answer>Hello</answer>
    </task_complete>
</action>
"""

    parser = ToleranceXMLParser()
    parsed_values = parser.extract_elements(xml_content)
    print(parsed_values)
    if "action" in parsed_values:
        print(parsed_values["action"])
    action = parser.extract_elements(text=xml_content, element_names=["action"])
    print(action["action"])
