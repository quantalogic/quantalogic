import ast
import inspect
from functools import wraps

from loguru import logger
from lxml import etree
import xml.etree.ElementTree as ET


def logged_tool(verb: str):
    """Decorator factory to add consistent logging to tool functions."""
    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            logger.info(f"Starting tool execution: {func.__name__}")
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            args_str = ", ".join(f"{k}={v}" for k, v in bound_args.arguments.items())
            logger.info(f"{verb} {args_str}")
            result = await func(*args, **kwargs)
            logger.info(f"Finished tool execution: {func.__name__}")
            return result
        return wrapped
    return decorator


def log_tool_method(func):
    """Decorator to add logging to Tool class methods."""
    @wraps(func)
    async def wrapper(self, **kwargs):
        logger.info(f"Starting tool execution: {self.name}")
        try:
            result = await func(self, **kwargs)
            logger.info(f"Finished tool execution: {self.name}")
            return result
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {str(e)}")
            raise
    return wrapper


def validate_xml(xml_string: str) -> bool:
    """Validate XML string against a simple implicit schema."""
    try:
        etree.fromstring(xml_string)
        return True
    except etree.XMLSyntaxError as e:
        logger.error(f"XML validation failed: {e}")
        return False


def validate_code(code: str) -> bool:
    """Check if code contains an async main() function."""
    try:
        tree = ast.parse(code)
        return any(isinstance(node, ast.AsyncFunctionDef) and node.name == "main" for node in ast.walk(tree))
    except SyntaxError:
        return False


def format_execution_result(result) -> str:
    """Format execution result as XML string."""
    root = etree.Element("ExecutionResult")
    etree.SubElement(root, "Status").text = "Success" if not result.error else "Error"
    etree.SubElement(root, "Value").text = etree.CDATA(str(result.result or result.error))
    etree.SubElement(root, "ExecutionTime").text = f"{result.execution_time:.2f} seconds"
    
    if not result.error and result.result and result.result.startswith("Task completed:"):
        etree.SubElement(root, "Completed").text = "true"
        final_answer = result.result[len("Task completed:"):].strip()
        etree.SubElement(root, "FinalAnswer").text = etree.CDATA(final_answer)
    else:
        etree.SubElement(root, "Completed").text = "false"
    
    if result.local_variables:
        vars_elem = etree.SubElement(root, "Variables")
        for k, v in result.local_variables.items():
            if not callable(v) and not k.startswith("__"):
                var_elem = etree.SubElement(vars_elem, "Variable", name=k)
                var_elem.text = etree.CDATA(str(v)[:5000] + ("... (truncated)" if len(str(v)) > 5000 else ""))
    
    return etree.tostring(root, pretty_print=True, encoding="unicode")


def format_result_xml(result_xml: str) -> str:
    """
    Formats the XML result into a readable string for the history.

    Args:
        result_xml (str): The XML string containing the execution result.

    Returns:
        str: A formatted string with key information extracted from the XML.
    """
    try:
        root = ET.fromstring(result_xml)
        status = root.findtext("Status", default="N/A")
        value = root.findtext("Value", default="N/A")
        execution_time = root.findtext("ExecutionTime", default="N/A")
        completed = root.findtext("Completed", default="N/A")
        final_answer = root.findtext("FinalAnswer", default=None)
        
        result_lines = [
            f"- Status: {status}",
            f"- Value: {value}",
            f"- Execution Time: {execution_time}",
            f"- Completed: {completed}"
        ]
        if final_answer:
            result_lines.append(f"- Final Answer: {final_answer}")
        
        variables = []
        vars_elem = root.find("Variables")
        if vars_elem is not None:
            for var in vars_elem.findall("Variable"):
                name = var.get("name", "unknown")
                value = var.text.strip() if var.text else "N/A"
                variables.append(f"  - {name}: {value}")
        if variables:
            result_lines.append("- Variables:")
            result_lines.extend(variables)
        
        return "\n".join(result_lines)
    except ET.ParseError:
        logger.error(f"Failed to parse result XML: {result_xml}")
        return result_xml  # Fallback to raw result if parsing fails