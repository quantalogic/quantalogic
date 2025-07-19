"""Example validation tests for quantalogic_flow examples."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from quantalogic_flow.flow import Nodes

# Mark all tests in this file as 'examples'
pytestmark = pytest.mark.examples


class MockLLMResponse:
    """A mock response object for language model calls."""
    def __init__(self, text):
        self.text = text
        # Create a mock choices structure that matches the expected format
        from unittest.mock import MagicMock
        self.choices = [MagicMock()]
        self.choices[0].message.content = text
        # Add usage information
        self.usage = MagicMock()
        self.usage.prompt_tokens = 10
        self.usage.completion_tokens = 20
        self.usage.total_tokens = 30
        self.cost = 0.001


class TestExampleValidation:
    """Test suite for validating example workflows."""

    def _load_agent_module(self, agent_name: str):
        """Load an agent module dynamically from the examples directory."""
        # Correct the path to point to the actual examples directory
        example_path = Path(__file__).parent.parent.parent / "examples" / agent_name
        module_path = example_path / "story_generator_agent.py"  # Fixed filename
        
        spec = importlib.util.spec_from_file_location("story_generator_agent", module_path)
        if spec and spec.loader:
            agent_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(agent_module)
            return agent_module
        raise ImportError(f"Could not load agent module from {module_path}")

    @pytest.fixture(autouse=True)
    def clear_node_registry(self):
        """Fixture to clear the node registry before and after each test."""
        Nodes.NODE_REGISTRY.clear()
        yield
        Nodes.NODE_REGISTRY.clear()

    @pytest.mark.examples
    @patch("quantalogic_flow.flow.nodes.acompletion")
    async def test_simple_story_generator_workflow(self, mock_acompletion):
        """Test the simple story generator example workflow."""
        # Setup mock responses for the story generator
        mock_acompletion.side_effect = [
            MockLLMResponse("The Digital Frontier"),  # Title generation
            MockLLMResponse("""
# Story Outline: The Digital Frontier

## Chapter 1: Discovery
- Protagonist discovers mysterious AI

## Chapter 2: Investigation
- Exploring the AI's capabilities

## Chapter 3: Resolution
- Final confrontation and resolution
            """.strip()),  # Outline generation
            MockLLMResponse("Chapter 1: Discovery\n\nIn a world where..."),  # Chapter 1
            MockLLMResponse("Chapter 2: Investigation\n\nThe next day..."),  # Chapter 2
            MockLLMResponse("Chapter 3: Resolution\n\nFinally, the truth..."),  # Chapter 3
            MockLLMResponse("Quality check passed: The story has good flow and coherence.")  # Quality check
        ]

        # Import the example workflow
        example_path = Path(__file__).parent.parent.parent / "examples" / "simple_story_generator"
        sys.path.insert(0, str(example_path))

        try:
            # Importing the agent module will register the nodes
            import story_generator_agent

            # Create and run the workflow
            workflow = story_generator_agent.create_story_workflow()
            engine = workflow.build()

            # Test with valid inputs
            result = await engine.run({
                "genre": "science fiction",
                "num_chapters": 3,
                "style": "descriptive",
                "completed_chapters": 0,
                "chapters": []
            })
            
            # Verify the workflow completed successfully
            assert "validation_result" in result
            assert result["validation_result"] == "Input validated"
            assert "title" in result
            assert result["title"] == "The Digital Frontier"
            assert "outline" in result
            assert "Digital Frontier" in result["outline"]
            assert "manuscript" in result
            assert "Chapter 1: Discovery" in result["manuscript"]
            assert "Chapter 2: Investigation" in result["manuscript"]
            assert "Chapter 3: Resolution" in result["manuscript"]
            assert "quality_check_result" in result
            assert "Quality check passed" in result["quality_check_result"]
            
            # Verify LLM was called the expected number of times
            assert mock_acompletion.call_count == 6  # title + outline + 3 chapters + quality_check
            
        finally:
            sys.path.remove(str(example_path))
    
    @pytest.mark.examples
    @patch("quantalogic_flow.flow.nodes.acompletion")
    async def test_story_generator_input_validation(self, mock_acompletion):
        """Test story generator input validation."""
        story_generator_agent = self._load_agent_module("simple_story_generator")

        workflow = story_generator_agent.create_story_workflow()
        engine = workflow.build()

        # Mock the acompletion call to avoid actual LLM calls
        mock_acompletion.side_effect = [
            MockLLMResponse("The Digital Frontier"),  # Title generation
            MockLLMResponse("""
