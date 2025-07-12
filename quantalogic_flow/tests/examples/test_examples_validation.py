"""Example validation tests for quantalogic_flow examples."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tests.mocks import MockLLMResponse


class TestExampleValidation:
    """Validate that examples work correctly."""
    
    @pytest.mark.examples
    @patch("quantalogic_flow.flow.nodes.acompletion")
    async def test_simple_story_generator_workflow(self, mock_acompletion):
        """Test the simple story generator example workflow."""        # Setup mock responses for the story generator
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
        import sys
        example_path = Path(__file__).parent.parent.parent / "examples" / "simple_story_generator"
        sys.path.insert(0, str(example_path))
        
        try:
            from story_generator_agent import create_story_workflow
            
            # Create and run the workflow
            workflow = create_story_workflow()
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
        import sys
        example_path = Path(__file__).parent.parent.parent / "examples" / "simple_story_generator"
        sys.path.insert(0, str(example_path))
        
        try:
            from story_generator_agent import create_story_workflow
            
            workflow = create_story_workflow()
            engine = workflow.build()
            
            # Test invalid genre
            with pytest.raises(ValueError, match="Invalid input"):
                await engine.run({
                    "genre": "invalid_genre",
                    "num_chapters": 3,
                    "style": "descriptive",
                    "completed_chapters": 0,
                    "chapters": []
                })
            
            # Test invalid chapter count
            with pytest.raises(ValueError, match="Invalid input"):
                await engine.run({
                    "genre": "science fiction",
                    "num_chapters": 25,  # Too many chapters
                    "style": "descriptive",
                    "completed_chapters": 0,
                    "chapters": []
                })
                
        finally:
            sys.path.remove(str(example_path))
    
    @pytest.mark.examples
    async def test_story_generator_structure_validation(self):
        """Test that the story generator workflow is properly structured."""
        import sys
        example_path = Path(__file__).parent.parent.parent / "examples" / "simple_story_generator"
        sys.path.insert(0, str(example_path))
        
        try:
            from story_generator_agent import create_story_workflow
            
            workflow = create_story_workflow()
            
            # Verify workflow structure
            assert workflow.start_node == "validate_input"
            assert "validate_input" in workflow.nodes
            assert "generate_title" in workflow.nodes
            assert "generate_outline" in workflow.nodes
            assert "generate_chapter" in workflow.nodes
            assert "compile_book" in workflow.nodes
            
            # Verify transitions exist
            assert "validate_input" in workflow.transitions
            
            # Verify node outputs are properly configured
            assert workflow.node_outputs["validate_input"] == "validation_result"
            assert workflow.node_outputs["generate_title"] == "title"
            assert workflow.node_outputs["generate_outline"] == "outline"
            
        finally:
            sys.path.remove(str(example_path))
    
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
        
        import sys
        
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
