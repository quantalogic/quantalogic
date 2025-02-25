import argparse
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from quantalogic.tools.tool import Tool, ToolArgument


class LineType(Enum):
    """Enum for different types of lines in a patch."""

    CONTEXT = " "
    ADDITION = "+"
    DELETION = "-"

    @classmethod
    def from_line(cls, line: str) -> Optional["LineType"]:
        """Get the line type from a patch line."""
        if line.startswith(" "):
            return cls.CONTEXT
        elif line.startswith("+"):
            return cls.ADDITION
        elif line.startswith("-"):
            return cls.DELETION
        return None


@dataclass
class PatchLine:
    """Represents a line in a patch with type and content."""

    type: LineType
    content: str
    original_line_number: Optional[int] = None
    new_line_number: Optional[int] = None


@dataclass
class HunkHeader:
    """Represents a hunk header in a patch."""

    orig_start: int
    orig_count: int
    new_start: int
    new_count: int
    section_header: Optional[str] = None


@dataclass
class Hunk:
    """Represents a complete hunk in a patch with validation and application logic."""

    header: HunkHeader
    lines: List[PatchLine]

    def validate(self, file_lines: List[str], start_line: int, lenient: bool = False, tolerance: int = 5) -> int:
        """Validate hunk context against file contents with detailed error reporting.

        Args:
            file_lines (List[str]): The lines of the file to patch.
            start_line (int): The expected starting line number for the hunk.
            lenient (bool): Whether to allow lenient matching of context lines.
            tolerance (int): The number of lines to search around the expected line for context matching.

        Returns:
            int: The offset to apply to subsequent lines in the hunk.
        """
        if not file_lines:
            if self.header.orig_start > 0:
                raise PatchError("Cannot delete from empty file", {"Hunk header": self._format_header()})
            return 0

        if start_line > len(file_lines):
            raise PatchError(
                "Patch refers to lines beyond file length",
                {"File length": len(file_lines), "Start line": start_line, "Hunk header": self._format_header()},
            )

        context_lines = [line for line in self.lines if line.type in (LineType.CONTEXT, LineType.DELETION)]
        if not context_lines:  # Only additions, no context to validate
            return 0

        file_pos = start_line - 1
        offset = 0

        for patch_line in context_lines:
            expected_line = file_pos + offset
            search_start = max(0, expected_line - tolerance)
            search_end = min(len(file_lines), expected_line + tolerance + 1)

            found = False
            for i in range(search_start, search_end):
                if file_lines[i].rstrip() == patch_line.content.rstrip():
                    found = True
                    if i != expected_line:
                        offset = i - expected_line
                    break

            if not found:
                raise PatchError(
                    "Context mismatch",
                    {
                        "Expected": patch_line.content.rstrip(),
                        "Found": file_lines[expected_line].rstrip()
                        if expected_line < len(file_lines)
                        else "End of file",
                        "At line": expected_line + 1,
                        "Hunk header": self._format_header(),
                        "Offset": offset,
                    },
                )

            file_pos += 1

        return offset

    def _format_header(self) -> str:
        """Format hunk header for error messages."""
        header = (
            f"@@ -{self.header.orig_start},{self.header.orig_count} +{self.header.new_start},{self.header.new_count} @@"
        )
        if self.header.section_header:
            header += f" {self.header.section_header}"
        return header

    def apply(self, lines: List[str], start_line: int, offset: int = 0) -> List[str]:
        """Apply this hunk to the given lines."""
        result = lines[: start_line - 1 + offset]
        file_pos = start_line - 1 + offset

        for patch_line in self.lines:
            if patch_line.type == LineType.CONTEXT:
                if file_pos < len(lines):
                    result.append(lines[file_pos])
                file_pos += 1
            elif patch_line.type == LineType.ADDITION:
                result.append(patch_line.content.rstrip() + "\n")
            elif patch_line.type == LineType.DELETION:
                if file_pos < len(lines):
                    file_pos += 1

        result.extend(lines[file_pos:])
        return result


