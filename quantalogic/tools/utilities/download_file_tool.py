"""Tool for preparing files or directories for download through the existing file server."""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class PrepareDownloadTool(Tool):
    """Tool for preparing files or directories for download through the existing file server."""

    name: str = "prepare_download_tool"
    description: str = (
        "Prepares a local file or directory for download. "
        "If it's a directory, it will be zipped. "
        "Returns an HTML link for downloading."
    )
    need_validation: bool = True
    arguments: list = [
        ToolArgument(
            name="path",
            arg_type="string",
            description="The local path of the file or directory to prepare for download",
            required=True,
            example="/path/to/local/file.pdf",
        ),
        ToolArgument(
            name="filename",
            arg_type="string",
            description="Optional custom filename for download. If not provided, uses original name.",
            required=False,
            example="custom_name.pdf",
        ),
        ToolArgument(
            name="link_text",
            arg_type="string",
            description="Optional custom text for the download link. If not provided, uses a default.",
            required=False,
            example="Download Report",
        ),
    ]

    def __init__(self, upload_dir: str = "/tmp/data", base_url: str = "http://localhost:8082"):
        """Initialize the tool with upload directory path.
        
        Args:
            upload_dir: Directory where files are served from. Defaults to /tmp/data.
            base_url: Base URL of the server. Defaults to http://localhost:8082.
        """
        super().__init__()
        self.upload_dir = upload_dir
        self.base_url = base_url.rstrip('/')
        # Ensure upload directory exists
        os.makedirs(upload_dir, exist_ok=True)

    def _zip_directory(self, dir_path: str, zip_path: str) -> None:
        """Zip a directory.
        
        Args:
            dir_path: Path to the directory to zip
            zip_path: Path where to save the zip file
        """
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            base_path = os.path.basename(dir_path)
            for root, _, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(dir_path))
                    zipf.write(file_path, arcname)
        logger.info(f"Directory zipped successfully: {zip_path}")

    def _generate_html_link(self, url: str, text: str, filename: str) -> str:
        """Generate an HTML link with custom styling.
        
        Args:
            url: The download URL
            text: Text to display in the link
            filename: Name of the file (for logging)
            
        Returns:
            HTML formatted link
        """
        # CSS styling for the download link
        style = (
            "color: #0066cc; "
            "text-decoration: none; "
            "padding: 8px 16px; "
            "border: 1px solid #0066cc; "
            "border-radius: 4px; "
            "display: inline-block; "
            "font-family: system-ui, -apple-system, sans-serif; "
            "transition: all 0.2s;"
        )
        
        hover_style = (
            "background-color: #0066cc; "
            "color: white; "
            "cursor: pointer;"
        )
        
        # Create the HTML link with embedded styles
        html = f'''<a href="{url}" 
            style="{style}" 
            onmouseover="this.style.backgroundColor='#0066cc'; this.style.color='white';" 
            onmouseout="this.style.backgroundColor='transparent'; this.style.color='#0066cc';" 
            download="{filename}">{text}</a>'''
            
        return html

    def execute(self, path: str, filename: str = None, link_text: str = None) -> str:
        """Prepares a file or directory for download.

        Args:
            path: The local path of the file or directory to prepare.
            filename: Optional custom filename for download.
            link_text: Optional custom text for the download link.

        Returns:
            HTML link for downloading the file.

        Raises:
            Exception: If file operations fail.
        """
        try:
            path = os.path.abspath(path)
            
            # Verify path exists
            if not os.path.exists(path):
                error_msg = f"Path not found: {path}"
                logger.error(error_msg)
                return error_msg

            # Handle directory case - create zip file
            if os.path.isdir(path):
                source_name = os.path.basename(path)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_filename = filename or f"{source_name}_{timestamp}.zip"
                if not zip_filename.endswith('.zip'):
                    zip_filename += '.zip'
                
                zip_path = os.path.join(self.upload_dir, zip_filename)
                self._zip_directory(path, zip_path)
                target_path = zip_path
                target_filename = zip_filename
            else:
                # Handle single file case
                source_filename = os.path.basename(path)
                target_filename = filename or source_filename
                target_path = os.path.join(self.upload_dir, target_filename)
                shutil.copy2(path, target_path)
                logger.success(f"File copied to upload directory: {target_path}")

            # Generate download URL
            download_url = f"{self.base_url}/api/agent/download/{target_filename}"
            
            # Generate link text
            if not link_text:
                if os.path.isdir(path):
                    link_text = f"Download {os.path.basename(path)} (ZIP)"
                else:
                    link_text = f"Download {os.path.basename(path)}"

            # Generate and return HTML link
            return self._generate_html_link(download_url, link_text, target_filename)

        except Exception as e:
            error_msg = f"Error while preparing download: {str(e)}"
            logger.error(error_msg)
            return error_msg


if __name__ == "__main__":
    tool = PrepareDownloadTool()
    print(tool.to_markdown())
