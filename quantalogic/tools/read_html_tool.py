import os
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import BaseModel, Field, field_validator

# Ensure that markdownify is installed: pip install markdownify
try:
    from markdownify import markdownify as md
except ImportError:
    logger.error("Missing dependency: markdownify. Install it using 'pip install markdownify'")
    raise

# Assuming Tool and ToolArgument are properly defined in quantalogic.tools.tool
from quantalogic.tools.tool import Tool, ToolArgument

# User-Agent list to mimic different browsers
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.124 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.124 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)"
    " Version/14.1.1 Safari/605.1.15",
]

# Additional headers to mimic real browser requests
ADDITIONAL_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;" "q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",  # Do Not Track
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
}


class ReadHTMLTool(Tool):
    """Tool for reading HTML content from files or URLs in specified line ranges."""

    class Arguments(BaseModel):
        source: str = Field(
            ..., description="The file path or URL to read HTML from", example="https://example.com or ./example.html"
        )
        convert: Optional[str] = Field(
            "text",
            description="Convert input to 'text' (Markdown) or 'html' no conversion. Default is 'text'",
            example="'text' or 'html'",
        )
        line_start: Optional[int] = Field(
            1, description="The starting line number (1-based index). Default: 1", ge=1, example="1"
        )
        line_end: Optional[int] = Field(
            300, description="The ending line number (1-based index). Default: 300", ge=1, example="300"
        )

        @field_validator("convert")
        def validate_convert(cls, v):
            if v not in ["text", "html"]:
                raise ValueError("Convert must be either 'text' or 'html'")
            return v

        @field_validator("line_end")
        def validate_line_end(cls, v, values):
            if "line_start" in values and v < values["line_start"]:
                raise ValueError("line_end must be greater than or equal to line_start")
            return v

    name: str = "read_html_tool"
    description: str = (
        "Reads HTML content from either a file path or URL in specified line ranges. "
        "Returns parsed HTML content using BeautifulSoup or converts it to Markdown. "
        "Allows reading specific portions of HTML files by defining start and end lines."
    )
    arguments: list = [
        ToolArgument(
            name="source",
            arg_type="string",
            description="The file path or URL to read HTML from",
            required=True,
            example="https://example.com or ./example.html",
        ),
        ToolArgument(
            name="convert",
            arg_type="string",
            description="Convert input to 'text' (Markdown) or 'html'. Default is 'text'",
            default="text",
            required=False,
            example="'text' or 'html'",
        ),
        ToolArgument(
            name="line_start",
            arg_type="int",
            description="The starting line number (1-based index). Default: 1",
            required=False,
            example="1",
            default="1",
        ),
        ToolArgument(
            name="line_end",
            arg_type="int",
            description="The ending line number (1-based index). Default: 300",
            required=False,
            example="300",
            default="300",
        ),
    ]

    def validate_source(self, source: str) -> bool:
        """Validate if source is a valid file path or URL."""
        if os.path.isfile(source):
            return True
        try:
            result = requests.utils.urlparse(source)
            return all([result.scheme, result.netloc])
        except (requests.exceptions.RequestException, ValueError) as e:
            # Log the specific exception for debugging
            logger.debug(f"URL validation failed: {e}")
            return False

    def read_from_file(self, file_path: str) -> str:
        """Read HTML content from a file."""
        try:
            with open(file_path, encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            raise ValueError(f"Error reading file: {e}")

    def read_from_url(self, url: str) -> str:
        """Read HTML content from a URL with randomized User-Agent and headers."""
        try:
            # Randomize User-Agent
            headers = ADDITIONAL_HEADERS.copy()
            headers["User-Agent"] = random.choice(USER_AGENTS)

            # Add a small random delay to mimic human behavior
            time.sleep(random.uniform(0.5, 2.0))

            # Use a timeout to prevent hanging
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            raise ValueError(f"Error fetching URL: {e}")

    def parse_html(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content using BeautifulSoup."""
        try:
            return BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            raise ValueError(f"Error parsing HTML: {e}")

    def read_source(self, source: str) -> str:
        """Read entire content from source."""
        if os.path.isfile(source):
            return self.read_from_file(source)
        else:
            return self.read_from_url(source)

    def _convert_content(self, content: str, convert_type: str) -> str:
        """
        Convert content based on the specified type.

        Args:
            content (str): The input content to convert
            convert_type (str): The type of conversion to perform

        Returns:
            str: Converted content
        """
        if convert_type == "text":
            # Convert HTML to Markdown using markdownify
            try:
                markdown_content = md(content, heading_style="ATX")
                return markdown_content
            except Exception as e:
                logger.error(f"Error converting HTML to Markdown: {e}")
                raise ValueError(f"Error converting HTML to Markdown: {e}")

        if convert_type == "html":
            # Ensure content is valid HTML
            try:
                soup = BeautifulSoup(content, "html.parser")
                return soup.prettify()
            except Exception as e:
                logger.error(f"Error prettifying HTML: {e}")
                raise ValueError(f"Error prettifying HTML: {e}")

        return content

    def execute(self, source: str, convert: Optional[str] = "text", line_start: int = 1, line_end: int = 300) -> str:
        """Execute the tool to read and parse HTML content in specified line ranges."""
        logger.debug(f"Executing read_html_tool with source: {source}")

        line_start = int(line_start)
        line_end = int(line_end)

        if not self.validate_source(source):
            logger.warning(f"Invalid source: {source}")
            return f"Invalid source: {source}"

        try:
            # Step 1: Read entire content from source
            raw_content = self.read_source(source)

            # Step 2: Convert content
            converted_content = self._convert_content(raw_content, convert)

            # Step 3: Split converted content into lines
            lines = converted_content.splitlines()
            total_lines = len(lines)

            # Step 4: Adjust line_end if it exceeds total_lines
            adjusted_end_line = min(line_end, total_lines)

            # Step 5: Slice lines based on line_start and adjusted_end_line
            sliced_lines = lines[line_start - 1 : adjusted_end_line]
            sliced_content = "\n".join(sliced_lines)

            # Step 6: Calculate actual_end_line based on lines returned
            if sliced_lines:
                actual_end_line = line_start + len(sliced_lines) - 1
            else:
                actual_end_line = line_start

            # Step 7: Determine if this is the last block
            is_last_block = actual_end_line >= total_lines

            # Step 8: Calculate total lines returned
            total_lines_returned = len(sliced_lines)

            # Prepare detailed output
            result = [
                f"==== Source: {source} ====",
                f"==== Lines: {line_start} - {actual_end_line} of {total_lines} ====",
                "==== Block Detail ====",
                f"Start Line: {line_start}",
                f"End Line: {actual_end_line}",
                f"Total Lines Returned: {total_lines_returned}",
                f"Is Last Block: {'Yes' if is_last_block else 'No'}",
                "==== Content ====",
                sliced_content,
                "==== End of Block ====",
            ]

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Unexpected error processing source {source}: {e}")
            return f"Unexpected error: {e}"


if __name__ == "__main__":
    tool = ReadHTMLTool()

    # Since to_markdown() is not defined, we'll comment it out.
    # print(tool.to_markdown())

    # Test with a known working URL
    try:
        result = tool.execute(source="https://www.quantalogic.app", line_start=1, line_end=100)
        print("URL Test Result:")
        print(result)
    except Exception as e:
        print(f"URL Test Failed: {e}")

    # Test with local file (if available)
    try:
        local_file = os.path.join(os.path.dirname(__file__), "test.html")
        if os.path.exists(local_file):
            result = tool.execute(source=local_file, line_start=1, line_end=1000)
            print("Local File Test Result:")
            print(result)
        else:
            print("No local test file found.")
    except Exception as e:
        print(f"Local File Test Failed: {e}")