class PatchError(Exception):
    """Custom exception for patch-related errors with context."""

    def __init__(self, message: str, context: Optional[Dict] = None):
        self.context = context or {}
        super().__init__(message)

    def __str__(self):
        """Override the default exception string to include context."""
        msg = [super().__str__()]
        if self.context:
            for key, value in self.context.items():
                msg.append(f"\n{key}:")
                msg.append(f"  {str(value)}")
        return "\n".join(msg)


class Patch:
    """Represents a complete patch with enhanced parsing and validation."""

    def __init__(self, content: str):
        self.content = content
        self.hunks: List[Hunk] = []
        self.original_filename: Optional[str] = None
        self.new_filename: Optional[str] = None
        self.metadata: Dict[str, str] = {}
        self._parse()

    def _parse(self) -> None:
        """Parse the patch content with metadata and headers."""
        if not self.content:
            raise PatchError("Empty patch content")

        lines = self.content.splitlines()
        if not lines:
            raise PatchError("No lines in patch")

        if self.content.startswith("<![CDATA[") and self.content.endswith("]]>"):
            self.content = self.content[9:-3]
            lines = self.content.splitlines()

        self._parse_headers(lines)
        self._parse_hunks(lines)

        if not self.hunks:
            raise PatchError("No valid hunks found in patch")

    def _parse_headers(self, lines: List[str]) -> None:
        """Parse patch headers and metadata."""
        for line in lines:
            if line.startswith("--- "):
                self.original_filename = line[4:].split("\t")[0].strip()
            elif line.startswith("+++ "):
                self.new_filename = line[4:].split("\t")[0].strip()
            elif ":" in line:  # Possible metadata
                key, value = line.split(":", 1)
                self.metadata[key.strip()] = value.strip()

    def _parse_hunks(self, lines: List[str]) -> None:
        """Parse patch hunks with line number tracking."""
        current_hunk_lines: List[str] = []
        in_hunk = False

        for line in lines:
            if line.startswith("@@ "):
                if current_hunk_lines:
                    self._parse_hunk(current_hunk_lines)
                    current_hunk_lines = []
                in_hunk = True

            if in_hunk:
                current_hunk_lines.append(line)
            elif not (line.startswith("--- ") or line.startswith("+++ ") or line.strip() == ""):
                if ":" in line:
                    key, value = line.split(":", 1)
                    self.metadata[key.strip()] = value.strip()

        if current_hunk_lines:
            self._parse_hunk(current_hunk_lines)

    def _parse_hunk(self, lines: List[str]) -> None:
        """Parse a single hunk from its lines."""
        if not lines or not lines[0].startswith("@@ "):
            raise PatchError("Invalid hunk format", {"First line": lines[0] if lines else "No lines"})

        header = self._parse_hunk_header(lines[0])
        patch_lines: List[PatchLine] = []
        orig_line = header.orig_start
        new_line = header.new_start

        for line in lines[1:]:
            line_type = LineType.from_line(line)
            if line_type:
                content = line[1:]
                patch_line = PatchLine(line_type, content)
                if line_type in (LineType.CONTEXT, LineType.DELETION):
                    patch_line.original_line_number = orig_line
                    orig_line += 1
                if line_type in (LineType.CONTEXT, LineType.ADDITION):
                    patch_line.new_line_number = new_line
                    new_line += 1
                patch_lines.append(patch_line)

        self.hunks.append(Hunk(header, patch_lines))

    def _parse_hunk_header(self, header_line: str) -> HunkHeader:
        """Parse a hunk header line."""
        if not header_line.startswith("@@ "):
            raise PatchError("Malformed hunk header", {"Header line": header_line})

        parts = header_line.split("@@")
        if len(parts) < 3:
            raise PatchError("Malformed hunk header", {"Header line": header_line})

        ranges = parts[1].strip().split(" ")
        if len(ranges) != 2:
            raise PatchError("Malformed hunk ranges", {"Header line": header_line, "Ranges": ranges})

        orig_range = ranges[0][1:]
        new_range = ranges[1][1:]

        try:
            orig_start, orig_count = self._parse_range(orig_range)
            new_start, new_count = self._parse_range(new_range)
        except ValueError as e:
            raise PatchError(
                "Invalid range format",
                {"Header line": header_line, "Original range": orig_range, "New range": new_range, "Error": str(e)},
            )

        section_header = " ".join(parts[2:]).strip() if len(parts) > 2 else None
        return HunkHeader(orig_start, orig_count, new_start, new_count, section_header)

    def _parse_range(self, range_str: str) -> Tuple[int, int]:
        """Parse a range string (e.g., 'start,length') into start and count."""
        try:
            if "," in range_str:
                start, count = range_str.split(",")
                return int(start), int(count)
            return int(range_str), 1
        except ValueError:
            raise ValueError(f"Invalid range format: {range_str}")

    def apply_to_text(self, text: str, lenient: bool = False, tolerance: int = 5) -> str:
        """Apply the patch to the given text with enhanced error handling."""
        lines = text.splitlines(keepends=True) if text else []

        for hunk in self.hunks:
            offset = hunk.validate(lines, hunk.header.orig_start, lenient, tolerance)
            lines = hunk.apply(lines, hunk.header.orig_start, offset)

        return "".join(lines)


