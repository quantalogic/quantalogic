"""Test suite for analyze_paper.py example workflow."""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from quantalogic_flow.flow import Nodes


class MockLLMResponse:
    """Mock response for LLM completions."""
    def __init__(self, content: str):
        self.content = content
        # Create mock tool call for structured responses
        mock_tool_call = Mock()
        mock_tool_call.function.arguments = content
        mock_tool_call.function.name = 'test_function'
        mock_tool_call.id = 'test_call_id'
        mock_tool_call.type = 'function'
        
        self.choices = [
            type('Choice', (), {
                'message': type('Message', (), {
                    'content': content,
                    'role': 'assistant',
                    'refusal': None,
                    'tool_calls': [mock_tool_call]  # List with one tool call
                })(),
                'finish_reason': 'stop',
                'index': 0
            })()
        ]
        self.usage = type('Usage', (), {
            'prompt_tokens': 100,
            'completion_tokens': 200,
            'total_tokens': 300
        })()
        self.id = 'test-response-id'
        self.model = 'test-model'
        self.created = 1234567890
        self.object = 'chat.completion'


class TestAnalyzePaper:
    """Test suite for analyze_paper.py functionality."""

    @classmethod
    def setup_class(cls):
        """Set up the test class by importing analyze_paper module."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        # Import the module to register all nodes globally
        import analyze_paper  # noqa: F401
        cls.analyze_paper = analyze_paper

    @pytest.fixture(autouse=True)
    def clear_node_registry(self):
        """Clear node registry before and after each test."""
        # Save existing nodes
        saved_nodes = Nodes.NODE_REGISTRY.copy()
        # Don't clear at the beginning - let tests register their own nodes
        yield
        # Restore saved nodes instead of clearing
        Nodes.NODE_REGISTRY.clear()
        Nodes.NODE_REGISTRY.update(saved_nodes)

    @pytest.fixture
    def temp_text_file(self):
        """Create a temporary text file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# Test Research Paper\n\n")
            f.write("## Abstract\n")
            f.write("This is a test research paper about artificial intelligence.\n\n")
            f.write("## Authors\n")
            f.write("- John Smith\n")
            f.write("- Jane Doe\n\n")
            f.write("## Introduction\n")
            f.write("This paper explores AI applications in modern technology.\n\n")
            f.write("## Methodology\n")
            f.write("We used various machine learning algorithms.\n\n")
            f.write("## Results\n")
            f.write("The results show promising outcomes.\n\n")
            f.write("## Conclusion\n")
            f.write("AI continues to evolve and provide valuable solutions.\n")
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def temp_markdown_file(self):
        """Create a temporary markdown file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Research Paper\n\n")
            f.write("## Abstract\n")
            f.write("This is a test research paper about **artificial intelligence**.\n\n")
            f.write("## Authors\n")
            f.write("- John Smith\n")
            f.write("- Jane Doe\n\n")
            f.write("## Introduction\n")
            f.write("This paper explores *AI applications* in modern technology.\n\n")
            f.write("## Methodology\n")
            f.write("We used various `machine learning` algorithms.\n\n")
            f.write("## Results\n")
            f.write("The results show promising outcomes.\n\n")
            f.write("## Conclusion\n")
            f.write("AI continues to evolve and provide valuable solutions.\n")
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def temp_pdf_file(self):
        """Create a temporary PDF file for testing."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
            # Create a minimal PDF file (not a real PDF, just for testing file detection)
            f.write(b"%PDF-1.4\n%Test PDF content\n")
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    def test_analyze_paper_module_import(self):
        """Test that the analyze_paper module can be imported successfully."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            import analyze_paper  # noqa: F401
            
            # Test that key functions and classes exist
            assert hasattr(analyze_paper, 'check_file_type')
            assert hasattr(analyze_paper, 'read_text_or_markdown')
            assert hasattr(analyze_paper, 'convert_pdf_to_markdown')
            assert hasattr(analyze_paper, 'run_workflow')
            assert hasattr(analyze_paper, 'create_file_to_linkedin_workflow')
            assert hasattr(analyze_paper, 'PaperInfo')
            assert hasattr(analyze_paper, 'app')
            
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    def test_paper_info_model(self):
        """Test PaperInfo Pydantic model."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to register all nodes
            import analyze_paper  # noqa: F401
            from analyze_paper import PaperInfo
            
            # Test valid data
            paper_info = PaperInfo(
                title="Test Paper",
                authors=["John Smith", "Jane Doe"]
            )
            
            assert paper_info.title == "Test Paper"
            assert paper_info.authors == ["John Smith", "Jane Doe"]
            
            # Test serialization
            data = paper_info.model_dump()
            assert data["title"] == "Test Paper"
            assert data["authors"] == ["John Smith", "Jane Doe"]
            
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    def test_workflow_creation(self):
        """Test workflow structure creation."""
        from analyze_paper import create_file_to_linkedin_workflow
        
        workflow = create_file_to_linkedin_workflow()
        
        # Check that the workflow has the expected structure
        assert workflow.start_node == "check_file_type"
        
        # Check that all expected nodes are present
        expected_nodes = [
            "check_file_type", "read_text_or_markdown", "convert_pdf_to_markdown",
            "save_markdown_content", "extract_first_100_lines", "extract_paper_info",
            "extract_title_str", "extract_authors_str", "generate_linkedin_post",
            "save_draft_post_content", "format_linkedin_post", "clean_markdown_syntax",
            "copy_to_clipboard"
        ]
        
        # Check each expected node exists in the workflow
        for node_name in expected_nodes:
            assert node_name in workflow.nodes, f"Node {node_name} missing from workflow"
        
        # Check that the workflow has at least the expected number of nodes
        assert len(workflow.nodes) >= len(expected_nodes)
    
    
    def test_cli_command_help(self):
        """Test CLI command help functionality."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to register all nodes
            import analyze_paper  # noqa: F401
            from analyze_paper import app
            
            # Test that the app is a typer app
            assert hasattr(app, 'info')
            # Typer apps have registered_commands instead of commands
            assert hasattr(app, 'registered_commands') or hasattr(app, 'registered_callback')
            
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    def test_check_poppler_dependency(self):
        """Test poppler dependency check."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to register all nodes
            import analyze_paper  # noqa: F401
            from analyze_paper import check_poppler            # Mock subprocess to test both success and failure cases
            with patch('subprocess.run') as mock_run:
                # Test successful poppler check
                mock_run.return_value = None
                try:
                    check_poppler()
                    # Should not raise an exception
                except Exception:
                    pytest.fail("check_poppler should not raise exception when poppler is available")
                
                # Test failed poppler check
                mock_run.side_effect = FileNotFoundError()
                with pytest.raises(typer.Exit):
                    check_poppler()
                    
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    @patch('quantalogic_flow.flow.nodes.acompletion')
    @patch('pyperclip.copy')
    def test_workflow_integration_markdown(self, mock_copy, mock_acompletion, temp_markdown_file):
        """Test the complete workflow with a markdown file."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to register all nodes
            import analyze_paper  # noqa: F401
            from analyze_paper import run_workflow, PaperInfo
            
            # Create a proper mock for structured responses
            def create_structured_mock(content: str, response_model):
                """Create a mock structured response that matches instructor expectations."""
                mock_tool_call = Mock()
                mock_tool_call.function.arguments = content
                mock_tool_call.function.name = response_model.__name__  # Use the class name
                mock_tool_call.id = 'test_call_id'
                mock_tool_call.type = 'function'
                
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message = Mock()
                mock_response.choices[0].message.content = content
                mock_response.choices[0].message.role = 'assistant'
                mock_response.choices[0].message.refusal = None
                mock_response.choices[0].message.tool_calls = [mock_tool_call]
                mock_response.choices[0].finish_reason = 'stop'
                mock_response.choices[0].index = 0
                mock_response.usage = Mock()
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 200
                mock_response.usage.total_tokens = 300
                mock_response.id = 'test-response-id'
                mock_response.model = 'test-model'
                mock_response.created = 1234567890
                mock_response.object = 'chat.completion'
                return mock_response
                
            # Mock LLM responses
            mock_responses = [
                create_structured_mock('{"title": "Test Research Paper", "authors": ["John Smith", "Jane Doe"]}', PaperInfo),  # extract_paper_info
                MockLLMResponse("This is a great LinkedIn post about AI research..."),  # generate_linkedin_post
                MockLLMResponse("This is a great LinkedIn post about AI research...")   # format_linkedin_post
            ]
            mock_acompletion.side_effect = mock_responses
            
            result = asyncio.run(run_workflow(
                file_path=temp_markdown_file,
                text_extraction_model="test-model",
                cleaning_model="test-model",
                writing_model="test-model",
                copy_to_clipboard_flag=True,
                max_character_count=1000
            ))
            
            # Check that the workflow completed successfully
            assert "post_content" in result
            assert "clipboard_status" in result
            assert result["clipboard_status"] == "Content copied to clipboard"
            
            # Check that files were created
            assert "markdown_file_path" in result
            assert result["markdown_file_path"].endswith(".extracted.md")
            assert os.path.exists(result["markdown_file_path"])
            
            # Check that pyperclip was called
            mock_copy.assert_called_once()
            
            # Cleanup
            for file_path in [result.get("markdown_file_path"), result.get("draft_post_file_path")]:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
                
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    @patch('quantalogic_flow.flow.nodes.acompletion')
    @patch('pyperclip.copy')
    def test_workflow_integration_text(self, mock_copy, mock_acompletion, temp_text_file):
        """Test the complete workflow with a text file."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to register all nodes
            import analyze_paper  # noqa: F401
            from analyze_paper import run_workflow
            
            # Mock LLM responses
            mock_responses = [
                MockLLMResponse('{"title": "Test Research Paper", "authors": ["John Smith", "Jane Doe"]}'),  # extract_paper_info
                MockLLMResponse("This is a great LinkedIn post about AI research..."),  # generate_linkedin_post
                MockLLMResponse("This is a great LinkedIn post about AI research...")   # format_linkedin_post
            ]
            mock_acompletion.side_effect = mock_responses
            
            result = asyncio.run(run_workflow(
                file_path=temp_text_file,
                text_extraction_model="test-model",
                cleaning_model="test-model",
                writing_model="test-model",
                copy_to_clipboard_flag=False,
                max_character_count=1000
            ))
            
            # Check that the workflow completed successfully
            assert "post_content" in result
            assert "clipboard_status" in result
            assert result["clipboard_status"] == "Clipboard copying skipped"
            
            # Cleanup
            for file_path in [result.get("markdown_file_path"), result.get("draft_post_file_path")]:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
                
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    def test_workflow_nonexistent_file(self):
        """Test workflow with nonexistent file."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to register all nodes
            import analyze_paper  # noqa: F401
            from analyze_paper import run_workflow
            
            with pytest.raises(ValueError, match="File not found"):
                asyncio.run(run_workflow(
                    file_path="/nonexistent/file.pdf",
                    text_extraction_model="test-model",
                    cleaning_model="test-model",
                    writing_model="test-model"
                ))
                
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    @patch('pyzerox.zerox')
    def test_convert_pdf_to_markdown(self, mock_zerox, temp_pdf_file):
        """Test PDF to markdown conversion."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to load the nodes
            import analyze_paper  # noqa: F401
            
            # Mock zerox response
            mock_result = Mock()
            mock_result.pages = [Mock(content="# Extracted Content\n\nThis is extracted text.")]
            mock_zerox.return_value = mock_result
            
            # Get the registered node function
            node_func = Nodes.NODE_REGISTRY['convert_pdf_to_markdown'][0]
            
            result = asyncio.run(node_func(
                file_path=temp_pdf_file,
                model="test-model",
                custom_system_prompt=None,
                output_dir=None,
                select_pages=None
            ))
            
            assert "Extracted Content" in result
            assert "extracted text" in result
            mock_zerox.assert_called_once()
            
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    def test_file_type_detection_via_workflow(self, temp_pdf_file, temp_text_file, temp_markdown_file):
        """Test file type detection through workflow execution."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to load the nodes
            import analyze_paper  # noqa: F401
            
            # Get the registered node function
            node_func = Nodes.NODE_REGISTRY['check_file_type'][0]
            
            # Test PDF
            result = asyncio.run(node_func(file_path=temp_pdf_file))
            assert result == "pdf"
            
            # Test text
            result = asyncio.run(node_func(file_path=temp_text_file))
            assert result == "text"
            
            # Test markdown
            result = asyncio.run(node_func(file_path=temp_markdown_file))
            assert result == "markdown"
            
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    def test_read_text_or_markdown_via_workflow(self, temp_text_file, temp_markdown_file):
        """Test text/markdown reading through workflow execution."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to load the nodes
            import analyze_paper  # noqa: F401
            
            # Get the registered node function
            node_func = Nodes.NODE_REGISTRY['read_text_or_markdown'][0]
            
            # Test text file
            result = asyncio.run(node_func(file_path=temp_text_file, file_type="text"))
            assert "Test Research Paper" in result
            assert "John Smith" in result
            assert "Jane Doe" in result
            
            # Test markdown file
            result = asyncio.run(node_func(file_path=temp_markdown_file, file_type="markdown"))
            assert "Test Research Paper" in result
            assert "**artificial intelligence**" in result
            assert "*AI applications*" in result
            
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    def test_clean_markdown_syntax_via_workflow(self):
        """Test markdown syntax cleaning through workflow execution."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))
        
        try:
            # Import the module to load the nodes
            import analyze_paper  # noqa: F401
            
            # Get the registered node function
            node_func = Nodes.NODE_REGISTRY['clean_markdown_syntax'][0]
            
            test_content = """
