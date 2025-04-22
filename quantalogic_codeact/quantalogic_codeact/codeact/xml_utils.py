from typing import Any, Tuple

from loguru import logger
from lxml import etree
from quantalogic_pythonbox import AsyncExecutionResult


def validate_xml(xml_string: str) -> bool:
    """Validate XML string using strict parser."""
    try:
        etree.fromstring(xml_string)
        return True
    except etree.XMLSyntaxError as e:
        logger.error(f"XML validation failed: {e}")
        return False

def format_xml_element(tag: str, value: Any, **attribs) -> etree.Element:
    """Create an XML element with optional CDATA and attributes."""
    elem = etree.Element(tag, **attribs)
    elem.text = etree.CDATA(str(value)) if value is not None else None
    return elem

class XMLResultHandler:
    """Utility class for handling all XML formatting and parsing operations."""
    
    _parser = etree.XMLParser(recover=True, remove_comments=True, resolve_entities=False)

    @staticmethod
    def format_execution_result(result: AsyncExecutionResult) -> str:
        """Format execution result as XML, handling dictionary output."""
        root = etree.Element("ExecutionResult")
        status = "Success" if not result.error else "Error"
        root.append(format_xml_element("Status", status))

        if result.error:
            value = result.error
            completed = False
            final_answer = None
            next_step_desc = None
        elif isinstance(result.result, dict) and "status" in result.result:
            status_value = result.result["status"]
            if status_value == "completed":
                completed = True
                final_answer = result.result.get("result", "")
                next_step_desc = None
                value = final_answer
            elif status_value == "inprogress":
                completed = False
                final_answer = None
                next_step_desc = result.result.get("next_step", "")
                value = result.result.get("result", "")
            else:
                completed = False
                final_answer = None
                next_step_desc = None
                value = f"Invalid status: {status_value}"
        else:
            # Fallback for legacy string results
            if isinstance(result.result, str) and result.result.startswith("Task completed:"):
                completed = True
                final_answer = result.result[len("Task completed:"):].strip()
                value = final_answer
                next_step_desc = None
            else:
                completed = False
                final_answer = None
                next_step_desc = None
                value = str(result.result) if result.result is not None else ""

        root.append(format_xml_element("Value", value))
        root.append(format_xml_element("ExecutionTime", f"{result.execution_time:.2f} seconds"))
        root.append(format_xml_element("Completed", str(completed).lower()))
        if completed and final_answer is not None:
            root.append(format_xml_element("FinalAnswer", final_answer))
        if not completed and next_step_desc:
            root.append(format_xml_element("NextStepDescription", next_step_desc))

        if result.local_variables:
            vars_elem = etree.SubElement(root, "Variables")
            for k, v in result.local_variables.items():
                if not callable(v) and not k.startswith("__"):
                    var_elem = etree.SubElement(vars_elem, "Variable", name=k)
                    var_value = str(v)[:5000] + ("... (truncated)" if len(str(v)) > 5000 else "")
                    var_elem.text = etree.CDATA(var_value)
        
        xml_str = etree.tostring(root, pretty_print=True, encoding="unicode")
        if not validate_xml(xml_str):
            logger.error(f"Generated invalid XML: {xml_str}")
            raise ValueError("Generated XML is invalid")
        return xml_str

    @staticmethod
    def format_result_summary(result_xml: str) -> str:
        """Format XML result into a readable summary with error resilience."""
        try:
            root = etree.fromstring(result_xml, parser=XMLResultHandler._parser)
            if root is None:
                raise ValueError("Empty XML document")
            
            lines = [
                f"- Status: {root.findtext('Status', 'N/A')}",
                f"- Value: {root.findtext('Value', 'N/A')}",
                f"- Execution Time: {root.findtext('ExecutionTime', 'N/A')}",
                f"- Completed: {root.findtext('Completed', 'N/A').capitalize()}"
            ]
            
            if final_answer := root.findtext("FinalAnswer"):
                lines.append(f"- Final Answer: {final_answer}")
            if next_step_desc := root.findtext("NextStepDescription"):
                lines.append(f"- Next Step Description: {next_step_desc}")

            if (vars_elem := root.find("Variables")) is not None:
                lines.append("- Variables:")
                lines.extend(f"  - {var.get('name', 'unknown')}: {var.text.strip() or 'N/A'}" 
                            for var in vars_elem.findall("Variable"))
            return "\n".join(lines)
        except (etree.XMLSyntaxError, ValueError) as e:
            logger.error(f"Failed to parse XML result: {e}")
            return f"Raw Result (Error: {str(e)}):\n{result_xml}"

    @staticmethod
    def parse_action_response(response: str) -> Tuple[str, str]:
        """Parse XML response to extract thought and code with robust error handling."""
        try:
            root = etree.fromstring(response, parser=XMLResultHandler._parser)
            if root is None:
                raise ValueError("Empty XML document")
            
            # Log XML parsing warnings
            if XMLResultHandler._parser.error_log:
                for error in XMLResultHandler._parser.error_log:
                    logger.warning(f"XML parse warning: {error.message} (line {error.line})")
            
            return (
                root.findtext("Thought") or "",
                root.findtext("Code") or ""
            )
        except etree.XMLSyntaxError as e:
            logger.error(f"Critical XML parsing error: {e}")
            raise ValueError(f"Malformed XML structure: {e}") from e

    @staticmethod
    def extract_result_value(result: str) -> str:
        """Safely extract the value from the result XML."""
        try:
            root = etree.fromstring(result, parser=XMLResultHandler._parser)
            return root.findtext("Value") or "" if root is not None else ""
        except etree.XMLSyntaxError as e:
            logger.warning(f"XML extraction error: {e}")
            return ""

    @staticmethod
    def format_error_result(error_msg: str) -> str:
        """Format an error result as XML with proper escaping."""
        root = etree.Element("Action")
        root.append(format_xml_element("Thought", f"Failed to generate valid action: {error_msg}"))
        error_elem = etree.SubElement(root, "Error")
        error_elem.append(format_xml_element("Message", error_msg))
        root.append(format_xml_element("Code", """
import asyncio
async def main():
    print("Error: Action generation failed")
"""))
        return etree.tostring(root, pretty_print=True, encoding="unicode")