class UnifiedDiffTool(Tool):
    """Tool for applying unified diff patches with comprehensive error handling."""

    name: str = "unified_diff"
    description: str = "Applies a unified diff patch to update a file."
    need_validation: bool = False
    lenient: bool = True
    tolerance: int = 5
    arguments: list[ToolArgument] = [
        ToolArgument(
            name="file_path",
            arg_type="string",
            description="The path to the file to patch. Using an absolute path is recommended.",
            required=True,
            example="/path/to/file.txt",
        ),
        ToolArgument(
            name="patch",
            arg_type="string",
            description="The unified diff patch content in CDATA format.",
            required=True,
            example="<![CDATA[--- a/file.txt\n+++ b/file.txt\n@@ -1,3 +1,4 @@\n Hello, world!\n+New line!]]>",
        ),
    ]

    def execute(self, file_path: str, patch: str):
        """Apply the patch to the specified file."""
        error_context = {
            "File": file_path,
            "File exists": os.path.exists(file_path),
        }

        try:
            if os.path.exists(file_path):
                with open(file_path, encoding="utf-8") as f:
                    original_content = f.read()
                    error_context["File preview"] = (
                        original_content[:200] + "..." if len(original_content) > 200 else original_content
                    )
            else:
                original_content = ""

            patch_obj = Patch(patch)
            new_content = patch_obj.apply_to_text(original_content, lenient=self.lenient, tolerance=self.tolerance)

            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return "Patch applied successfully"

        except Exception as e:
            raise PatchError(f"Unexpected error: {str(e)}", error_context)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply a unified diff patch to a file")
    parser.add_argument("file_path", help="Path to the file to patch")
    parser.add_argument("--patch-file", help="Path to the patch file")
    parser.add_argument("--patch", help="Patch content as string")
    parser.add_argument("--lenient", action="store_true", help="Enable lenient mode for patch application")
    parser.add_argument(
        "--tolerance", type=int, default=5, help="Number of lines to search around for context matching"
    )

    args = parser.parse_args()

    if args.patch_file and args.patch:
        parser.error("Cannot specify both --patch-file and --patch")

    if args.patch_file:
        with open(args.patch_file, encoding="utf-8") as f:
            patch_content = f.read()
    elif args.patch:
        patch_content = args.patch
    else:
        parser.error("Must specify either --patch-file or --patch")

    tool = UnifiedDiffTool()
    tool.lenient = args.lenient
    tool.tolerance = args.tolerance
    try:
        result = tool.execute(args.file_path, patch_content)
        print(result)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
