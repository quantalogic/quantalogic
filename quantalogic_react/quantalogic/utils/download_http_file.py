"""Utility function to download a file from a given URL and save it to a local path."""

import logging
from time import sleep
from typing import Optional

import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout, TooManyRedirects

# Configure logging
logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def download_http_file(
    url: str, local_path: str, chunk_size: int = 8192, max_retries: int = 3, timeout: int = 10, delay: int = 2
) -> Optional[str]:
    """Downloads a file from a given URL and saves it to the specified local path.

    Args:
        url (str): The URL of the file to download.
        local_path (str): The local file path where the downloaded file will be saved.
        chunk_size (int): The size of each chunk to download. Default is 8192 bytes.
        max_retries (int): The maximum number of retries for transient errors. Default is 3.
        timeout (int): Timeout in seconds for the HTTP request. Default is 10.
        delay (int): Delay in seconds between retries. Default is 2.

    Returns:
        Optional[str]: The local path where the file was saved if successful, None otherwise.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1} of {max_retries} to download {url}")
            response = requests.get(url, headers=headers, stream=True, timeout=timeout)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "unknown")
            logger.debug(f"Downloading content with Content-Type: {content_type}")

            with open(local_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    file.write(chunk)

            logger.debug(f"File successfully downloaded and saved to {local_path}")
            return local_path

        except HTTPError as http_err:
            status_code = http_err.response.status_code if http_err.response else "unknown"
            error_msg = f"HTTP error occurred (status code: {status_code}, URL: {url}): {http_err}"
            logger.error(error_msg)
            if status_code in [404, 403, 401]:  # Don't retry for these status codes
                break
        except ConnectionError as conn_err:
            error_msg = f"Connection error occurred (URL: {url}): {conn_err}"
            logger.error(error_msg)
        except Timeout as timeout_err:
            error_msg = f"Request timed out after {timeout} seconds (URL: {url}): {timeout_err}"
            logger.error(error_msg)
        except TooManyRedirects as redirect_err:
            error_msg = f"Too many redirects (URL: {url}): {redirect_err}"
            logger.error(error_msg)
        except RequestException as req_err:
            error_msg = f"An unexpected error occurred (URL: {url}): {req_err}"
            logger.error(error_msg)

        if attempt < max_retries - 1:
            sleep_duration = delay * (2**attempt)  # Exponential backoff
            logger.debug(f"Retrying in {sleep_duration} seconds...")
            sleep(sleep_duration)

    logger.error("Max retries reached. Download failed.")
    return None
