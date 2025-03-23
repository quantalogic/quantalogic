import ast
import inspect
from functools import wraps
from typing import Any, Callable, Tuple

from loguru import logger
from lxml import etree


def log_async_tool(verb: str):
    """Decorator factory for consistent async tool logging."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger.info(f"Starting tool: {func.__name__}")
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            logger.info(f"{verb} {', '.join(f'{k}={v}' for k, v in bound_args.arguments.items())}")
            result = await func(*args, **kwargs)
            logger.info(f"Finished tool: {func.__name__}")
            return result
        return wrapper
    return decorator


def log_tool_method(func: Callable) -> Callable:
    """Decorator for logging Tool class methods."""
    @wraps(func)
    async def wrapper(self, **kwargs):
        logger.info(f"Starting tool: {self.name}")
        try:
            result = await func(self, **kwargs)
            logger.info(f"Finished tool: {self.name}")
            return result
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {e}")
            raise
    return wrapper


def validate_xml(xml_string: str) -> bool:
    """Validate XML string."""
    try:
        etree.fromstring(xml_string)
        return True
    except etree.XMLSyntaxError as e:
        logger.error(f"XML validation failed: {e}")
        return False


def validate_code(code: str) -> bool:
    """Check if code has an async main() function."""
    try:
        tree = ast.parse(code)
        return any(isinstance(node, ast.AsyncFunctionDef) and node.name == "main" 
                  for node in ast.walk(tree))
    except SyntaxError:
        return False


def format_xml_element(tag: str, value: Any, **attribs) -> etree.Element:
    """Create an XML element with optional CDATA and attributes."""
    elem = etree.Element(tag, **attribs)
    elem.text = etree.CDATA(str(value)) if value is not None else None
    return elem


class XMLResultHandler:
    """Utility class for handling XML formatting and parsing."""
    @staticmethod
    def format_execution_result(result) -> str:
        """Format execution result as XML."""
        root = etree.Element("ExecutionResult")
        root.append(format_xml_element("Status", "Success" if not result.error else "Error"))
        root.append(format_xml_element("Value", result.result or result.error))
        root.append(format_xml_element("ExecutionTime", f"{result.execution_time:.2f} seconds"))

        completed = result.result and result.result.startswith("Task completed:")
        root.append(format_xml_element("Completed", str(completed).lower()))
        
        if completed:
            final_answer = result.result[len("Task completed:"):].strip()
            root.append(format_xml_element("FinalAnswer", final_answer))

        if result.local_variables:
            vars_elem = etree.SubElement(root, "Variables")
            for k, v in result.local_variables.items():
                if not callable(v) and not k.startswith("__"):
                    vars_elem.append(format_xml_element("Variable", str(v)[:5000] + 
                                                      ("... (truncated)" if len(str(v)) > 5000 else ""), 
                                                      name=k))
        return etree.tostring(root, pretty_print=True, encoding="unicode")

    @staticmethod
    def format_result_summary(result_xml: str) -> str:
        """Format XML result into a readable summary."""
        try:
            root = etree.fromstring(result_xml)
            lines = [
                f"- Status: {root.findtext('Status', 'N/A')}",
                f"- Value: {root.findtext('Value', 'N/A')}",
                f"- Execution Time: {root.findtext('ExecutionTime', 'N/A')}",
                f"- Completed: {root.findtext('Completed', 'N/A').capitalize()}"
            ]
            if final_answer := root.findtext("FinalAnswer"):
                lines.append(f"- Final Answer: {final_answer}")

            if (vars_elem := root.find("Variables")) is not None:
                lines.append("- Variables:")
                lines.extend(f"  - {var.get('name', 'unknown')}: {var.text.strip() or 'N/A'}" 
                            for var in vars_elem.findall("Variable"))
            return "\n".join(lines)
        except etree.XMLSyntaxError:
            logger.error(f"Failed to parse XML: {result_xml}")
            return result_xml

    @staticmethod
    def parse_response(response: str) -> Tuple[str, str]:
        """Parse XML response to extract thought and code."""
        try:
            root = etree.fromstring(response)
            thought = root.findtext("Thought") or ""
            code = root.findtext("Code") or ""
            return thought, code
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Failed to parse XML: {e}")

    @staticmethod
    def extract_result_value(result: str) -> str:
        """Extract the value from the result XML."""
        try:
            return etree.fromstring(result).findtext("Value") or ""
        except etree.XMLSyntaxError:
            return ""