"""Tool for converting markdown content to well-structured LaTeX documents.

Why this tool:
- Provides a standardized way to convert markdown to professional LaTeX documents
- Supports mathematical equations and scientific content
- Handles citations, references, and bibliographies
- Maintains consistent academic formatting
- Supports custom document classes and packages
"""

import json
import os
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Union

import mermaid
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class MarkdownToLatexTool(Tool):
    """Converts markdown to professional LaTeX documents with advanced formatting."""

    model_config = {
        "arbitrary_types_allowed": True
    }
    
    name: str = "markdown_to_latex_tool"
    description: str = (
        "Converts markdown to LaTeX with support for images, Mermaid diagrams, "
        "code blocks, tables, and advanced formatting."
    )
    need_validation: bool = False
    
    arguments: List[ToolArgument] = [
        ToolArgument(
            name="markdown_content",
            arg_type="string",
            description="Markdown content with support for LaTeX equations, citations, and academic formatting",
            required=True,
            example="# Title\n\nEquation: $E=mc^2$\n\nCite: [@einstein1905]",
        ),
        ToolArgument(
            name="output_path",
            arg_type="string",
            description="Path for saving the LaTeX file",
            required=True,
            example="/path/to/output.tex",
        ),
        ToolArgument(
            name="document_class",
            arg_type="string",
            description="LaTeX document class (article, report, book)",
            required=False,
            default="article",
        ),
        ToolArgument(
            name="bibliography_file",
            arg_type="string",
            description="Optional path to BibTeX file",
            required=False,
            example="path/to/references.bib",
        ),
        ToolArgument(
            name="style_config",
            arg_type="string",
            description="JSON string with style settings and packages",
            required=False,
            example='{"font_size": "12pt", "packages": ["amsmath", "graphicx"]}',
        ),
    ]

    DOCUMENT_TEMPLATE: ClassVar[str] = r"""\documentclass[{font_size},{paper_size}]{article}

% Packages
{packages}

% Document settings
\usepackage[{margin}]{geometry}
\usepackage{{font_package}}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}

% Hyperref settings
\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,
    urlcolor=cyan,
    pdftitle={{title}}
}

\setlength{\parskip}{1em}
\renewcommand{\baselinestretch}{line_spacing}

{extra_preamble}

\begin{document}

{content}

{bibliography}

\end{document}
"""

    DEFAULT_PACKAGES: ClassVar[List[str]] = [
        "graphicx",
        "hyperref",
        "listings",
        "xcolor",
        "amsmath",
        "amssymb",
        "booktabs",
        "float",
        "caption",
        "subcaption",
        "fancyhdr",
        "titlesec",
        "enumitem",
        "microtype",
    ]

    DEFAULT_STYLES: ClassVar[Dict[str, Union[str, float, List[str]]]] = {
        "font_size": "12pt",
        "paper_size": "a4paper",
        "margin": "margin=1in",
        "font_package": "lmodern",
        "line_spacing": 1.15,
        "code_style": {
            "basicstyle": r"\ttfamily\small",
            "breaklines": "true",
            "commentstyle": r"\color{gray}",
            "keywordstyle": r"\color{blue}",
            "stringstyle": r"\color{green!50!black}",
            "numberstyle": r"\tiny\color{gray}",
            "frame": "single",
            "rulecolor": r"\color{black!30}",
            "backgroundcolor": r"\color{gray!5}",
        }
    }

    def _normalize_path(self, path: str) -> Path:
        """Convert path string to normalized Path object."""
        if path.startswith("~"):
            path = os.path.expanduser(path)
        return Path(path).resolve()

    def _parse_style_config(self, style_config: Optional[str]) -> Dict[str, Any]:
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

    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters."""
        chars = {
            '&': '\\&',
            '%': '\\%',
            '$': '\\$',
            '#': '\\#',
            '_': '\\_',
            '{': '\\{',
            '}': '\\}',
            '~': '\\textasciitilde{}',
            '^': '\\textasciicircum{}',
            '\\': '\\textbackslash{}',
        }
        pattern = '|'.join(map(re.escape, chars.keys()))
        return re.sub(pattern, lambda m: chars[m.group()], text)

    def _convert_math(self, text: str) -> str:
        """Convert markdown math to LaTeX math."""
        # Inline math
        text = re.sub(r'\$([^$]+)\$', r'$\1$', text)
        # Display math
        text = re.sub(r'\$\$([^$]+)\$\$', r'\\[\1\\]', text)
        return text

    def _convert_code_blocks(self, text: str) -> str:
        """Convert markdown code blocks to LaTeX listings."""
        def replace_code(match):
            code = match.group(2)
            lang = match.group(1) if match.group(1) else ''
            return (
                f"\\begin{{lstlisting}}[language={lang}, "
                "basicstyle=\\ttfamily\\small, "
                "breaklines=true, "
                "commentstyle=\\color{gray}, "
                "keywordstyle=\\color{blue}, "
                "stringstyle=\\color{green}, "
                "numbers=left, "
                "frame=single]\n"
                f"{code}\n"
                "\\end{lstlisting}\n"
            )
        
        return re.sub(
            r'```(\w+)?\n(.*?)\n```',
            replace_code,
            text,
            flags=re.DOTALL
        )

    def _convert_tables(self, text: str) -> str:
        """Convert markdown tables to LaTeX tables."""
        def convert_table(match):
            lines = match.group(0).split('\n')
            header = lines[0].strip('|').split('|')
            alignment = lines[1].strip('|').split('|')
            data = [line.strip('|').split('|') for line in lines[2:] if line.strip()]
            
            # Determine column alignment
            col_align = []
            for col in alignment:
                col = col.strip()
                if col.startswith(':') and col.endswith(':'):
                    col_align.append('c')
                elif col.endswith(':'):
                    col_align.append('r')
                else:
                    col_align.append('l')
            
            # Build LaTeX table
            latex = "\\begin{table}[H]\n\\centering\n\\begin{tabular}"
            latex += "{" + "".join(col_align) + "}\n"
            latex += "\\toprule\n"
            latex += " & ".join(h.strip() for h in header) + " \\\\\n"
            latex += "\\midrule\n"
            for row in data:
                latex += " & ".join(cell.strip() for cell in row) + " \\\\\n"
            latex += "\\bottomrule\n"
            latex += "\\end{tabular}\n\\end{table}\n"
            
            return latex
        
        pattern = r'\|.+\|\n\|[-:| ]+\|\n(?:\|.+\|\n?)+'
        return re.sub(pattern, convert_table, text)

    def _process_citations(self, text: str, bib_file: Optional[Path]) -> tuple[str, bool]:
        """Process markdown citations and return updated text and citation flag."""
        has_citations = False
        
        if bib_file and bib_file.exists():
            # Convert [@citation] to \cite{citation}
            text = re.sub(r'\[@([^\]]+)\]', r'\\cite{\1}', text)
            has_citations = bool(re.search(r'\\cite{', text))
        
        return text, has_citations

    def _process_mermaid_diagrams(self, text: str, output_dir: Path) -> str:
        """Convert Mermaid diagrams to TikZ or image figures."""
        def replace_mermaid(match):
            try:
                diagram = mermaid.generate_diagram(match.group(1))
                img_path = output_dir / f"diagram_{hash(match.group(1))}.pdf"
                
                # Save diagram as PDF
                with open(img_path, 'wb') as f:
                    f.write(diagram)
                
                return (
                    "\\begin{figure}[H]\n"
                    "\\centering\n"
                    f"\\includegraphics[width=0.8\\textwidth]{{{img_path}}}\n"
                    "\\caption{Generated diagram}\n"
                    "\\end{figure}\n"
                )
            except Exception as e:
                logger.error(f"Error processing Mermaid diagram: {e}")
                return "% Error processing diagram\n"
        
        return re.sub(
            r'```mermaid\n(.*?)\n```',
            replace_mermaid,
            text,
            flags=re.DOTALL
        )

    def execute(self, **kwargs) -> str:
        """Execute the markdown to LaTeX conversion.
        
        Args:
            **kwargs: Tool arguments including markdown_content, output_path,
                     document_class, bibliography_file, and style_config
        
        Returns:
            Success message with output path
        """
        try:
            markdown_content = kwargs['markdown_content']
            output_path = self._normalize_path(kwargs['output_path'])
            document_class = kwargs.get('document_class', 'article')
            bib_file = kwargs.get('bibliography_file')
            style_config = kwargs.get('style_config')

            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Parse style configuration
            styles = self._parse_style_config(style_config)

            # Process content
            content = markdown_content

            # Convert math expressions
            content = self._convert_math(content)

            # Process citations
            bib_path = self._normalize_path(bib_file) if bib_file else None
            content, has_citations = self._process_citations(content, bib_path)

            # Convert code blocks
            content = self._convert_code_blocks(content)

            # Convert tables
            content = self._convert_tables(content)

            # Process Mermaid diagrams
            content = self._process_mermaid_diagrams(content, output_path.parent)

            # Extract title
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else 'Document'
            content = re.sub(r'^#\s+(.+)$', r'\\title{\1}\n\\maketitle', content, flags=re.MULTILINE)

            # Convert headers
            content = re.sub(r'^#{6}\s+(.+)$', r'\\paragraph{\1}', content, flags=re.MULTILINE)
            content = re.sub(r'^#{5}\s+(.+)$', r'\\subsubsection{\1}', content, flags=re.MULTILINE)
            content = re.sub(r'^#{4}\s+(.+)$', r'\\subsection{\1}', content, flags=re.MULTILINE)
            content = re.sub(r'^#{3}\s+(.+)$', r'\\section{\1}', content, flags=re.MULTILINE)
            content = re.sub(r'^#{2}\s+(.+)$', r'\\section{\1}', content, flags=re.MULTILINE)

            # Convert emphasis
            content = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', content)
            content = re.sub(r'\*(.+?)\*', r'\\textit{\1}', content)

            # Convert links
            content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\\href{\2}{\1}', content)

            # Generate package includes
            packages = '\n'.join(f"\\usepackage{{{pkg}}}" for pkg in self.DEFAULT_PACKAGES)

            # Generate bibliography settings
            bibliography = ""
            if has_citations and bib_path and bib_path.exists():
                bibliography = (
                    f"\\bibliographystyle{{{styles['bibliography_style']}}}\n"
                    f"\\bibliography{{{bib_path.stem}}}"
                )

            # Generate final LaTeX
            latex_content = self.DOCUMENT_TEMPLATE.format(
                font_size=styles['font_size'],
                paper_size=styles['paper_size'],
                margin=styles['margin'],
                font_package=styles['font_package'],
                packages=packages,
                title=title,
                line_spacing=styles['line_spacing'],
                extra_preamble="",
                content=content,
                bibliography=bibliography
            )

            # Write output file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)

            return f"Successfully created LaTeX document at: {output_path}"

        except Exception as e:
            error_msg = f"Error converting markdown to LaTeX: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


if __name__ == "__main__":
    # Example usage with error handling
    try:
        tool = MarkdownToLatexTool()
        result = tool.execute(
            markdown_content="""
            # Sample Academic Document
            
            ## Introduction
            
            This is a sample document with an equation:
            
            $$E = mc^2$$
            
            And a citation [@einstein1905].
            
            ```python
            def calculate_energy(mass):
                c = 299792458  # speed of light
                return mass * (c ** 2)
            ```
            
            | Column 1 | Column 2 |
            |:---------|----------:|
            | Data 1   | Value 1   |
            | Data 2   | Value 2   |
            """,
            output_path="sample.tex",
            bibliography_file="references.bib"
        )
        print(result)
    except Exception as e:
        print(f"Error: {e}")
