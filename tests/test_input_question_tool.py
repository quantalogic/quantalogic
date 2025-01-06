"""Tests for the InputQuestionTool."""

from unittest.mock import patch
import pytest

from quantalogic.tools.input_question_tool import InputQuestionTool


def test_input_question_tool_initialization():
    """Test that the InputQuestionTool can be initialized correctly."""
    tool = InputQuestionTool()
    assert tool.name == "input_question"
    assert tool.description == "Prompts the user with a question and captures their input."
    assert len(tool.arguments) == 2


@patch("rich.prompt.Prompt.ask")
def test_input_question_tool_execute(mock_prompt_ask):
    """Test the execute method of InputQuestionTool."""
    # Arrange
    tool = InputQuestionTool()
    mock_prompt_ask.return_value = "Test Answer"
    question = "What is your test question?"

    # Act
    result = tool.execute(question)

    # Assert
    mock_prompt_ask.assert_called_once_with(question, default=None)
    assert result == "Test Answer"


@patch("rich.prompt.Prompt.ask")
def test_input_question_tool_with_default(mock_prompt_ask):
    """Test the execute method with a default value."""
    # Arrange
    tool = InputQuestionTool()
    mock_prompt_ask.return_value = "Default Value"
    question = "What is your test question?"
    default = "Default Value"

    # Act
    result = tool.execute(question, default)

    # Assert
    mock_prompt_ask.assert_called_once_with(question, default=default)
    assert result == "Default Value"


def test_input_question_tool_markdown_generation():
    """Test that the tool can generate markdown documentation."""
    tool = InputQuestionTool()
    markdown = tool.to_markdown()

    # Assert basic markdown generation
    assert "## input_question" in markdown
    assert "Prompts the user with a question and captures their input" in markdown
    assert "### Arguments" in markdown
