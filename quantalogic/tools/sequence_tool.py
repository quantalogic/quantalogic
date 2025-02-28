"""
Module for SequenceTool.

The SequenceTool groups multiple tool calls into one action for use within the ReAct framework.
It allows an LLM to invoke several authorized tools in one step by using XML syntax.
The XML input must follow one of these formats:

Option A (wrapped in a <sequence> element):
  <sequence>
    <tool_name1>
      <param1>value1</param1>
      <param2>value2</param2>
      ...
    </tool_name1>
    <tool_name2>
      <param1>value1</param1>
    </tool_name2>
    ...
  </sequence>

Option B (raw tool calls without a wrapping <sequence> element):
  <tool_name1>
    <param1>value1</param1>
    <param2>value2</param2>
    ...
  </tool_name1>
  <tool_name2>
    <param1>value1</param1>
  </tool_name2>
  ...

Where:
  - In Option A the root tag is <sequence>.
  - Each tool call (child element of <sequence>) must have a tag that exactly matches one of the authorized tools.
  - In Option B the entire input is treated as the sequence content.
  - The sub-elements inside each tool call represent parameter names and values.

Objective:
  Execute each tool call in order—even if some calls fail—and return a comprehensive XML report.
  The report includes the execution order, the provided parameters, execution status (success/failure),
  and either the output or error message for each call.

Authorized Tools:
  The list of authorized tool names is derived from the tools provided in the constructor.
"""

import xml.etree.ElementTree as ET
from typing import Any, List

from quantalogic.tools.tool import Tool, ToolArgument
from quantalogic.xml_parser import ToleranceXMLParser
from quantalogic.xml_tool_parser import ToolParser  # XML-based argument parser


class SequenceTool(Tool):
    """
    A tool to execute a sequence of authorized tool calls specified in XML.

    Description for the LLM:
      Use this tool to chain multiple operations into one action. Provide an XML string that either
      wraps the tool calls in a single <sequence> element or is the raw collection of tool calls.
      The tag for each tool call must be one of the authorized tool names.
      Authorized tools: {authorized_list}

      For each tool call, include the required parameters as sub-elements. The syntax is as follows:

      <sequence>
          <tool_name>
              <param1>value1</param1>
              <param2>value2</param2>
              ...
          </tool_name>
          ...
      </sequence>

    Objective:
      Execute each tool call in order—even if some calls fail—and return an XML report that includes
      the order of execution, provided parameters, execution status (success/failure), and the output or
      error message for each call.
    """

    def __init__(self, tools: List[Tool], **data: Any):
        authorized_names = sorted(tool.name for tool in tools)
        desc = (
            "Executes a sequence of authorized tool calls defined in XML, then returns an XML report "
            "detailing the outcome of each call. The XML input may either be wrapped in a <sequence> "
            "element or provided as raw tool calls. Example formats:\n\n"
            "Option A:\n"
            "<sequence>\n"
            "    <tool_name>\n"
            "        <param1>value1</param1>\n"
            "        <param2>value2</param2>\n"
            "    </tool_name>\n"
            "    ...\n"
            "</sequence>\n\n"
            "Option B:\n"
            "<tool_name>\n"
            "    <param1>value1</param1>\n"
            "    <param2>value2</param2>\n"
            "</tool_name>\n"
            "...\n\n"
            f"Authorized tools provided: {', '.join(authorized_names)}."
        )
        data.setdefault("name", "sequence_tool")
        data.setdefault("description", desc)
        default_argument = ToolArgument(
            name="sequence",
            arg_type="string",
            required=True,
            description="XML formatted sequence of tool calls. See syntax above.",
        )
        data.setdefault("arguments", [default_argument])
        super().__init__(**data)

        # Build a dictionary mapping tool names to tool instances.
        self.available_tools = {tool.name: tool for tool in tools}

    def execute(self, **kwargs) -> str:
        """
        Execute a sequence of tool calls provided in XML format and return an XML summary report.

        Expected input formats:
          Option A (wrapped):
            <sequence>...</sequence>
          Option B (raw):
            <tool_name>...</tool_name>
            <tool_name2>...</tool_name2>
            ...

        This implementation uses ToleranceXMLParser to extract the potential <sequence> element.
        If exactly one <sequence> element is found, its content is used; otherwise, the entire input is treated
        as the sequence content. Then, for each tool call, ToolParser (from quantalogic/xml_tool_parser.py)
        is used to parse and validate arguments.

        For each tool call, a <tool_call> element is created with:
          - order: the position in the sequence.
          - name: the tool's name.
          - parameters: the parsed parameter names and values.
          - status: "success" or "failure".
          - output: tool output (if successful) or error_message (if an error occurred).

        All tool calls are executed regardless of failures.
        """
        if "sequence" not in kwargs:
            raise ValueError("Missing 'sequence' parameter.")

        sequence_xml = kwargs["sequence"]
        xml_parser = ToleranceXMLParser()

        # Try to locate <sequence> elements in the input.
        all_elements = xml_parser._find_all_elements(sequence_xml)
        sequence_elems = [(tag, content) for tag, content in all_elements if tag.strip().lower() == "sequence"]
        if len(sequence_elems) > 1:
            raise ValueError("Input XML must contain exactly one <sequence> element.")
        elif len(sequence_elems) == 1:
            # Use the inner content of the found <sequence> element.
            sequence_content = sequence_elems[0][1]
        else:
            # No <sequence> element found; assume the entire input is the sequence content.
            sequence_content = sequence_xml

        # Extract tool call elements from the sequence content.
        # Each tool call is represented as a tuple: (tool_name, inner_xml)
        tool_calls = xml_parser._find_all_elements(sequence_content)
        results_root = ET.Element("sequence_results")

        for index, (tool_name, inner_xml) in enumerate(tool_calls, start=1):
            tool_call_elem = ET.Element("tool_call", attrib={"order": str(index), "name": tool_name})
            parameters_elem = ET.SubElement(tool_call_elem, "parameters")

            # Validate that this is an authorized tool.
            if tool_name not in self.available_tools:
                status_elem = ET.SubElement(tool_call_elem, "status")
                status_elem.text = "failure"
                error_elem = ET.SubElement(tool_call_elem, "error_message")
                error_elem.text = f"Tool '{tool_name}' not found among authorized tools."
                results_root.append(tool_call_elem)
                continue

            tool = self.available_tools[tool_name]
            # Use ToolParser to extract and validate arguments from the inner XML.
            tool_parser = ToolParser(tool)
            try:
                parsed_params = tool_parser.parse(inner_xml)
                # Record parsed parameters in the XML report.
                for arg_name, arg_value in parsed_params.items():
                    param_record = ET.SubElement(parameters_elem, "param", attrib={"name": arg_name})
                    param_record.text = arg_value
            except Exception as e:
                status_elem = ET.SubElement(tool_call_elem, "status")
                status_elem.text = "failure"
                error_elem = ET.SubElement(tool_call_elem, "error_message")
                error_elem.text = f"Argument parsing error: {str(e)}"
                results_root.append(tool_call_elem)
                continue

            # Execute the authorized tool with the validated parameters.
            try:
                output = tool.execute(**parsed_params)
                status_elem = ET.SubElement(tool_call_elem, "status")
                status_elem.text = "success"
                output_elem = ET.SubElement(tool_call_elem, "output")
                output_elem.text = output
            except Exception as e:
                status_elem = ET.SubElement(tool_call_elem, "status")
                status_elem.text = "failure"
                error_elem = ET.SubElement(tool_call_elem, "error_message")
                error_elem.text = str(e)
            results_root.append(tool_call_elem)

        return ET.tostring(results_root, encoding="unicode")


