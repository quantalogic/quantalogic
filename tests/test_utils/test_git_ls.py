from pathspec import PathSpec

from quantalogic.tools.utils.git_ls import format_tree, generate_file_tree, git_ls, load_gitignore_spec


class TestGitLs:
    """Test suite for git_ls utility functions."""
    
    def test_git_ls_basic(self, tmp_path):
        """Test basic git_ls functionality."""
        # Create test directory structure
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").touch()

        # Test basic listing
        result = git_ls(str(tmp_path))
        
        # Check that the result is not empty
        assert result is not None, "git_ls should return a non-empty result"
        
        # Verify the result contains expected file and directory information
        assert "📄 file1.txt" in result, "Result should contain file1.txt"
        assert "📄 file2.txt" in result, "Result should contain file2.txt"
        assert "📁 subdir/" in result, "Result should contain subdir"
        
        # Verify the result follows the expected format
        lines = result.split('\n')
        assert lines[0].startswith("==== Lines:"), "Result should start with line range information"
        assert lines[-1] == "==== End of Block ====", "Result should end with block end marker"
        
    def test_load_gitignore_spec(self, tmp_path):
        """Test .gitignore pattern loading"""
        # Create .gitignore file
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.tmp\nignore_dir/\n")
        
        # Test pattern loading
        spec = load_gitignore_spec(tmp_path)
        assert isinstance(spec, PathSpec)
        assert spec.match_file("test.tmp") is True
        assert spec.match_file("ignore_dir/") is True
        assert spec.match_file("valid.txt") is False
        
    def test_generate_file_tree(self, tmp_path):
        """Test file tree generation"""
        # Create test directory structure
        (tmp_path / "file1.txt").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").touch()
        
        # Create empty gitignore spec
        spec = load_gitignore_spec(tmp_path)
        
        # Test tree generation
        tree = generate_file_tree(tmp_path, spec, recursive=True)
        assert tree["name"] == tmp_path.name
        assert tree["type"] == "directory"
        assert len(tree["children"]) == 2
        assert any(child["name"] == "file1.txt" for child in tree["children"])
        assert any(child["name"] == "subdir" for child in tree["children"])
        
    def test_format_tree(self):
        """Test tree formatting"""
        # Create sample tree structure
        tree = {
            "name": "test_dir",
            "type": "directory",
            "children": [
                {"name": "file1.txt", "type": "file", "size": "100 bytes"},
                {"name": "subdir", "type": "directory", "children": []}
            ]
        }
        
        # Test formatting
        result = format_tree(tree, 1, 10)
        assert "📁 test_dir/" in result
        assert "📄 file1.txt (100 bytes)" in result
        assert "📁 subdir/" in result
        assert "==== Lines: 1-10 of 3 ====" in result