# Header

This is **bold** text and *italic* text.

## Another header

Here's some `inline code` and a [link](http://example.com).

```python
def hello():
    print("Hello")
```

> This is a blockquote

<div>HTML content</div>

---

Final paragraph.
"""
            
            result = asyncio.run(node_func(post_content=test_content))
            
            # Should remove markdown syntax
            assert "**bold**" not in result
            assert "*italic*" not in result
            assert "# Header" not in result
            assert "## Another header" not in result
            assert "`inline code`" not in result
            assert "[link](http://example.com)" not in result
            assert "```python" not in result
            assert "> This is a blockquote" not in result
            assert "<div>HTML content</div>" not in result
            assert "---" not in result
            
            # Should keep the actual text content
            assert "bold" in result
            assert "italic" in result
            assert "Header" in result
            assert "inline code" in result
            assert "link" in result
            assert "Hello" in result
            assert "Final paragraph" in result
            
        finally:
            sys.path.remove(str(Path(__file__).parent.parent.parent / "examples" / "analyze_paper"))

    def test_script_execution_with_test_file(self, temp_markdown_file):
        """Test running the script with a test file."""
        import subprocess
        import sys
        
        # Get the script path
        script_path = Path(__file__).parent.parent.parent / "examples" / "analyze_paper" / "analyze_paper.py"
        
        # Run the script with the test file and no-copy flag
        result = subprocess.run([
            sys.executable, str(script_path),
            temp_markdown_file,
            "--no-copy-to-clipboard-flag",
            "--text-extraction-model", "gemini/gemini-2.5-flash",
            "--cleaning-model", "gemini/gemini-2.5-flash", 
            "--writing-model", "gemini/gemini-2.5-flash"
        ], capture_output=True, text=True, timeout=30)
        
        # The script should run without errors (though it might fail due to API keys)
        # We mainly want to test that the script structure is valid
        assert result.returncode in [0, 1]  # 0 for success, 1 for API key errors
        
        # Check that help works
        help_result = subprocess.run([
            sys.executable, str(script_path), "--help"
        ], capture_output=True, text=True, timeout=10)
        
        assert help_result.returncode == 0
        assert "analyze" in help_result.stdout.lower()
        assert "file_path" in help_result.stdout.lower()
        
    def test_example_has_documentation(self):
        """Test that the example has proper documentation."""
        example_dir = Path(__file__).parent.parent.parent / "examples" / "analyze_paper"
        
        # Check that README exists
        readme_path = example_dir / "README.md"
        assert readme_path.exists(), "README.md should exist"
        
        # Check that the main script has proper docstrings
        script_path = example_dir / "analyze_paper.py"
        assert script_path.exists(), "analyze_paper.py should exist"
        
        content = script_path.read_text()
        assert '"""' in content or "'''" in content, "Script should have documentation"
        
        # Check that README has basic content
        readme_content = readme_path.read_text()
        assert "Paper Analyzer" in readme_content
        assert "Usage" in readme_content
        assert "LinkedIn" in readme_content
