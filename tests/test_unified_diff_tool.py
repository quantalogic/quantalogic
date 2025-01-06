import os
import tempfile
import unittest
import shutil

from quantalogic.tools.unified_diff_tool import UnifiedDiffTool, PatchError


class TestUnifiedDiffTool(unittest.TestCase):
    def setUp(self):
        """Create a temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        self.tool = UnifiedDiffTool()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def create_test_file(self, content):
        """Helper method to create a test file."""
        test_file_path = os.path.join(self.test_dir, "test_file.txt")
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return test_file_path

    def test_simple_line_replacement(self):
        """Test replacing a single line."""
        original_content = "Hello World\nThis is a test.\nGoodbye World\n"
        test_file_path = self.create_test_file(original_content)

        patch = "@@ -1,3 +1,3 @@\n-Hello World\n+Hello Universe\n This is a test.\n Goodbye World\n"
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "Hello Universe\nThis is a test.\nGoodbye World\n")

    def test_line_addition(self):
        """Test adding a new line."""
        original_content = "Hello World\nThis is a test.\n"
        test_file_path = self.create_test_file(original_content)

        patch = "@@ -2,1 +2,2 @@\n This is a test.\n+A new line added.\n"
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "Hello World\nThis is a test.\nA new line added.\n")

    def test_line_deletion(self):
        """Test deleting a line."""
        original_content = "Hello World\nThis is a test.\nGoodbye World\n"
        test_file_path = self.create_test_file(original_content)

        patch = "@@ -1,3 +1,2 @@\n Hello World\n-This is a test.\n Goodbye World\n"
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "Hello World\nGoodbye World\n")

    def test_multiple_hunks(self):
        """Test applying a patch with multiple hunks."""
        original_content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
        test_file_path = self.create_test_file(original_content)

        patch = (
            "@@ -1,2 +1,2 @@\n-Line 1\n+Updated Line 1\n Line 2\n"
            "@@ -4,2 +4,2 @@\n Line 4\n-Line 5\n+Updated Line 5\n"
        )
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "Updated Line 1\nLine 2\nLine 3\nLine 4\nUpdated Line 5\n")

    def test_context_mismatch(self):
        """Test that a patch with incorrect context raises an error."""
        original_content = "Hello World\nThis is a test.\nGoodbye World\n"
        test_file_path = self.create_test_file(original_content)

        patch = "@@ -1,3 +1,3 @@\n-Wrong Context\n+Hello Universe\n This is a test.\n Goodbye World\n"

        with self.assertRaises(PatchError) as context:
            self.tool.execute(test_file_path, patch)

        self.assertTrue("Context mismatch" in str(context.exception))

    def test_non_existent_file(self):
        """Test applying a patch to a non-existent file."""
        non_existent_file = os.path.join(self.test_dir, "non_existent.txt")
        patch = "@@ -1,1 +1,1 @@\n-Old Line\n+New Line\n"

        with self.assertRaises(FileNotFoundError):
            self.tool.execute(non_existent_file, patch)

    def test_malformed_hunk_header(self):
        """Test a patch with a malformed hunk header."""
        original_content = "Hello World\n"
        test_file_path = self.create_test_file(original_content)

        patch = "@@ Invalid Hunk Header @@\n-Hello World\n+Hello Universe\n"

        with self.assertRaises(PatchError) as context:
            self.tool.execute(test_file_path, patch)

        self.assertTrue("Malformed hunk header" in str(context.exception))

    def test_patch_beyond_file_length(self):
        """Test a patch that refers to lines beyond the file's length."""
        original_content = "Short File\n"
        test_file_path = self.create_test_file(original_content)

        # Patch starts at line 2 and tries to add 2 lines
        patch = "@@ -2,2 +2,2 @@\n+New Line 1\n+New Line 2\n"

        with self.assertRaises(PatchError) as context:
            self.tool.execute(test_file_path, patch)

        self.assertTrue("Patch refers to lines beyond file length" in str(context.exception))

    def test_backup_file_creation(self):
        """Test that a backup file is created during patch application."""
        original_content = "Hello World\n"
        test_file_path = self.create_test_file(original_content)
        backup_path = f"{test_file_path}.bak"

        patch = "@@ -1,1 +1,1 @@\n-Hello World\n+Hello Universe\n"
        self.tool.execute(test_file_path, patch)

        self.assertTrue(os.path.exists(backup_path))
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_content = f.read()
        self.assertEqual(backup_content, original_content)

    def test_cdata_wrapped_patch(self):
        """Test applying a patch wrapped in CDATA tags."""
        original_content = "Hello World\nThis is a test.\nGoodbye World\n"
        test_file_path = self.create_test_file(original_content)

        patch = (
            "<![CDATA[\n"
            "@@ -1,3 +1,3 @@\n"
            "-Hello World\n"
            "+Hello Universe\n"
            " This is a test.\n"
            " Goodbye World\n"
            "]]>"
        )
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "Hello Universe\nThis is a test.\nGoodbye World\n")

    def test_patch_with_file_headers(self):
        """Test applying a patch with file headers."""
        original_content = "Hello World\nThis is a test.\nGoodbye World\n"
        test_file_path = self.create_test_file(original_content)

        patch = (
            "--- a/original_file.txt\n"
            "+++ b/modified_file.txt\n"
            "@@ -1,3 +1,3 @@\n"
            "-Hello World\n"
            "+Hello Universe\n"
            " This is a test.\n"
            " Goodbye World\n"
        )
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "Hello Universe\nThis is a test.\nGoodbye World\n")

    def test_patch_with_empty_lines(self):
        """Test applying a patch with empty lines."""
        original_content = "Hello World\nThis is a test.\nGoodbye World\n"
        test_file_path = self.create_test_file(original_content)

        patch = "@@ -1,3 +1,4 @@\n" "-Hello World\n" "+\n" "+Hello Universe\n" " This is a test.\n" " Goodbye World\n"
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "\nHello Universe\nThis is a test.\nGoodbye World\n")

    def test_snake_game_patch(self):
        """Test applying a patch with multiple hunks and comment additions."""
        original_content = """import pygame
import time
import random

pygame.init()

white = (255, 255, 255)
yellow = (255, 255, 102)
black = (0, 0, 0)
green = (0, 255, 0)
blue = (50, 153, 213)

width = 600
height = 400
dis = pygame.display.set_mode((width, height))
pygame.display.set_caption('Snake Game')

snake_block = 10
snake_speed = 15

font_style = pygame.font.SysFont("bahnschrift", 25)
score_font = pygame.font.SysFont("comicsansms", 35)

def our_snake(snake_block, snake_list):
    for x in snake_list:
        pygame.draw.rect(dis, black, [x[0], x[1], snake_block, snake_block])

def message(msg, color):
    mesg = font_style.render(msg, True, color)
    dis.blit(mesg, )

def gameLoop():
    game_over = False
    game_close = False

    x1 = width / 2
    y1 = height / 2

    x1_change = 0
    y1_change = 0
    snake_list = []
    length_of_snake = 1

    foodx = round(random.randrange(0, width - snake_block) / 10.0) * 10.0
    foody = round(random.randrange(0, height - snake_block) / 10.0) * 10.0

    while not game_over:
        while game_close == True:
            dis.fill(blue)
            message("You Lost! Press C-Play Again or Q-Quit", red)
            pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_over = True
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    x1_change = -snake_block
                elif event.key == pygame.K_RIGHT:
                    x1_change = snake_block
                elif event.key == pygame.K_UP:
                    y1_change = -snake_block
                elif event.key == pygame.K_DOWN:
                    y1_change = snake_block

        if x1 >= width or x1 < 0 or y1 >= height or y1 < 0:
            game_close = True
        x1 += x1_change
        y1 += y1_change
        dis.fill(white)
        pygame.draw.rect(dis, green, )
        snake_head = []
        snake_head.append(x1)
        snake_head.append(y1)
        snake_list.append(snake_head)
        if len(snake_list) > length_of_snake:
            del snake_list[0]

        our_snake(snake_block, snake_list)

        pygame.display.update()

        if x1 == foodx and y1 == foody:
            foodx = round(random.randrange(0, width - snake_block) / 10.0) * 10.0
            foody = round(random.randrange(0, height - snake_block) / 10.0) * 10.0
            length_of_snake += 1

        pygame.time.Clock().tick(snake_speed)

    pygame.quit()
    quit()

gameLoop()"""
        test_file_path = self.create_test_file(original_content)

        patch = """--- ./demo01/snake.py
+++ ./demo01/snake.py
@@ -1,6 +1,8 @@
 import pygame
 import time
 import random

 pygame.init()

+ # Define colors using RGB values
 white = (255, 255, 255)
 yellow = (255, 255, 102)
 black = (0, 0, 0)
@@ -10,7 +12,8 @@
 green = (0, 255, 0)
 blue = (50, 153, 213)

+ # Set dimensions for the game window
 width = 600
 height = 400
 dis = pygame.display.set_mode((width, height))
@@ -14,6 +17,8 @@
 pygame.display.set_caption('Snake Game')

 snake_block = 10
+ # Set the speed of the snake
 snake_speed = 15

 font_style = pygame.font.SysFont("bahnschrift", 25)
@@ -19,6 +24,8 @@
 score_font = pygame.font.SysFont("comicsansms", 35)

 def our_snake(snake_block, snake_list):
+     # Draw the snake on the display
     for x in snake_list:
         pygame.draw.rect(dis, black, [x[0], x[1], snake_block, snake_block])

@@ -25,6 +32,8 @@
 def message(msg, color):
+     # Display a message on the screen
     mesg = font_style.render(msg, True, color)
     dis.blit(mesg, )

 def gameLoop():
+     # Main function to run the game loop
     game_over = False
     game_close = False
@@ -30,6 +39,8 @@
     x1 = width / 2
     y1 = height / 2

+     # Initialize snake movement variables
     x1_change = 0
     y1_change = 0
     snake_list = []
@@ -36,6 +47,8 @@
     length_of_snake = 1

+     # Generate food location
     foodx = round(random.randrange(0, width - snake_block) / 10.0) * 10.0
     foody = round(random.randrange(0, height - snake_block) / 10.0) * 10.0

     while not game_over:
@@ -42,6 +55,8 @@
         while game_close == True:
             dis.fill(blue)
+            # Show game over message
             message("You Lost! Press C-Play Again or Q-Quit", red)
             pygame.display.update()

@@ -48,6 +63,8 @@
         for event in pygame.event.get():
             if event.type == pygame.QUIT:
                 game_over = True
+            # Control snake movement with arrow keys
             if event.type == pygame.KEYDOWN:
                 if event.key == pygame.K_LEFT:
                     x1_change = -snake_block
@@ -58,6 +75,8 @@

         if x1 >= width or x1 < 0 or y1 >= height or y1 < 0:
+            # End game if snake hits the wall
             game_close = True
         x1 += x1_change
         y1 += y1_change
@@ -64,6 +83,8 @@
         pygame.draw.rect(dis, green, )
         snake_head = []
         snake_head.append(x1)
         snake_head.append(y1)
+        # Add new position to the snake's body
         snake_list.append(snake_head)
         if len(snake_list) > length_of_snake:
             del snake_list[0]
@@ -72,6 +93,8 @@

         our_snake(snake_block, snake_list)

+        # Update display
         pygame.display.update()

         if x1 == foodx and y1 == foody:
+            # Increase snake length and generate new food position
             foodx = round(random.randrange(0, width - snake_block) / 10.0) * 10.0
             foody = round(random.randrange(0, height - snake_block) / 10.0) * 10.0
             length_of_snake += 1"""
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        # Verify that comments have been added
        self.assertTrue("# Define colors using RGB values" in updated_content)
        self.assertTrue("# Set dimensions for the game window" in updated_content)
        self.assertTrue("# Set the speed of the snake" in updated_content)
        # Verify that the overall structure remains the same
        self.assertTrue("def gameLoop():" in updated_content)
        self.assertTrue("pygame.init()" in updated_content)

    def test_empty_file_additions(self):
        """Test applying a patch to an empty file with only additions."""
        test_file_path = self.create_test_file("")

        patch = "@@ -0,0 +1,3 @@\n+First line\n+Second line\n+Third line\n"
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "First line\nSecond line\nThird line\n")

    def test_empty_file_invalid_start(self):
        """Test applying a patch to an empty file with invalid start line."""
        test_file_path = self.create_test_file("")

        patch = "@@ -2,0 +2,2 @@\n+Invalid line\n+Should fail\n"

        with self.assertRaises(PatchError) as context:
            self.tool.execute(test_file_path, patch)

        self.assertIn("Cannot apply hunk to empty file with start line > 1", str(context.exception))

    def test_only_additions_patch(self):
        """Test applying a patch that only contains additions."""
        original_content = "First line\nSecond line\n"
        test_file_path = self.create_test_file(original_content)

        patch = "@@ -2,0 +2,2 @@\n+New line 1\n+New line 2\n"
        result = self.tool.execute(test_file_path, patch)

        with open(test_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("Patch applied successfully", result)
        self.assertEqual(updated_content, "First line\nNew line 1\nNew line 2\nSecond line\n")

    def test_empty_file_deletion(self):
        """Test that attempting to delete from an empty file raises an error."""
        test_file_path = self.create_test_file("")

        patch = "@@ -1,1 +1,0 @@\n-Should not exist\n"

        with self.assertRaises(PatchError) as context:
            self.tool.execute(test_file_path, patch)

        self.assertIn("Cannot delete from empty file", str(context.exception))


if __name__ == "__main__":
    unittest.main()
