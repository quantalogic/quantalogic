"""Test suite for the XML tool parser module."""

from typing import Any

import pytest
from loguru import logger
from pydantic import BaseModel, ValidationError

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.xml_tool_parser import ToolArguments, ToolParser


class MockTool(Tool):
    """Mock tool for testing."""

    def __init__(self: Any) -> None:
        """Initialize mock tool."""
        super().__init__(
            name="mock_tool",
            description="Mock tool for testing",
            arguments=[
                ToolArgument(
                    name="input",
                    arg_type="string",
                    description="Input argument",
                    required=True
                ),
                ToolArgument(
                    name="output",
                    arg_type="string", 
                    description="Output argument",
                    required=True
                ),
                ToolArgument(
                    name="optional",
                    arg_type="string",
                    description="Optional argument",
                    required=False
                )
            ]
        )


@pytest.fixture
def mock_tool() -> MockTool:
    """Fixture to create a mock tool for testing."""
    return MockTool()


@pytest.fixture
def tool_parser(mock_tool: MockTool) -> ToolParser:
    """Fixture to create a ToolParser instance for testing."""
    return ToolParser(mock_tool)


@pytest.fixture(autouse=True)
def setup_loguru(caplog: Any):
    """Configure loguru to work with pytest's caplog fixture."""
    import logging
    import sys
    from loguru import logger

    # Remove any existing handlers
    logger.remove()
    
    # Add a handler that writes to stderr
    logger.add(
        sys.stderr,
        format="{time} | {level} | {message}",
        level="DEBUG",
        backtrace=True,
        diagnose=True,
    )
    
    # Add a handler that writes to caplog
    logger.add(
        lambda msg: caplog.handler.emit(
            logging.LogRecord(
                "loguru", logging.INFO, "", 0, msg, (), None
            )
        ),
        format="{message}",
    )


def test_tool_parser_initialization(mock_tool: MockTool):
    """Test ToolParser initialization."""
    parser = ToolParser(mock_tool)
    assert parser.tool == mock_tool


def test_tool_arguments_model():
    """Test ToolArguments model initialization and validation."""
    # Test valid initialization
    args = ToolArguments(arguments={"key": "value"})
    assert args.arguments == {"key": "value"}

    # Test empty arguments
    args = ToolArguments()
    assert args.arguments == {}


def test_tool_parser_successful_parsing(tool_parser: ToolParser):
    """Test successful parsing of XML with all required arguments."""
    xml = '''
    <root>
        <input>test input</input>
        <output>test output</output>
        <optional>test optional</optional>
    </root>
    '''
    result = tool_parser.parse(xml)
    assert result["input"] == "test input"
    assert result["output"] == "test output"
    assert result["optional"] == "test optional"


def test_tool_parser_missing_argument(tool_parser: ToolParser):
    """Test parsing XML with missing required argument."""
    xml = '''
    <root>
        <input>test input</input>
    </root>
    '''
    with pytest.raises(ValueError) as exc_info:
        tool_parser.parse(xml)
    assert "argument output not found" in str(exc_info.value)


def test_tool_parser_custom_arguments(tool_parser: ToolParser):
    """Test parsing XML with custom argument structure."""
    xml = '''
    <arguments>
        <input>custom input</input>
        <output>custom output</output>
    </arguments>
    '''
    result = tool_parser.parse(xml)
    assert result["input"] == "custom input"
    assert result["output"] == "custom output"


def test_tool_parser_empty_xml(tool_parser: ToolParser):
    """Test parsing empty XML string."""
    with pytest.raises(ValueError) as exc_info:
        tool_parser.parse("")
    assert "Input text must be a non-empty string" in str(exc_info.value)


def test_tool_parser_whitespace_handling(tool_parser: ToolParser):
    """Test handling of whitespace in XML content."""
    xml = '''
    <root>
        <input>
            test input
        </input>
        <output>
            test output
        </output>
    </root>
    '''
    result = tool_parser.parse(xml)
    assert result["input"].strip() == "test input"
    assert result["output"].strip() == "test output"


def test_tool_parser_special_characters(tool_parser: ToolParser):
    """Test handling of special characters in XML content."""
    xml = '''
    <root>
        <input>test &amp; input</input>
        <output>test &lt; output &gt;</output>
    </root>
    '''
    result = tool_parser.parse(xml)
    assert result["input"] == "test & input"
    assert result["output"] == "test < output >"


def test_tool_parser_with_cdata(tool_parser: ToolParser):
    """Test parsing XML with CDATA sections."""
    xml = '''
    <root>
        <input><![CDATA[test input with <special> chars]]></input>
        <output><![CDATA[test output with & symbols]]></output>
    </root>
    '''
    result = tool_parser.parse(xml)
    assert result["input"] == "test input with <special> chars"
    assert result["output"] == "test output with & symbols"


def test_tool_parser_error_logging(tool_parser: ToolParser, caplog: Any):
    """Test error logging during XML parsing."""
    caplog.set_level("ERROR")
    
    with pytest.raises(ValueError):
        tool_parser.parse("<invalid>xml")
    
    # Check if any log record contains the error message
    for record in caplog.records:
        print(f"Log record: {record.message}")
        
    assert any(
        "Error extracting XML elements" in record.message
        for record in caplog.records
    ), "Expected error message not found in logs"


@pytest.mark.parametrize("xml,error_msg", [
    ("<root></root>", "argument input not found"),
    ("<root><input>test</input></root>", "argument output not found"),
    ("invalid xml", "Failed to parse XML"),
])
def test_tool_parser_error_cases(
    tool_parser: ToolParser,
    xml: str,
    error_msg: str
):
    """Test various error cases in XML parsing."""
    with pytest.raises(ValueError) as exc_info:
        tool_parser.parse(xml)
    assert error_msg in str(exc_info.value)
