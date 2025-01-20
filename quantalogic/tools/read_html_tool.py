import os
import random
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import field_validator

from quantalogic.tools.tool import Tool, ToolArgument

# Add User-Agent list to mimic different browsers
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
]

# Additional headers to make requests look more like a real browser
ADDITIONAL_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",  # Do Not Track
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0"
}


class ReadHTMLTool(Tool):
    """Tool for reading HTML content from files or URLs in blocks."""
    
    name: str = "read_html_tool"
    description: str = (
        "Reads HTML content from either a file path or URL in blocks. "
        "Returns parsed HTML content using BeautifulSoup. "
        "Can read specific portions of HTML files in blocks of lines."
    )
    arguments: list = [
        ToolArgument(
            name="source",
            arg_type="string",
            description="The file path or URL to read HTML from",
            required=True,
            example="https://example.com or ./example.html"
        ),
        ToolArgument(
            name="line_start",
            arg_type="int",
            description="The starting line number (1-based index). Default: 0",
            required=False,
            example="0"
        ),
        ToolArgument(
            name="line_end",
            arg_type="int",
            description="The ending line number (1-based index). Default: 300",
            required=False,
            example="300"
        )
    ]

    def validate_source(self, source: str) -> bool:
        """Validate if source is a valid file path or URL."""
        if os.path.isfile(source):
            return True
        try:
            result = urlparse(source)
            return all([result.scheme, result.netloc])
        except:
            return False

    def read_from_file(self, file_path: str) -> Optional[str]:
        """Read HTML content from a file."""
        try:
            with open(file_path, encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            raise ValueError(f"Error reading file: {e}")

    def read_from_url(self, url: str) -> Optional[str]:
        """Read HTML content from a URL with randomized User-Agent and headers."""
        try:
            # Randomize User-Agent
            headers = ADDITIONAL_HEADERS.copy()
            headers["User-Agent"] = random.choice(USER_AGENTS)
            
            # Add a small random delay to mimic human behavior
            import time
            time.sleep(random.uniform(0.5, 2.0))
            
            # Use a timeout to prevent hanging
            response = requests.get(
                url, 
                headers=headers, 
                timeout=10,
                allow_redirects=True
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            raise ValueError(f"Error fetching URL: {e}")

    def parse_html(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content using BeautifulSoup."""
        try:
            return BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            raise ValueError(f"Error parsing HTML: {e}")

    @field_validator("line_start", "line_end", check_fields=False)
    @classmethod
    def validate_line_numbers(cls, v: Optional[int], info) -> Optional[int]:
        """
        Validate line numbers with robust error handling.
        
        Args:
            v (Optional[int]): Line number to validate
            info: Validation context information
        
        Returns:
            Optional[int]: Validated line number
        
        Raises:
            ValueError: If line number is invalid
        """
        # If no value is provided, return None
        if v is None:
            return None
        
        # Ensure the value is an integer
        try:
            line_number = int(v)
        except (TypeError, ValueError):
            logger.error(f"Invalid line number: {v}. Must be an integer.")
            raise ValueError(f"Line number must be an integer, got {type(v).__name__}")
        
        # Validate line number is non-negative
        if line_number < 0:
            logger.error(f"Negative line number not allowed: {line_number}")
            raise ValueError(f"Line number must be non-negative, got {line_number}")
        
        logger.debug(f"Validated line number: {line_number}")
        return line_number

    def execute(self, source: str, line_start: int = 0, line_end: int = 300) -> str:
        """Execute the tool to read and parse HTML content in blocks."""
        logger.debug(f"Executing read_html_tool with source: {source}")
        
        if not self.validate_source(source):
            raise ValueError("Invalid source. Must be a valid file path or URL")

        try:
            # Validate line numbers
            line_start = self.validate_line_numbers(line_start, {})
            line_end = self.validate_line_numbers(line_end, {})

            # Read content
            if os.path.isfile(source):
                with open(source, encoding='utf-8') as file:
                    lines = file.readlines()
                    total_lines = len(lines)
                    block = lines[line_start:line_end + 1]
                    html_content = ''.join(block)
            else:
                # Improved URL reading with more robust error handling
                try:
                    html_content = self.read_from_url(source)
                    lines = html_content.splitlines()
                    total_lines = len(lines)
                except Exception as url_error:
                    logger.error(f"Failed to read URL {source}: {url_error}")
                    # If URL reading fails, return an error message
                    return f"Error reading URL: {url_error}"

                # Apply line filtering if specific lines are requested
                if line_start != 0 or line_end != 300:
                    block = lines[line_start:line_end + 1]
                    html_content = '\n'.join(block)

            # Check if content is empty
            if not html_content.strip():
                logger.warning(f"No content retrieved from source: {source}")
                return f"No content found in source: {source}"

            # Parse HTML
            soup = self.parse_html(html_content)
            is_last_block = (line_end >= total_lines - 1) if total_lines > 0 else True
            
            result = [
                f"==== Source: {source} ====",
                f"==== Lines: {line_start}-{min(line_end, total_lines - 1)} of {total_lines} ====",
                "==== Content ====",
                soup.prettify(),
                "==== End of Block ====" + (" [LAST BLOCK]" if is_last_block else "")
            ]
            
            return "\n".join(result)
        except Exception as e:
            logger.error(f"Unexpected error processing source {source}: {e}")
            return f"Unexpected error: {e}"

if __name__ == "__main__":
    tool = ReadHTMLTool()
    print(tool.to_markdown())
    
    # Test with a known working URL
    try:
        result = tool.execute(source="https://www.python.org", line_start=1, line_end=100)
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
