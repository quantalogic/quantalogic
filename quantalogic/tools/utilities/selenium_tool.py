"""Selenium Tool for web automation and testing.

This tool provides a high-level interface for web automation tasks using Selenium WebDriver.
It supports common web interactions like navigation, form filling, and element manipulation.
"""

import asyncio
from typing import Optional, List, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from pydantic import Field, ConfigDict
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument

class SeleniumTool(Tool):
    """Tool for web automation using Selenium WebDriver."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="selenium_tool")
    description: str = Field(
        default=(
            "Automates web browser interactions using Selenium WebDriver. "
            "Supports navigation, form filling, clicking, and extracting content. "
            "Uses Chrome browser in headless mode by default."
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="action",
                arg_type="string",
                description=(
                    "The automation action to perform. Available actions: "
                    "navigate, click, type, extract_text, extract_attribute, wait_for_element"
                ),
                required=True,
                example="navigate",
            ),
            ToolArgument(
                name="url",
                arg_type="string",
                description="URL to navigate to (required for 'navigate' action)",
                required=False,
                example="https://example.com",
            ),
            ToolArgument(
                name="selector",
                arg_type="string",
                description="CSS or XPath selector for target element",
                required=False,
                example="#login-button",
            ),
            ToolArgument(
                name="selector_type",
                arg_type="string",
                description="Type of selector (css, xpath, id, name, class_name)",
                required=False,
                default="css",
                example="css",
            ),
            ToolArgument(
                name="value",
                arg_type="string",
                description="Value to type or attribute to extract",
                required=False,
                example="username123",
            ),
            ToolArgument(
                name="timeout",
                arg_type="int",
                description="Maximum time to wait for element (seconds)",
                required=False,
                default="10",
                example="10",
            ),
        ]
    )

    driver: Optional[webdriver.Chrome] = Field(default=None, exclude=True)
    headless: bool = Field(default=True, description="Run browser in headless mode")
    custom_options: List[str] = Field(default_factory=list, description="Custom Chrome options")

    def __init__(
        self,
        headless: bool = True,
        custom_options: Optional[List[str]] = None,
        name: str = "selenium_tool"
    ):
        """Initialize SeleniumTool with browser configuration.

        Args:
            headless (bool): Run browser in headless mode. Defaults to True.
            custom_options (List[str], optional): Custom Chrome options.
            name (str): Name of the tool instance.
        """
        super().__init__(
            **{
                "headless": headless,
                "custom_options": custom_options or [],
                "name": name,
            }
        )
        self._initialize_driver()

    def _initialize_driver(self):
        """Initialize Chrome WebDriver with configured options."""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Add common options for stability
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # Add custom options
            for option in self.custom_options:
                chrome_options.add_argument(option)

            # Initialize the driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(5)
            logger.info("Successfully initialized Chrome WebDriver")

        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            raise

    def _get_by_method(self, selector_type: str) -> By:
        """Get the appropriate By method based on selector type.

        Args:
            selector_type: Type of selector (css, xpath, id, name, class_name)

        Returns:
            selenium.webdriver.common.by.By method
        """
        selector_types = {
            "css": By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id": By.ID,
            "name": By.NAME,
            "class_name": By.CLASS_NAME,
        }
        return selector_types.get(selector_type.lower(), By.CSS_SELECTOR)

    async def async_execute(
        self,
        action: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        selector_type: str = "css",
        value: Optional[str] = None,
        timeout: int = 10,
    ) -> Dict[str, Any]:
        """Execute a Selenium automation action asynchronously.

        Args:
            action: The automation action to perform
            url: URL to navigate to (for navigate action)
            selector: Element selector
            selector_type: Type of selector (css, xpath, id, name, class_name)
            value: Value to type or attribute to extract
            timeout: Maximum time to wait for element (seconds)

        Returns:
            Dict containing action result and any extracted data
        """
        try:
            if not self.driver:
                self._initialize_driver()

            result = {"success": False, "message": "", "data": None}

            # Handle different actions
            if action == "navigate":
                if not url:
                    raise ValueError("URL is required for navigate action")
                self.driver.get(url)
                result["success"] = True
                result["message"] = f"Successfully navigated to {url}"

            elif action in ["click", "type", "extract_text", "extract_attribute", "wait_for_element"]:
                if not selector:
                    raise ValueError("Selector is required for element actions")

                # Wait for element
                by_method = self._get_by_method(selector_type)
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by_method, selector))
                )

                if action == "click":
                    element.click()
                    result["success"] = True
                    result["message"] = f"Successfully clicked element: {selector}"

                elif action == "type":
                    if not value:
                        raise ValueError("Value is required for type action")
                    element.clear()
                    element.send_keys(value)
                    result["success"] = True
                    result["message"] = f"Successfully typed '{value}' into element: {selector}"

                elif action == "extract_text":
                    text = element.text
                    result["success"] = True
                    result["message"] = "Successfully extracted text"
                    result["data"] = text

                elif action == "extract_attribute":
                    if not value:
                        raise ValueError("Attribute name is required for extract_attribute action")
                    attr_value = element.get_attribute(value)
                    result["success"] = True
                    result["message"] = f"Successfully extracted attribute: {value}"
                    result["data"] = attr_value

                elif action == "wait_for_element":
                    result["success"] = True
                    result["message"] = f"Element found: {selector}"

            else:
                raise ValueError(f"Unknown action: {action}")

            return result

        except Exception as e:
            logger.error(f"Error in SeleniumTool.async_execute: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "data": None
            }

    def execute(
        self,
        action: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        selector_type: str = "css",
        value: Optional[str] = None,
        timeout: int = 10,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for async_execute."""
        return asyncio.run(
            self.async_execute(
                action=action,
                url=url,
                selector=selector,
                selector_type=selector_type,
                value=value,
                timeout=timeout,
            )
        )

    def __del__(self):
        """Clean up WebDriver when the tool is destroyed."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Successfully closed WebDriver")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")


if __name__ == "__main__":
    # Example usage
    tool = SeleniumTool(headless=True)

    # Navigate to a website
    result = tool.execute(
        action="navigate",
        url="https://example.com"
    )
    print("Navigation result:", result)

    # Extract text from an element
    result = tool.execute(
        action="extract_text",
        selector="h1",
        selector_type="css"
    )
    print("Extracted text:", result)

    # Clean up
    del tool