# ----------------- Example Usage and Testing -----------------

if __name__ == "__main__":
    from typing import Any

    # Dummy tool: WriteFileTool simulates writing content to a file.
    class WriteFileTool(Tool):
        def __init__(self, **data: Any):
            data.setdefault("name", "write_file_tool")
            data.setdefault("description", "Writes content to a file at the specified path.")
            data.setdefault(
                "arguments",
                [
                    ToolArgument(name="file_path", arg_type="string", required=True, description="Path to the file"),
                    ToolArgument(
                        name="content", arg_type="string", required=True, description="Content to write to the file"
                    ),
                ],
            )
            super().__init__(**data)

        def execute(self, **kwargs) -> str:
            file_path = kwargs.get("file_path", "")
            content = kwargs.get("content", "")
            # For demonstration, simulate writing to a file.
            return f"File '{file_path}' written with content length {len(content)}."

    # Instantiate the WriteFileTool.
    write_file = WriteFileTool()

    # Instantiate the SequenceTool with WriteFileTool as the authorized tool.
    sequence_tool = SequenceTool(tools=[write_file])

    # Example XML sequence using CDATA blocks for multiline content.
    # This example uses Option A (wrapped in a <sequence> element).
    xml_sequence = """
    <sequence>
      <write_file_tool>
        <file_path>poem1.txt</file_path>
        <content><![CDATA[
Under the moon's silver glow,
Where shadows dance and winds do flow,
There lies a heart so pure and bright,
In the quiet of the night.
        ]]></content>
      </write_file_tool>
      <write_file_tool>
        <file_path>poem2.txt</file_path>
        <content><![CDATA[
In the morning's golden light,
When dewdrops kiss the grass so bright,
The world awakens anew each day,
And hope finds its own sweet way.
        ]]></content>
      </write_file_tool>
    </sequence>
    """

    try:
        result_xml = sequence_tool.execute(sequence=xml_sequence)
        print("SequenceTool result:\n", result_xml)
    except Exception as e:
        print("SequenceTool error:\n", str(e))
