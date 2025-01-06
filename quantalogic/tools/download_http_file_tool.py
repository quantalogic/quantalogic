"""Tool for downloading a file from an HTTP URL and saving it to a local file."""

from urllib.parse import urlparse

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.utils.download_http_file import download_http_file


class DownloadHttpFileTool(Tool):
    """Tool for downloading a file from an HTTP URL and saving it to a local file."""

    name: str = "download_http_file_tool"
    description: str = "Downloads a file from an HTTP URL and saves it to a local file."
    arguments: list = [
        ToolArgument(
            name="url",
            arg_type="string",
            description="The URL of the file to download.",
            required=True,
            example="https://example.com/data.txt",
        ),
        ToolArgument(
            name="output_path",
            arg_type="string",
            description="The local path where the downloaded file will be saved.",
            required=True,
            example="/path/to/save/data.txt",
        ),
    ]

    def _is_url(self, path: str) -> bool:
        """Check if the given path is a valid URL."""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def execute(self, url: str, output_path: str) -> str:
        """Downloads a file from an HTTP URL and saves it to a local file.

        Args:
            url (str): The URL of the file to download.
            output_path (str): The local path where the downloaded file will be saved.

        Returns:
            str: A message indicating the result of the download operation.
        """
        if not self._is_url(url):
            return f"Error: {url} is not a valid URL."

        try:
            result = download_http_file(url, output_path)
            if result:
                return f"File downloaded successfully and saved to {output_path}."
            else:
                return f"Error downloading file from {url}: Unable to download."
        except Exception as e:
            return f"Error downloading file from {url}: {str(e)}"


if __name__ == "__main__":
    tool = DownloadHttpFileTool()
    print(tool.to_markdown())
