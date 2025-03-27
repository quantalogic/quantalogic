# Standard library imports
import os
import sys
import subprocess
import tempfile
import traceback
from pathlib import Path
from typing import List, Tuple, Optional

# Third-party imports
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import logging

# Configure logging
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    level="DEBUG",  # Capture all log levels
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
    backtrace=True,  # Show full traceback for errors
    diagnose=True,  # Add variable values to traceback
)

# Ensure loguru captures all log levels
logging.getLogger().setLevel(logging.DEBUG)  # Capture all Python standard logging


class MermaidProcessor:
    def __init__(self, target_directory: str, filename_prefix: str):
        """
        Initialize MermaidProcessor with comprehensive setup and validation.

        Args:
            target_directory (str): Directory to save generated images
            filename_prefix (str): Prefix for generated image filenames
        """
        # Validate and normalize target directory
        self.target_dir = Path(target_directory).resolve()

        # Ensure target directory exists
        try:
            self.target_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"📂 Target directory created/verified: {self.target_dir}")
        except PermissionError:
            logger.error(f"🔒 Permission denied creating directory: {self.target_dir}")
            raise

        # Create assets subdirectory if it doesn't exist
        self.assets_dir = self.target_dir / 'assets'
        self.assets_dir.mkdir(exist_ok=True, parents=True)

        # Set filename prefix
        self.filename_prefix = filename_prefix

        # Perform initial Mermaid CLI installation check
        if not self.check_mermaid_cli_installation():
            logger.warning(
                "⚠️ Mermaid CLI is not properly installed. Image generation may fail."
            )

        # Log initialization details
        logger.info("🚀 MermaidProcessor Initialized")
        logger.debug(f"🗂️ Target Directory: {self.target_dir}")
        logger.debug(f"📝 Filename Prefix: {self.filename_prefix}")

        self.project_root = Path.cwd()
        self._validate_parameters()
        # self.check_mermaid_cli_installation()

    def _validate_parameters(self) -> None:
        """Validate and normalize input parameters with detailed checks"""
        if not self.target_dir.exists():
            raise ValueError(f"Target directory {self.target_dir} does not exist")

        if not self.target_dir.is_dir():
            raise ValueError(f"Path {self.target_dir} is not a directory")

        try:
            self.target_dir.mkdir(parents=True, exist_ok=True)
            test_file = self.target_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except OSError as e:
            raise ValueError(f"Target directory is not writable: {e}") from e

        if not re.match(r"^[a-zA-Z][\w-]{0,49}$", self.filename_prefix):
            raise ValueError(
                "Filename prefix must be 1-50 characters, start with a letter, "
                "and contain only alphanumerics, underscores, and hyphens"
            )

    @staticmethod
    def find_mermaid_blocks(content: str) -> List[Tuple[int, int]]:
        """
        Identify mermaid code blocks with stateful parsing.
        Returns list of (start_index, end_index) tuples.
        """
        blocks = []
        pattern = re.compile(
            r'''(?xm)
                ^\s*```mermaid\s*$\n
                (.*?)\n
                ^\s*```\s*$\n
            ''', re.DOTALL | re.IGNORECASE
        )

        for match in pattern.finditer(content):
            start, end = match.start(), match.end()
            blocks.append((start, end))

        if not blocks:
            logger.warning("No mermaid blocks detected")

        return blocks

    def process_content(self, markdown_content: str, parallel: bool = False) -> str:
        """Main processing method to replace Mermaid code blocks with images"""
        # Find all Mermaid code blocks
        mermaid_blocks = self.find_mermaid_blocks(markdown_content)
        
        if not mermaid_blocks:
            return markdown_content

        # Prepare to store replacements
        replacements = []

        # Process each Mermaid block
        with self._get_executor(parallel) as executor:
            futures = []
            for idx, (start, end) in enumerate(mermaid_blocks, 1):
                # Extract the Mermaid code
                code = self._extract_code(markdown_content, start, end)
                if not code:
                    continue

                # Submit image generation task
                future = executor.submit(
                    self._process_single_block,
                    code=code,
                    block_number=idx,
                    start=start,
                    end=end,
                )
                futures.append(future)

            # Collect results
            for future in as_completed(futures):
                result = future.result()
                if result:
                    replacements.append(result)

        # Apply replacements in reverse order
        for start, end, markdown_image in sorted(replacements, key=lambda x: x[0], reverse=True):
            markdown_content = markdown_content[:start] + markdown_image + markdown_content[end:]

        return markdown_content

    def _process_single_block(self, code: str, block_number: int, start: int, end: int):
        """Process individual mermaid block and generate markdown image reference"""
        try:
            # Generate image with a descriptive filename
            filename = f"{self.filename_prefix}_diagram_{block_number}"
            image_path = self.generate_image(code, filename)
            
            # If image is generated, create a markdown image reference
            if image_path:
                # Validate that the image is within the project root or assets directory
                image_path = Path(image_path).resolve()
                if (self.project_root not in image_path.parents and 
                    self.assets_dir.resolve() not in image_path.parents):
                    logger.error(f"Failed to process Mermaid block {block_number}: '{image_path}' is not in the subpath of '{self.project_root}' or '{self.assets_dir}'")
                    return None
                
                markdown_image = f"\n\n![Mermaid Diagram {block_number}](assets/{image_path.name})\n\n"
                return (start, end, markdown_image)
            
            return None
        except Exception as e:
            logger.error(f"Failed to process Mermaid block {block_number}: {e}")
            return None

    def _get_executor(self, parallel: bool):
        """Get appropriate executor based on parallel flag"""
        return (
            ThreadPoolExecutor(max_workers=os.cpu_count() * 2)
            if parallel
            else ThreadPoolExecutor(max_workers=1)
        )

    def _extract_code(self, content: str, start: int, end: int) -> Optional[str]:
        """Extract and validate mermaid code from block"""
        try:
            code_block = content[start:end]
            lines = code_block.splitlines()[1:-1]  # Remove opening/closing lines
            return "\n".join(lines).strip()
        except Exception as e:
            logger.error("Error extracting code from block: {}", e)
            return None

    def generate_image(self, code: str, filename: str, theme: str = 'default', scale: float = 2.0) -> Optional[str]:
        """
        Generate an image from Mermaid code with comprehensive logging and error handling.

        Args:
            code (str): Mermaid diagram code
            filename (str): Base filename for the output image
            theme (str, optional): Mermaid theme to use. Defaults to 'default'.
                                   Options: 'dark', 'forest', 'neutral', 'default'
            scale (float, optional): Image scale factor for high resolution. 
                                     Defaults to 2.0 for Retina-like quality.
                                     Recommended range: 1.0 to 4.0

        Returns:
            Optional[str]: Path to the generated image, or None if generation fails
        """
        try:
            # Validate Mermaid code
            if not code or not code.strip():
                logger.warning("⚠️ Empty Mermaid code block")
                return None

            # Clean and normalize Mermaid code
            code_lines = [line.strip() for line in code.split('\n') if line.strip()]
            
            # Remove any markdown code fence markers
            code_lines = [line for line in code_lines if not line.startswith('```') and not line.endswith('```')]
            
            # Strict list of allowed diagram types
            ALLOWED_DIAGRAM_TYPES = [
                'zenuml', 'flowchart', 'sequenceDiagram', 'classDiagram', 
                'stateDiagram', 'erDiagram', 'gantt', 'journey', 'gitGraph', 
                'pie', 'mindmap', 'quadrantChart', 'xychart', 'block-beta', 
                'packet-beta','graph'
            ]

            # Strict diagram type detection with support for graph variations
            diagram_type = next((line.split()[0] for line in code_lines if line.split()[0] in ALLOWED_DIAGRAM_TYPES), None)
            
            # If no allowed diagram type detected, raise an error
            if not diagram_type:
                logger.error(f"🚫 Invalid or unsupported Mermaid diagram type. Allowed types: {ALLOWED_DIAGRAM_TYPES}")
                return None

            # Reconstruct the Mermaid code with the strict diagram type
            cleaned_code = '\n'.join(code_lines)

            # Generate output path in assets directory
            output_path = self.assets_dir / f"{self.filename_prefix}_{filename}.png"
            logger.debug(f"🎯 Target Output Path: {output_path}")
            logger.debug(f"🔍 Image Scale: {scale}")

            # Ensure target directory exists
            self.assets_dir.mkdir(parents=True, exist_ok=True)

            # Create a temporary file with Mermaid code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as temp_file:
                temp_file.write(cleaned_code)
                temp_file.close()

            try:
                # Attempt to generate image using Mermaid CLI
                subprocess.run(
                    [
                        'mmdc', 
                        '-i', temp_file.name, 
                        '-o', str(output_path),
                        '-t', theme,  # Use configurable theme
                        '-b', 'transparent',  # Optional: transparent background
                        '-s', str(scale)  # Add scale parameter
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30  # 30-second timeout
                )
            except subprocess.TimeoutExpired:
                logger.error("⏰ Mermaid CLI image generation timed out")
                return None
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Mermaid CLI image generation failed: {e}")
                logger.error(f"Error Output: {e.stderr}")
                return None
            finally:
                # Clean up temporary file
                os.unlink(temp_file.name)

            # Convert to absolute path for validation
            output_path = Path(output_path)

            # Validate the output
            if not self._validate_output(output_path):
                logger.error(f"❌ Generated image validation failed: {output_path}")
                return None

            # Convert to relative path from project root
            try:
                relative_path = str(output_path.relative_to(self.project_root))
            except ValueError:
                # If not relative to project root, use absolute path
                relative_path = str(output_path)

            logger.success(f"🎉 Image generated successfully: {relative_path}")
            return relative_path

        except Exception as e:
            logger.error(f"💥 Unexpected error during image generation: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _validate_output(self, output_path: Path):
        """
        Validate generated image file with more lenient checks.
        
        Args:
            output_path (Path): Path to the generated image file
        
        Returns:
            bool: True if image is valid, False otherwise
        """
        # Check if file exists
        if not output_path.exists():
            logger.error(f"❌ Image file does not exist: {output_path}")
            return False

        # Get file stats
        try:
            file_stat = output_path.stat()
            file_size = file_stat.st_size

            # Check file size (more lenient)
            if file_size == 0:
                logger.error(f"❌ Generated image is empty: {output_path}")
                output_path.unlink(missing_ok=True)
                return False

            output_path = output_path.resolve()
            if self.target_dir.resolve() not in output_path.parents:
                logger.error(f"❌ Image file is not within project root: {output_path}")
                return False

            # Log file details
            logger.debug("📊 Image File Details:")
            logger.debug(f"  Path: {output_path}")
            logger.debug(f"  Size: {file_size} bytes")

            return True

        except Exception as e:
            logger.error(f"❌ Error validating image file: {e}")
            return False

    def check_mermaid_cli_installation(self) -> bool:
        """
        Comprehensively check Mermaid CLI installation with detailed logging.

        Returns:
            bool: True if Mermaid CLI is correctly installed, False otherwise
        """
        try:
            # Check if mmdc command exists
            result = subprocess.run(
                ["which", "mmdc"], capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0:
                logger.warning("🚫 Mermaid CLI (mmdc) not found in system PATH")
                logger.info("Installation Instructions:")
                logger.info("1. Ensure Node.js is installed: https://nodejs.org")
                logger.info("2. Install Mermaid CLI globally:")
                logger.info("   npm install -g @mermaid-js/mermaid-cli")
                logger.info("3. Verify installation with: mmdc --version")
                return False

            # Get version information
            version_result = subprocess.run(
                ["mmdc", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )

            # Log detailed version information
            logger.info("✅ Mermaid CLI Installed")
            logger.debug(f"📦 Version: {version_result.stdout.strip()}")

            # Additional system checks
            logger.debug(f"📍 Executable Path: {result.stdout.strip()}")

            return True

        except subprocess.TimeoutExpired:
            logger.error("⏰ Mermaid CLI version check timed out")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Error checking Mermaid CLI: {e}")
            logger.error(f"Error Output: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"💥 Unexpected error during Mermaid CLI check: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False


def process_markdown(
    markdown_content: str, output_directory: str, filename_prefix: str = "example", 
    theme: str = 'default', scale: float = 2.0
) -> str:
    """
    Process markdown content and generate images for Mermaid diagrams.

    Args:
        markdown_content (str): Markdown text containing Mermaid diagrams
        output_directory (str): Directory to save generated images
        filename_prefix (str, optional): Prefix for generated image filenames
        theme (str, optional): Mermaid theme to use. Defaults to 'default'.
                               Options: 'dark', 'forest', 'neutral', 'default'
        scale (float, optional): Image scale factor for high resolution. 
                                 Defaults to 2.0 for Retina-like quality.
                                 Recommended range: 1.0 to 4.0

    Returns:
        str: Processed markdown with image references
    """
    logger.info("🔍 Starting Markdown Processing")
    logger.debug(f"📂 Output Directory: {output_directory}")
    logger.debug(f"📝 Filename Prefix: {filename_prefix}")
    logger.debug(f"🎨 Mermaid Theme: {theme}")
    logger.debug(f"🔍 Image Scale: {scale}")

    # Initialize Mermaid Processor
    processor = MermaidProcessor(output_directory, filename_prefix)

    # Extract Mermaid code blocks
    mermaid_blocks = re.findall(r'\s*```mermaid\n(.*?)\s*```', markdown_content, re.DOTALL)

    logger.info(f"🧩 Found {len(mermaid_blocks)} Mermaid diagram(s)")

    # Process each Mermaid block
    for idx, mermaid_code in enumerate(mermaid_blocks, 1):
        logger.debug(f"🖼️ Processing Diagram {idx}")
        logger.debug(f"📋 Mermaid Code:\n{mermaid_code}")

        # Add explicit ER diagram syntax declaration
        mermaid_code = f'''erDiagram\n{mermaid_code}'''

        # Generate image
        try:
            image_path = processor.generate_image(
                mermaid_code.strip(), f"diagram_{idx}", theme=theme, scale=scale
            )

            if image_path:
                logger.info(f"✅ Generated image: {image_path}")

                # Replace Mermaid code block with image reference
                img_tag = f"![Diagram {idx}]({image_path})"
                markdown_content = markdown_content.replace(
                    f"```mermaid\n{mermaid_code}\n```", img_tag
                )
            else:
                logger.warning(f"❌ Failed to generate image for Diagram {idx}")

        except Exception as e:
            logger.error(f"💥 Error processing Diagram {idx}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    logger.info("🏁 Markdown Processing Complete")
    return markdown_content


if __name__ == "__main__":
    # Ensure demo directory exists
    demo_dir = Path("./demo")
    demo_dir.mkdir(parents=True, exist_ok=True)

    # Example markdown content with Mermaid diagrams
    markdown_content = """
# Example Markdown with Mermaid Diagrams

## Workflow Diagram
```mermaid
graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Process]
    B -->|No| D[Stop]
    C --> E[Validate]
    E --> F[Complete]
```

## Sequence Diagram
        ```mermaid
        sequenceDiagram
            participant Alice
            participant Bob
            Alice->>Bob: Hello
            Bob-->>Alice: Hi there!
        ```
## Erd Diagram

```mermaid
erDiagram
    CUSTOMER {
        string customerId PK
        string name
        string email
        string address
    }
    ORDER {
        string orderId PK
        string customerId FK
        datetime orderDate
        string shippingAddress
    }
    CUSTOMER ||--o{ ORDER : places
```

## ZenUML

```mermaid
zenuml
    title Order Service
    @Actor Client #FFEBE6
    @Boundary OrderController #0747A6
    @EC2 <<BFF>> OrderService #E3FCEF
    group BusinessService {
      @Lambda PurchaseService
      @AzureFunction InvoiceService
    }

    @Starter(Client)
    // `POST /orders`
    OrderController.post(payload) {
      OrderService.create(payload) {
        order = new Order(payload)
        if(order != null) {
          par {
            PurchaseService.createPO(order)
            InvoiceService.createInvoice(order)      
          }      
        }
      }
    }
```    

"""

    # Input markdown file path
    input_markdown_path = demo_dir / "markdown.md"
    output_markdown_path = demo_dir / "markdown_updated.md"

    # Save original markdown
    with open(input_markdown_path, 'w') as f:
        f.write(markdown_content)
    logger.info(f"Saved original markdown to: {input_markdown_path}")

    # Initialize Mermaid Processor
    output_directory = str(demo_dir)
    filename_prefix = "demo"
    processor = MermaidProcessor(output_directory, filename_prefix)

    # Process markdown content
    processed_markdown = processor.process_content(markdown_content)

    # Save processed markdown
    with open(output_markdown_path, 'w') as f:
        f.write(processed_markdown)
    logger.info(f"Saved processed markdown to: {output_markdown_path}")
