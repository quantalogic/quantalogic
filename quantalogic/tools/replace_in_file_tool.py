"""Tool for replacing sections in an existing file based on SEARCH/REPLACE blocks.

This tool:
1. Parses multiple SEARCH/REPLACE blocks from a diff-like string.
2. Attempts exact replacement in the target file first.
3. If exact matches fail, attempts a similarity-based match by comparing the
   search string to every substring of the file content of matching length.
4. Replaces (or deletes if replace block is empty) the best-scoring substring
   if it meets the specified similarity threshold.
5. Tracks changes to avoid overlapping replacements.
6. Writes the modified file content back to disk if changes are made.
"""

import difflib
import os
from typing import List, Optional, Tuple

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from quantalogic.tools.tool import Tool, ToolArgument


class SearchReplaceBlock(BaseModel):
    """Represents a single SEARCH/REPLACE block.

    Attributes:
        search (str):
            Exact content to search for in the file (includes docstrings, whitespace, etc.).
        replace (str):
            Content to replace the `search` with. If empty, indicates deletion of the matched content.
        similarity (float | None):
            Stores the similarity ratio when a non-exact match is made.
    """

    search: str = Field(
        ...,
        description="Exact content to search for in the file. Space and tab characters are VERY important.",
        example="def old_function():\n    pass",
    )
    replace: str = Field(
        ...,
        description="Content that replaces the `search`. Can be empty to delete the searched content.",
        example="def new_function():\n    print('Hello, World!')",
    )
    similarity: Optional[float] = Field(
        None,
        description="Similarity ratio when non-exact match is made.",
    )

    @classmethod
    def from_block(cls, search: str, replace: str) -> "SearchReplaceBlock":
        """Creates a SearchReplaceBlock instance from search and replace strings."""
        return cls(search=search, replace=replace)


