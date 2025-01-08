"""Utility function to read text content from a given URL and return it as a string."""

import logging
from time import sleep

import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException

# Configure logging
logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def read_http_text_content(
    url: str, timeout: int = 10, retries: int = 3, delay: int = 2
) -> tuple[str | None, str | None]:
    """Fetches the content from the given URL and returns it as a string.

    Args:
        url (str): The URL from which to fetch the content.
        timeout (int): Timeout in seconds for the HTTP request. Default is 10.
        retries (int): Number of retries in case of failure. Default is 3.
        delay (int): Delay in seconds between retries. Default is 2.

    Returns:
        tuple[str | None, str | None]: A tuple containing the content as a string and an error message.
                                       If successful, the error message is None.
                                       If failed, the content is None and the error message is provided.

    Examples:
        >>> content, error = read_http_text_content("https://example.com/data.txt")
        >>> if error:
        ...     print(f"Error: {error}")
        ... else:
        ...     print(content)

        >>> content, error = read_http_file("https://example.com/binary.data")
        >>> if error:
        ...     print(f"Error: {error}")  # Output: Error: Expected text-based content, but received binary content with Content-Type: application/octet-stream
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/plain, application/json, application/xml, text/csv, text/html, application/javascript, application/x-yaml, application/x-www-form-urlencoded, application/octet-stream",
    }

    for attempt in range(retries):
        try:
            logger.debug(f"Attempt {attempt + 1} of {retries} to fetch {url}")
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)

            # Check if the content type is text-based
            content_type = response.headers.get("Content-Type", "").lower()
            text_based_types = [
                "text/",
                "application/json",
                "application/xml",
                "text/csv",
                "text/html",
                "application/javascript",
                "application/x-yaml",
                "application/x-www-form-urlencoded",
            ]
            if not any(content_type.startswith(t) for t in text_based_types):
                error_msg = (
                    f"Expected text-based content, but received binary content with Content-Type: {content_type}"
                )
                logger.error(error_msg)
                return None, error_msg

            return response.text, None
        except HTTPError as http_err:
            status_code = http_err.response.status_code if http_err.response else "unknown"
            error_msg = f"HTTP error occurred (status code: {status_code}): {http_err}"
            logger.error(error_msg)
            if status_code in [404, 403, 401]:  # Don't retry for these status codes
                break
        except ConnectionError as conn_err:
            error_msg = f"Connection error occurred (URL: {url}): {conn_err}"
            logger.error(error_msg)
        except requests.Timeout as timeout_err:
            error_msg = f"Request timed out after {timeout} seconds: {timeout_err}"
            logger.error(error_msg)
        except RequestException as req_err:
            error_msg = f"An unexpected error occurred (URL: {url}): {req_err}"
            logger.error(error_msg)

        if attempt < retries - 1:
            sleep_duration = delay * (2**attempt)  # Exponential backoff
            logger.debug(f"Retrying in {sleep_duration} seconds...")
            sleep(sleep_duration)

    return None, error_msg


if __name__ == "__main__":
    content, error = read_http_text_content("https://www.quantalogic.app")
    if error:
        print(f"Error: {error}")
    else:
        print(content)
