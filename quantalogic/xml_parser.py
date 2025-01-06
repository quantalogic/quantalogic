"""XML parsing utilities for extracting and processing XML-like elements.

This module provides tools for parsing and extracting XML-like elements from text,
with support for handling malformed XML and CDATA sections.
"""

import html
import re
from collections import defaultdict
from typing import Self

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

    def __init__(self: Self) -> None:
        """Initialize the parser with regex patterns for matching XML-like elements."""
        # Pattern for matching individual XML elements, including malformed tags
        # Modified to be more lenient with content and preserve exact formatting
        self.element_pattern = re.compile(r"<([^/>]+?)>(.*?)(?:</\1>|<\1>)", re.DOTALL)
        # Pattern for matching CDATA sections
        self.cdata_pattern = re.compile(r"<!\[CDATA\[(.*?)]]>", re.DOTALL)
        logger.debug("Initialized ToleranceXMLParser with regex patterns")

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
        # Map common element name variations
        name_map = {"o": "output", "i": "input", "opt": "optional"}
        return name_map.get(name.strip(), name.strip())

    def _extract_element_content(self: Self, text: str, preserve_cdata: bool = False) -> dict[str, str]:
        """Extract content from nested XML elements.

        Args:
            text: Input text containing XML elements.
            preserve_cdata: If True, preserve CDATA content in place.

        Returns:
            Dictionary mapping element names to their content values.
        """
        elements: dict[str, str] = defaultdict(str)

        # Process each match
        for match in self.element_pattern.finditer(text):
            name = match.group(1)
            content = match.group(2) or ""

            # Map element name to canonical form
            name = self._map_element_name(name)

            # Extract and handle CDATA sections
            content, cdata_sections = self._extract_and_remove_cdata(content, preserve_cdata)

            # Clean and normalize content
            content = self._clean_content(content)

            # If the content is empty but we have CDATA sections and we're
            # not preserving them
            if not content.strip() and cdata_sections and not preserve_cdata:
                content = cdata_sections[0]

            # Store the element content
            elements[name] = content

            # Extract nested elements from the content
            nested_elements = self._extract_element_content(content, preserve_cdata)
            elements.update(nested_elements)

        return dict(elements)  # Convert defaultdict to regular dict

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
            if not text or not isinstance(text, str):
                raise ValueError("Input text must be a non-empty string")

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
            if not text or not isinstance(text, str):
                raise ValueError("Input text must be a non-empty string")

            elements: list[XMLElement] = []
            pattern = re.compile(
                f"<{element_name}>"
                r"((?:(?!<!\[CDATA\[|]]>).)*?"
                r"(?:<!\[CDATA\[.*?]]>)?"
                r"(?:(?!<!\[CDATA\[|]]>).)*?)"
                f"(?:</\1>|<\1>)",
                re.DOTALL,
            )

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
            logger.error(error_msg)
            raise ValueError(error_msg)
