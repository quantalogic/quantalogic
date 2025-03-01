"""Tool for converting markdown content to well-structured ePub documents.

Why this tool:
- Provides a standardized way to convert markdown to professional ePub books
- Supports rich formatting and interactive elements
- Creates responsive e-books that work on all devices
- Handles chapters, table of contents, and metadata
- Includes support for custom styling and themes
"""

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

import markdown
import mermaid
from bs4 import BeautifulSoup
from ebooklib import epub
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class MarkdownToEpubTool(Tool):
    """Converts markdown to professional EPUB documents with advanced formatting."""

    model_config = {
        "arbitrary_types_allowed": True
    }
    
    name: str = "markdown_to_epub_tool"
    description: str = (
        "Converts markdown to EPUB with support for images, Mermaid diagrams, "
        "code blocks, tables, and advanced styling."
    )
    need_validation: bool = False
    
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="markdown_content",
            arg_type="string",
            description="Markdown content with optional chapter separators (---)",
            required=True,
            example="# Book Title\n\n## Chapter 1\n\nContent...\n\n---\n\n## Chapter 2\n\nMore content...",
        ),
        ToolArgument(
            name="output_path",
            arg_type="string",
            description="Path for saving the EPUB file",
            required=True,
            example="/path/to/output.epub",
        ),
        ToolArgument(
            name="metadata",
            arg_type="string",
            description="JSON string with book metadata",
            required=False,
            example='{"title": "My Book", "author": "John Doe", "language": "en"}',
        ),
        ToolArgument(
            name="cover_image",
            arg_type="string",
            description="Path to cover image file",
            required=False,
            example="path/to/cover.jpg",
        ),
        ToolArgument(
            name="style_config",
            arg_type="string",
            description="JSON string with style settings",
            required=False,
            example='{"theme": "light", "font_family": "Literata"}',
        ),
    ]

    # Default style configuration
    DEFAULT_CSS: ClassVar[str] = """
        @import url('https://fonts.googleapis.com/css2?family=Literata:ital,wght@0,400;0,600;1,400&family=Source+Code+Pro&display=swap');

        :root {
            color-scheme: %(theme)s;
        }

        body {
            font-family: %(font_family)s;
            line-height: %(line_height)s;
            color: %(text_color)s;
            background-color: %(background_color)s;
            margin: 0 auto;
            max-width: %(max_width)s;
            padding: 1em;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: %(heading_font)s;
            color: %(heading_color)s;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }

        a {
            color: %(link_color)s;
            text-decoration: none;
        }

        pre, code {
            font-family: %(code_font)s;
            background-color: #f6f8fa;
            border-radius: 3px;
            font-size: 0.9em;
        }

        pre {
            padding: 1em;
            overflow-x: auto;
            line-height: 1.45;
        }

        code {
            padding: 0.2em 0.4em;
        }

        img {
            max-width: 100%%;
            height: auto;
            display: block;
            margin: 1em auto;
        }

        blockquote {
            margin: 1em 0;
            padding-left: 1em;
            border-left: 4px solid %(link_color)s;
            color: #666666;
        }

        table {
            width: 100%%;
            border-collapse: collapse;
            margin: 1em 0;
        }

        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }

        th {
            background-color: #f6f8fa;
        }

        .chapter-title {
            text-align: center;
            margin-top: 3em;
            margin-bottom: 2em;
        }

        .chapter {
            break-before: page;
        }

        @media (prefers-color-scheme: dark) {
            body {
                background-color: #1a1a1a;
                color: #e6e6e6;
            }

            pre, code {
                background-color: #2d2d2d;
            }

            th {
                background-color: #2d2d2d;
            }

            blockquote {
                color: #b3b3b3;
            }
        }
    """

    DEFAULT_STYLES: ClassVar[Dict[str, str]] = {
        "theme": "light",
        "font_family": "'Literata', Georgia, serif",
        "heading_font": "'Literata', Georgia, serif",
        "code_font": "'Source Code Pro', monospace",
        "line_height": "1.6",
        "max_width": "45em",
        "text_color": "#333333",
        "heading_color": "#222222",
        "link_color": "#0366d6",
        "background_color": "#ffffff"
    }

    def _normalize_path(self, path: str) -> Path:
        """Convert path string to normalized Path object."""
        if path.startswith("~"):
            path = os.path.expanduser(path)
        return Path(path).resolve()

    def _parse_style_config(self, style_config: Optional[str]) -> Dict[str, str]:
        """Parse and validate style configuration."""
        try:
            if not style_config:
                return self.DEFAULT_STYLES.copy()
            
            custom_styles = json.loads(style_config)
            styles = self.DEFAULT_STYLES.copy()
            styles.update(custom_styles)
            return styles
        except json.JSONDecodeError as e:
            logger.error(f"Invalid style configuration JSON: {e}")
            return self.DEFAULT_STYLES.copy()

    def _process_mermaid_diagrams(self, html_content: str, temp_dir: Path) -> str:
        """Convert Mermaid diagram code blocks to SVG images."""
        soup = BeautifulSoup(html_content, 'html.parser')
        mermaid_blocks = soup.find_all('code', class_='language-mermaid')
        
        for block in mermaid_blocks:
            try:
                diagram = mermaid.generate_diagram(block.text)
                img_name = f"diagram_{hash(block.text)}.svg"
                img_path = temp_dir / img_name
                
                with open(img_path, 'wb') as f:
                    f.write(diagram)
                
                img_tag = soup.new_tag('img')
                img_tag['src'] = img_name
                img_tag['alt'] = 'Diagram'
                block.parent.replace_with(img_tag)
            except Exception as e:
                logger.error(f"Error processing Mermaid diagram: {e}")
                
        return str(soup)

    def _split_chapters(self, content: str) -> List[Dict[str, str]]:
        """Split markdown content into chapters."""
        chapters = []
        current_chapter = []
        current_title = "Untitled Chapter"

        for line in content.split('\n'):
            if line.strip() == '---':
                if current_chapter:
                    chapters.append({
                        'title': current_title,
                        'content': '\n'.join(current_chapter)
                    })
                    current_chapter = []
                    current_title = "Untitled Chapter"
            else:
                if line.startswith('# '):
                    current_title = line[2:].strip()
                current_chapter.append(line)

        if current_chapter:
            chapters.append({
                'title': current_title,
                'content': '\n'.join(current_chapter)
            })

        return chapters

    def _create_nav_page(self, chapters: List[Dict[str, str]]) -> epub.EpubHtml:
        """Create table of contents navigation page."""
        content = """
            <h1>Table of Contents</h1>
            <nav epub:type="toc">
                <ol>
        """
        
        for i, chapter in enumerate(chapters, 1):
            content += f'<li><a href="chapter_{i}.xhtml">{chapter["title"]}</a></li>'
        
        content += """
                </ol>
            </nav>
        """
        
        nav = epub.EpubHtml(
            title='Table of Contents',
            file_name='nav.xhtml',
            content=content
        )
        return nav

    def execute(self, **kwargs) -> str:
        """Execute the markdown to EPUB conversion.
        
        Args:
            **kwargs: Tool arguments including markdown_content, output_path,
                     metadata, cover_image, and style_config
        
        Returns:
            Success message with output path
        """
        try:
            markdown_content = kwargs['markdown_content']
            output_path = self._normalize_path(kwargs['output_path'])
            metadata = json.loads(kwargs.get('metadata', '{}'))
            cover_image = kwargs.get('cover_image')
            style_config = kwargs.get('style_config')

            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create temporary directory for assets
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Initialize EPUB book
                book = epub.EpubBook()

                # Set metadata
                book.set_identifier(str(uuid.uuid4()))
                book.set_title(metadata.get('title', 'Untitled'))
                book.set_language(metadata.get('language', 'en'))
                book.add_author(metadata.get('author', 'Unknown'))
                book.set_cover('cover.jpg', open(cover_image, 'rb').read()) if cover_image else None

                # Parse style configuration
                styles = self._parse_style_config(style_config)
                css_content = self.DEFAULT_CSS % styles

                # Add CSS
                style = epub.EpubItem(
                    uid="style",
                    file_name="style.css",
                    media_type="text/css",
                    content=css_content
                )
                book.add_item(style)

                # Split content into chapters
                chapters = self._split_chapters(markdown_content)
                epub_chapters = []

                # Process chapters
                for i, chapter in enumerate(chapters, 1):
                    # Convert markdown to HTML
                    html_content = markdown.markdown(
                        chapter['content'],
                        extensions=['extra', 'codehilite', 'tables', 'fenced_code']
                    )

                    # Process Mermaid diagrams
                    html_content = self._process_mermaid_diagrams(html_content, temp_path)

                    # Create chapter
                    epub_chapter = epub.EpubHtml(
                        title=chapter['title'],
                        file_name=f'chapter_{i}.xhtml',
                        content=f'''
                            <h1 class="chapter-title">{chapter['title']}</h1>
                            <div class="chapter">
                                {html_content}
                            </div>
                        '''
                    )
                    epub_chapter.add_item(style)
                    book.add_item(epub_chapter)
                    epub_chapters.append(epub_chapter)

                # Add navigation
                book.toc = [(epub.Section(chapter['title']), [c]) 
                           for chapter, c in zip(chapters, epub_chapters)]
                
                # Add navigation page
                nav = self._create_nav_page(chapters)
                book.add_item(nav)
                
                # Basic spine
                book.spine = ['nav'] + epub_chapters

                # Add any images from temp directory
                for img_path in temp_path.glob('*.svg'):
                    with open(img_path, 'rb') as f:
                        epub_image = epub.EpubItem(
                            uid=f"image_{img_path.stem}",
                            file_name=img_path.name,
                            media_type="image/svg+xml",
                            content=f.read()
                        )
                        book.add_item(epub_image)

                # Write EPUB file
                epub.write_epub(str(output_path), book, {})

            return f"Successfully created EPUB at: {output_path}"

        except Exception as e:
            error_msg = f"Error converting markdown to EPUB: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


if __name__ == "__main__":
    # Example usage with error handling
    try:
        tool = MarkdownToEpubTool()
        result = tool.execute(
            markdown_content="""
            # My Book
            
            ## Chapter 1: Introduction
            
            This is the first chapter with some **bold** text and a diagram:
            
            ```mermaid
            graph TD
                A[Start] --> B[Process]
                B --> C[End]
            ```
            
            ---
            
            ## Chapter 2: Development
            
            This is the second chapter with a code block:
            
            ```python
            def hello():
                print("Hello, World!")
            ```
            """,
            output_path="my_book.epub",
            metadata='{"title": "My Book", "author": "John Doe"}',
            style_config='{"theme": "light", "font_family": "Literata"}'
        )
        print(result)
    except Exception as e:
        print(f"Error: {e}")
