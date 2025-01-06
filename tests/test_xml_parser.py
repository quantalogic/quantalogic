"""Comprehensive test suite for the XML parser module."""

from typing import Any
import re
import pytest
from loguru import logger
from pydantic import ValidationError

from quantalogic.xml_parser import ToleranceXMLParser, XMLElement


@pytest.fixture
def parser() -> ToleranceXMLParser:
    """Fixture to create a ToleranceXMLParser instance for each test."""
    return ToleranceXMLParser()


def test_xml_element_initialization():
    """Test XMLElement initialization with default and custom parameters."""
    # Test with all parameters
    element = XMLElement(
        name="test",
        content="test content",
        raw="<test>test content</test>",
        start_pos=0,
        end_pos=25,
        cdata_sections=["cdata content"],
    )
    assert element.name == "test"
    assert element.content == "test content"
    assert element.raw == "<test>test content</test>"
    assert element.start_pos == 0
    assert element.end_pos == 25
    assert element.cdata_sections == ["cdata content"]

    # Test with default cdata_sections
    element_default = XMLElement(
        name="test", content="test content", raw="<test>test content</test>", start_pos=0, end_pos=25
    )
    assert element_default.cdata_sections == []


def test_xml_element_validation():
    """Test XMLElement validation with Pydantic v2."""
    # Test valid initialization
    element = XMLElement(
        name="test",
        content="test content",
        raw="<test>test content</test>",
        start_pos=0,
        end_pos=25,
        cdata_sections=["cdata content"],
    )
    assert isinstance(element.model_dump(), dict)

    # Test invalid types
    with pytest.raises(ValidationError):
        XMLElement(
            name=123,  # type: ignore
            content="test content",
            raw="<test>test content</test>",
            start_pos=0,
            end_pos=25,
        )

    # Test invalid position values
    with pytest.raises(ValidationError):
        XMLElement(
            name="test",
            content="test content",
            raw="<test>test content</test>",
            start_pos=10,
            end_pos=5,  # Invalid: end_pos <= start_pos
        )


def test_extract_and_remove_cdata(parser: ToleranceXMLParser):
    """Test the _extract_and_remove_cdata method."""
    # Test with CDATA section
    content = "Some text <![CDATA[CDATA content]]> more text <![CDATA[Another CDATA]]>"
    cleaned_content, cdata_sections = parser._extract_and_remove_cdata(content)

    # Normalize whitespace for comparison
    assert re.sub(r"\s+", " ", cleaned_content).strip() == "Some text more text"
    assert cdata_sections == ["CDATA content", "Another CDATA"]

    # Test without CDATA section
    content_no_cdata = "Some text without CDATA"
    cleaned_content, cdata_sections = parser._extract_and_remove_cdata(content_no_cdata)

    assert cleaned_content == "Some text without CDATA"
    assert cdata_sections == []


def test_extract_elements(parser: ToleranceXMLParser):
    """Test extracting XML-like elements from text."""
    # Test with multiple elements and CDATA
    text = """
    <thinking>Some thought</thinking>
    <attempt_reply>First reply</attempt_reply>
    <thinking>Another thought</thinking>
    <attempt_reply><![CDATA[Reply with CDATA]]></attempt_reply>
    """

    # Extract all elements
    elements = parser.extract_elements(text)
    assert len(elements) == 2
    assert "thinking" in elements
    assert "attempt_reply" in elements
    assert elements["thinking"] == "Another thought"
    assert elements["attempt_reply"] == "Reply with CDATA"

    # Extract specific elements
    specific_elements = parser.extract_elements(text, ["thinking"])
    assert len(specific_elements) == 1
    assert "thinking" in specific_elements
    assert specific_elements["thinking"] == "Another thought"


def test_extract_elements_with_logging(parser: ToleranceXMLParser, caplog: Any):
    """Test that logging is properly implemented."""
    # Ensure we capture loguru output
    logger.remove()
    logger.add(lambda msg: caplog.records.append(msg), level="DEBUG")

    text = "<element>content</element>"
    _ = parser.extract_elements(text)

    # Check for log messages in stderr output
    debug_messages = [str(record) for record in caplog.records]
    assert any("Extracting elements: all" in msg for msg in debug_messages)
    assert any("Successfully extracted 1 elements" in msg for msg in debug_messages)


def test_extract_elements_error_handling(parser: ToleranceXMLParser):
    """Test error handling in extract_elements method."""
    # Test with None input
    with pytest.raises(ValueError) as exc_info:
        parser.extract_elements(None)  # type: ignore
    assert "Input text must be a non-empty string" in str(exc_info.value)

    # Test with empty string
    with pytest.raises(ValueError) as exc_info:
        parser.extract_elements("")
    assert "Input text must be a non-empty string" in str(exc_info.value)


def test_malformed_xml(parser: ToleranceXMLParser):
    """Test parsing malformed or incomplete XML-like elements."""
    # Test with malformed tags
    text_malformed = """
    <incomplete_tag>Some content</incomplete_tag>
    <another_tag>More content</another_tag>
    """

    elements = parser.extract_elements(text_malformed)
    assert len(elements) == 2
    assert elements["incomplete_tag"] == "Some content"
    assert elements["another_tag"] == "More content"


def test_xml_element_attributes():
    """Test XMLElement attributes and their properties."""
    element = XMLElement(
        name="test",
        content="test content",
        raw="<test>test content</test>",
        start_pos=10,
        end_pos=35,
        cdata_sections=["cdata section"],
    )

    assert element.name == "test"
    assert element.content == "test content"
    assert element.raw == "<test>test content</test>"
    assert element.start_pos == 10
    assert element.end_pos == 35
    assert element.cdata_sections == ["cdata section"]


def test_edge_cases(parser: ToleranceXMLParser):
    """Test various edge cases in XML parsing."""
    # Empty text
    with pytest.raises(ValueError):
        parser.extract_elements("")

    # Text with no XML-like elements
    text = "Plain text without XML elements"
    elements = parser.extract_elements(text)
    assert len(elements) == 0

    # Text with nested elements
    nested_text = "<outer><inner>Nested content</inner></outer>"
    elements = parser.extract_elements(nested_text)
    assert len(elements) == 2
    assert "inner" in elements
    assert "outer" in elements
    assert elements["inner"] == "Nested content"


def test_cdata_extraction(parser: ToleranceXMLParser):
    """Test CDATA section extraction."""
    text_with_cdata = """
    <element>
        Some text <![CDATA[CDATA content 1]]> more text
        <![CDATA[CDATA content 2]]>
    </element>
    """

    elements = parser.extract_elements(text_with_cdata)
    assert len(elements) == 1
    assert "element" in elements
    assert elements["element"].strip() == "Some text more text"


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("<element>simple</element>", {"element": "simple"}),
        ("<tag><![CDATA[data]]></tag>", {"tag": "data"}),
    ],
)
def test_parametrized_parsing(parser: ToleranceXMLParser, test_input: str, expected: dict[str, str]):
    """Test various XML parsing scenarios using parametrize."""
    result = parser.extract_elements(test_input)
    assert result == expected