- Chapter 1: Discovery
- Chapter 2: Investigation
- Chapter 3: Resolution
"""),  # Outline generation
            MockLLMResponse("Chapter 1: Discovery\n\nIn a world where..."),  # Chapter 1
            MockLLMResponse("Chapter 2: Investigation\n\nThe next day..."),  # Chapter 2
            MockLLMResponse("Chapter 3: Resolution\n\nFinally, the truth..."),  # Chapter 3
            MockLLMResponse("Quality check passed: The story has good flow and coherence.")  # Quality check
        ]

        initial_context = {
            "genre": "science fiction",
            "num_chapters": 3,
            "style": "descriptive",
            "completed_chapters": 0,
            "chapters": []
        }

        # Test invalid genre
        with pytest.raises(ValueError, match="Invalid input"):
            await engine.run({
                **initial_context,
                "genre": "invalid_genre",
            })
        
        # Test invalid chapter count
        with pytest.raises(ValueError, match="Invalid input"):
            await engine.run({
                **initial_context,
                "num_chapters": 25,  # Too many chapters
            })
                
    @pytest.mark.examples
    @patch("quantalogic_flow.flow.nodes.acompletion")
    async def test_story_generator_structure_validation(self, mock_acompletion):
        """Test that the story generator workflow is properly structured."""
        # Mock the acompletion to allow workflow instantiation
        mock_acompletion.return_value = MockLLMResponse("")
        story_generator_agent = self._load_agent_module("simple_story_generator")

        workflow = story_generator_agent.create_story_workflow()

        # Validate start and end nodes
        assert workflow.start_node == "validate_input"
        
        # Check transitions
        assert "generate_title" in [t[0] for t in workflow.transitions["validate_input"]]
        assert "generate_outline" in [t[0] for t in workflow.transitions["generate_title"]]
        
        # Check loop
        assert "generate_chapter" in [t[0] for t in workflow.transitions["generate_outline"]]
        assert "update_progress" in [t[0] for t in workflow.transitions["generate_chapter"]]
        
        # Check convergence after loop
        assert "compile_book" in [t[0] for t in workflow.transitions["update_progress"]]
        assert "quality_check" in [t[0] for t in workflow.transitions["compile_book"]]
        
    @pytest.mark.examples
    @pytest.mark.slow
    def test_examples_can_be_imported(self):
        """Test that all examples can be imported without errors."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        
        # List of example directories to test
        example_dirs = [
            "simple_story_generator",
            "story_generator", 
            # Add more as needed
        ]
        
        for example_dir in example_dirs:
            example_path = examples_dir / example_dir
            if not example_path.exists():
                continue
                
            # Find Python files in the example directory
            python_files = list(example_path.glob("*.py"))
            
            for py_file in python_files:
                if py_file.name.startswith("__"):
                    continue
                    
                # Add to path and try to import
                sys.path.insert(0, str(example_path))
                try:
                    module_name = py_file.stem
                    # Try to import - this will fail if there are syntax errors
                    __import__(module_name)
                except ImportError as e:
                    # Some imports might fail due to missing dependencies, that's OK
                    if "No module named" not in str(e):
                        pytest.fail(f"Failed to import {py_file}: {e}")
                except Exception as e:
                    pytest.fail(f"Error importing {py_file}: {e}")
                finally:
                    if str(example_path) in sys.path:
                        sys.path.remove(str(example_path))
    
    @pytest.mark.examples
    def test_example_documentation_exists(self):
        """Test that examples have proper documentation."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        
        # Main README should exist
        assert (examples_dir / "README.md").exists(), "Examples README.md not found"
        
        # Examples table should exist
        assert (examples_dir / "EXAMPLES_TABLE.md").exists(), "EXAMPLES_TABLE.md not found"
        
        # Each example directory should have some documentation
        for item in examples_dir.iterdir():
            if item.is_dir() and not item.name.startswith(".") and not item.name.startswith("__"):
                python_files = list(item.glob("*.py"))
                if python_files:
                    # Should have at least one Python file with docstring
                    has_docs = False
                    for py_file in python_files:
                        try:
                            content = py_file.read_text()
                            if '"""' in content or "'''" in content:
                                has_docs = True
                                break
                        except Exception:
                            continue
                    
                    assert has_docs, f"Example {item.name} should have documentation in Python files"
