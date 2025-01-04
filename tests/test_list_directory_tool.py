import os
import unittest

from quantalogic.tools.list_directory_tool import ListDirectoryTool


class TestListDirectoryTool(unittest.TestCase):
    def setUp(self):
        self.tool = ListDirectoryTool()
        
        # Create a temporary directory with some test files and subdirectories
        self.test_dir = os.path.expanduser("~/test_directory_listing")
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Create some test files
        with open(os.path.join(self.test_dir, "file1.txt"), "w") as f:
            f.write("Test content 1")
        with open(os.path.join(self.test_dir, "file2.txt"), "w") as f:
            f.write("Test content 2")
        
        # Create a subdirectory
        os.makedirs(os.path.join(self.test_dir, "subdir"), exist_ok=True)
        with open(os.path.join(self.test_dir, "subdir", "subfile.txt"), "w") as f:
            f.write("Subdirectory file")

    def tearDown(self):
        # Clean up the test directory
        import shutil
        shutil.rmtree(self.test_dir)

    def test_non_recursive_listing(self):
        """Test non-recursive directory listing."""
        result = self.tool.execute(self.test_dir)
        
        # Verify basic structure
        self.assertIsInstance(result, str)
        self.assertIn(f"Contents of directory: {self.test_dir}", result)
        self.assertIn("file1.txt", result)
        self.assertIn("file2.txt", result)
        self.assertIn("subdir/ <DIR>", result)
        self.assertIn("End of directory listing", result)

    def test_recursive_listing(self):
        """Test recursive directory listing."""
        result = self.tool.execute(self.test_dir, recursive="true")
        
        # Verify basic structure
        self.assertIsInstance(result, str)
        self.assertIn(f"Contents of directory: {self.test_dir}", result)
        self.assertIn("file1.txt", result)
        self.assertIn("file2.txt", result)
        self.assertIn("subdir/ <DIR>", result)
        self.assertIn("subfile.txt", result)
        self.assertIn("End of directory listing", result)

    def test_pagination(self):
        """Test pagination functionality."""
        # Add more files to test pagination
        for i in range(3, 10):
            with open(os.path.join(self.test_dir, f"file{i}.txt"), "w") as f:
                f.write(f"Test content {i}")
        
        # Test first page
        result = self.tool.execute(self.test_dir, start_line="1", end_line="5")
        self.assertIsInstance(result, str)
        
        # Verify content and pagination
        self.assertIn("Showing lines 1-5", result)
        
        # Split the result into lines
        lines = result.split("\n")
        
        # Verify that the result contains the expected content
        self.assertTrue(len(lines) >= 5, f"Expected at least 5 lines, got {len(lines)}")
        self.assertTrue(len(lines) <= 10, f"Expected no more than 10 lines, got {len(lines)}")
        
        # Verify some key elements are present
        self.assertIn(f"Contents of directory: {self.test_dir}", result)
        self.assertIn("End of directory listing", result)

    def test_empty_directory(self):
        """Test listing an empty directory."""
        empty_dir = os.path.expanduser("~/empty_test_directory")
        os.makedirs(empty_dir, exist_ok=True)
        
        try:
            result = self.tool.execute(empty_dir)
            self.assertEqual(result, "The directory is empty.")
        finally:
            os.rmdir(empty_dir)

    def test_invalid_directory(self):
        """Test handling of invalid directory path."""
        with self.assertRaises(ValueError):
            self.tool.execute("/path/to/non/existent/directory")

if __name__ == '__main__':
    unittest.main()