class ReplaceInFileTool(Tool):
    """Tool for replacing sections in an existing file based on SEARCH/REPLACE blocks."""

    name: str = "replace_in_file_tool"
    description: str = (
        "Updates sections of content in an existing file using SEARCH/REPLACE blocks. "
        "If exact matches are not found, the tool attempts to find similar sections based on similarity. "
        "Returns the updated content or an error."
    )
    need_validation: bool = True

    SIMILARITY_THRESHOLD: float = 0.85

    arguments: list[ToolArgument] = [
        ToolArgument(
            name="path",
            arg_type="string",
            description=(
                "The path of the file to modify (relative to the current working "
                "directory). Using an absolute path is recommended."
            ),
            required=True,
            example="./src/main.py",
        ),
        ToolArgument(
            name="diff",
            arg_type="string",
            description=(
                "Define one or more SEARCH/REPLACE blocks to specify the exact changes to be made in the code. "
                "Each block must follow this precise format:\n"
                "```\n"
                "<<<<<<< SEARCH\n"
                "[exact content to find, characters must match EXACTLY including whitespace, indentation, line endings]\n"
                "=======\n"
                "[new content to replace with]\n"
                ">>>>>>> REPLACE\n"
                "```\n\n"
                "### Critical Rules:\n"
                "1. **Exact Matching**:\n"
                "   - The SEARCH content must match the corresponding section in the file exactly:\n"
                "     - This includes all characters, whitespace, indentation, and line endings.\n"
                "     - Ensure all comments, docstrings, and other relevant text are included.\n"
                "2. **Replacement Mechanics**:\n"
                "   - Each SEARCH/REPLACE block will only replace the first occurrence found.\n"
                "   - To make multiple changes, create separate unique SEARCH/REPLACE blocks for each.\n"
                "   - Include just enough context in each SEARCH section to uniquely identify the lines needing change.\n"
                "3. **Conciseness and Clarity**:\n"
                "   - Break larger SEARCH/REPLACE blocks into smaller segments that each modify a specific part of the file.\n"
                "   - Include only the lines that change and a few surrounding lines if necessary for uniqueness.\n"
                "   - Ensure each line is complete; do not truncate lines mid-way to prevent matching failures.\n"
                "4. **Special Operations**:\n"
                "   - An empty SEARCH/REPLACE block will result in the deletion of the corresponding line.\n"
                "   - If a block is missing entirely, the file will remain unchanged.\n"
                "   - To move code: Use two blocks—one to delete from the original location and another to insert at the new location.\n"
                "   - To delete code: Use an empty REPLACE section.\n"
            ),
            required=True,
            example=(
                "<<<<<<< SEARCH\n"
                "def old_function():\n"
                "    pass\n"
                "=======\n"
                "def new_function():\n"
                "    print('Hello, World!')\n"
                ">>>>>>> REPLACE\n"
            ),
        ),
    ]

    def normalize_whitespace(self, text: str) -> str:
        """Normalize leading whitespace by converting tabs to spaces."""
        return '\n'.join([self._normalize_line(line) for line in text.split('\n')])

    def _normalize_line(self, line: str) -> str:
        """Normalize leading whitespace in a single line."""
        leading_ws = len(line) - len(line.lstrip())
        return line.replace('\t', '    ', leading_ws)  # Convert tabs to 4 spaces only in leading whitespace

    def parse_diff(self, diff: str) -> list[SearchReplaceBlock]:
        """Parses the diff string into a list of SearchReplaceBlock instances."""
        if not diff or not diff.strip():
            raise ValueError("Empty or invalid diff string provided")

        blocks: list[SearchReplaceBlock] = []
        lines = diff.splitlines()
        idx = 0

        while idx < len(lines):
            line = lines[idx].strip()
            if line == "<<<<<<< SEARCH":
                search_lines = []
                idx += 1

                while idx < len(lines) and lines[idx].strip() != "=======":
                    search_lines.append(lines[idx])
                    idx += 1

                if idx >= len(lines):
                    raise ValueError("Invalid diff format: Missing '=======' marker")

                replace_lines = []
                idx += 1

                while idx < len(lines) and lines[idx].strip() != ">>>>>>> REPLACE":
                    replace_lines.append(lines[idx])
                    idx += 1

                if idx >= len(lines):
                    raise ValueError("Invalid diff format: Missing '>>>>>>> REPLACE' marker")

                search_content = "\n".join(search_lines).rstrip()
                replace_content = "\n".join(replace_lines).rstrip()

                try:
                    block = SearchReplaceBlock.from_block(search=search_content, replace=replace_content)
                    blocks.append(block)
                except ValidationError as ve:
                    raise ValueError(f"Invalid block format: {ve}")

            idx += 1

        if not blocks:
            raise ValueError("No valid SEARCH/REPLACE blocks found in the diff")

        return blocks

    def execute(self, path: str, diff: str) -> str:
        """Replaces sections in a file based on SEARCH/REPLACE blocks with similarity-based fallback."""
        if not path:
            return "Error: File path cannot be empty"

        if not diff:
            return "Error: Diff content cannot be empty"

        try:
            path = os.path.expanduser(path) if path.startswith("~") else path
            path = os.path.abspath(path) if not os.path.isabs(path) else path

            if not os.path.isfile(path):
                return f"Error: File not found: '{path}'"

            blocks = self.parse_diff(diff)

            try:
                with open(path, encoding="utf-8") as file:
                    content = file.read()
            except UnicodeDecodeError:
                return f"Error: File must be UTF-8 encoded: '{path}'"
            except Exception as e:
                return f"Error: Failed to read file '{path}': {str(e) or 'Unknown error'}"

            original_content = content
            changes: List[Tuple[int, int]] = []

            for idx, block in enumerate(blocks, 1):
                if not block.search:
                    if block.replace:
                        content += f"\n{block.replace}"
                        logger.debug(f"Block {idx}: Appended content")
                    continue

                match_found = False
                if block.search in content:
                    start = content.find(block.search)
                    end = start + len(block.search)
                    if not self._is_overlapping(changes, start, end):
                        if block.replace:
                            content = f"{content[:start]}{block.replace}{content[end:]}"
                        else:
                            content = f"{content[:start]}{content[end:]}"
                        changes.append((start, start + len(block.replace) if block.replace else start))
                        match_found = True
                        logger.debug(f"Block {idx}: Exact match {'replaced' if block.replace else 'deleted'}")

                if not match_found:
                    similarity, matched_str = self.find_similar_match(block.search, content)
                    if similarity >= self.SIMILARITY_THRESHOLD and matched_str:
                        start = content.find(matched_str)
                        end = start + len(matched_str)
                        if not self._is_overlapping(changes, start, end):
                            block.similarity = similarity
                            if block.replace:
                                content = f"{content[:start]}{block.replace}{content[end:]}"
                            else:
                                content = f"{content[:start]}{content[end:]}"
                            changes.append((start, start + len(block.replace) if block.replace else start))
                            logger.debug(
                                f"Block {idx}: Similar match (similarity={similarity:.1%}) "
                                f"{'replaced' if block.replace else 'deleted'}"
                            )
                            match_found = True

                if not match_found:
                    return f"Error: No matching content found for block {idx}. " f"Best similarity: {similarity:.1%}"

            if content == original_content:
                return f"No changes needed in '{path}'"

            try:
                with open(path, "w", encoding="utf-8") as file:
                    file.write(content)
            except Exception as e:
                return f"Error: Failed to write changes to '{path}': {str(e) or 'Unknown error'}"

            # Maintain original success message format
            message = [f"Successfully modified '{path}'"]
            for idx, block in enumerate(blocks, 1):
                status = "Exact match" if block.similarity is None else f"Similar match ({block.similarity:.1%})"
                message.append(f"- Block {idx}: {status}")

            return "\n".join(message)

        except (OSError, ValueError) as e:
            error_msg = str(e)
            logger.error(error_msg)
            return f"Error: {error_msg or 'Unknown error occurred'}"
        except Exception as e:
            error_msg = str(e)
            logger.exception("Unexpected error")
            return f"Error: Unexpected error occurred - {error_msg or 'Unknown error'}"

    def find_similar_match(self, search: str, content: str) -> Tuple[float, str]:
        """Finds the most similar substring in content compared to search with whitespace normalization."""
        norm_search = self.normalize_whitespace(search)
        content_lines = content.split('\n')
        norm_content = self.normalize_whitespace(content)
        norm_content_lines = norm_content.split('\n')

        if len(norm_content_lines) < len(norm_search.split('\n')):
            return 0.0, ""

        max_similarity = 0.0
        best_match = ""
        search_line_count = len(norm_search.split('\n'))

        for i in range(len(norm_content_lines) - search_line_count + 1):
            candidate_norm = '\n'.join(norm_content_lines[i:i+search_line_count])
            similarity = difflib.SequenceMatcher(None, norm_search, candidate_norm).ratio()

            if similarity > max_similarity:
                max_similarity = similarity
                # Get original lines (non-normalized) for accurate replacement
                best_match = '\n'.join(content_lines[i:i+search_line_count])

        return max_similarity, best_match

    def _is_overlapping(self, changes: List[Tuple[int, int]], start: int, end: int) -> bool:
        """Checks if the given range overlaps with any existing changes."""
        return any(not (end <= change_start or start >= change_end) for change_start, change_end in changes)


if __name__ == "__main__":
    tool = ReplaceInFileTool()
    print(tool.to_markdown())