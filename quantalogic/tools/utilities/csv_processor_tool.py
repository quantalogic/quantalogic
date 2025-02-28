"""Tool for processing CSV files with pandas."""

from pathlib import Path
from typing import Dict, List, Any
import json
import re

import pandas as pd
from loguru import logger

from quantalogic.tools.tool import Tool, ToolArgument


class CSVProcessorTool(Tool):
    """Tool for reading, processing and writing CSV files."""

    name: str = "csv_processor_tool"
    description: str = """
    Process CSV files with operations like:
    - read: Display CSV content and info
    - add_column: Add a new column with values
    - update_column: Update existing column values
    - process_rows: Process rows with custom conditions
    - filter_rows: Filter rows based on conditions
    - describe: Get statistical description of the data
    """
    need_validation: bool = False
    arguments: list = [
        ToolArgument(
            name="input_path",
            arg_type="string",
            description="Path to the input CSV file",
            required=True,
            example="/path/to/input.csv",
        ),
        ToolArgument(
            name="operation",
            arg_type="string",
            description="""Operation to perform:
            - read: Display CSV content
            - add_column: Add new column
            - update_column: Update column values
            - process_rows: Process specific rows
            - filter_rows: Filter rows by condition
            - describe: Get data statistics
            """,
            required=True,
            example="read",
        ),
        ToolArgument(
            name="column_name",
            arg_type="string", 
            description="Name of the column to add/update",
            required=False,
            example="description",
            default="",
        ),
        ToolArgument(
            name="column_value",
            arg_type="string",
            description="""Value for the column. Supports:
            - Simple value: "some text"
            - Template with variables: "User $name$ with email $email$"
            - JSON format for complex operations: {"condition": "price > 100", "value": "premium"}
            Variables in templates must be in $variable$ format and match column names.""",
            required=False,
            example="Hello $name$! Your email is $email$",
            default="",
        ),
        ToolArgument(
            name="output_path",
            arg_type="string",
            description="Path to save the processed CSV file. If not provided, will overwrite input file",
            required=False,
            example="/path/to/output.csv",
            default="",
        ),
    ]

    def _read_csv(self, df: pd.DataFrame) -> str:
        """Display CSV content and information."""
        info = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "data_types": df.dtypes.astype(str).to_dict(),
            "preview": df.head().to_dict(orient="records"),
            "total_rows": len(df),
        }
        return f"CSV Information:\n{json.dumps(info, indent=2)}"

    def _parse_value(self, value: str) -> Dict[str, Any]:
        """Parse the column_value string into a dictionary."""
        if not value:
            return {"value": ""}
            
        try:
            # Try parsing as JSON first
            return json.loads(value)
        except json.JSONDecodeError:
            # If not valid JSON, treat as template or simple value
            return {"value": value, "is_template": bool(re.search(r'\$\w+\$', value))}

    def _apply_template(self, template: str, row: pd.Series) -> str:
        """Apply template replacing $variable$ with values from row."""
        result = template
        for match in re.finditer(r'\$(\w+)\$', template):
            var_name = match.group(1)
            if var_name in row.index:
                value = str(row[var_name])
                result = result.replace(f"${var_name}$", value)
        return result

    def _process_rows(self, df: pd.DataFrame, condition: Dict[str, Any]) -> pd.DataFrame:
        """Process rows based on condition."""
        try:
            if "filter" in condition:
                query = condition["filter"]
                df = df.query(query)
            
            if "update" in condition:
                updates = condition["update"]
                for col, value in updates.items():
                    if "filter" in condition:
                        df.loc[df.eval(condition["filter"]), col] = value
                    else:
                        df[col] = value
            
            return df
        except Exception as e:
            logger.error(f"Error in _process_rows: {str(e)}")
            raise

    def execute(
        self,
        input_path: str,
        operation: str,
        column_name: str = "",
        column_value: str = "",
        output_path: str = "",
    ) -> str:
        """Process the CSV file according to specified operation."""
        try:
            input_path = Path(input_path)
            if not input_path.exists():
                return f"Error: Input file {input_path} does not exist"

            logger.info(f"Reading CSV file: {input_path}")
            df = pd.read_csv(input_path)
            initial_shape = df.shape

            if operation == "read":
                return self._read_csv(df)
                
            elif operation == "describe":
                stats = df.describe().to_dict()
                return f"Statistical Description:\n{json.dumps(stats, indent=2)}"
                
            elif operation == "add_column":
                if not column_name:
                    return "Error: column_name is required for add_column operation"
                if column_name in df.columns:
                    return f"Error: Column {column_name} already exists"
                    
                value_dict = self._parse_value(column_value)
                
                if value_dict.get("is_template", False):
                    # Handle template string with variables
                    df[column_name] = df.apply(
                        lambda row: self._apply_template(value_dict["value"], row),
                        axis=1
                    )
                elif "formula" in value_dict:
                    # Handle formula-based column addition
                    df[column_name] = df.eval(value_dict["formula"])
                else:
                    # Handle static value
                    df[column_name] = value_dict.get("value", "")
                
            elif operation == "update_column":
                if not column_name:
                    return "Error: column_name required for update_column"
                if column_name not in df.columns:
                    return f"Error: Column {column_name} does not exist"
                    
                value_dict = self._parse_value(column_value)
                
                if value_dict.get("is_template", False):
                    # Handle template string with variables
                    df[column_name] = df.apply(
                        lambda row: self._apply_template(value_dict["value"], row),
                        axis=1
                    )
                elif "condition" in value_dict:
                    # Update based on condition
                    mask = df.eval(value_dict["condition"])
                    df.loc[mask, column_name] = value_dict.get("value", "")
                else:
                    # Update all rows
                    df[column_name] = value_dict.get("value", "")
                
            elif operation == "process_rows" or operation == "filter_rows":
                if not column_value:
                    return f"Error: column_value with conditions required for {operation}"
                conditions = self._parse_value(column_value)
                df = self._process_rows(df, conditions)
                
            else:
                return f"Error: Unknown operation {operation}"

            # Save if output path provided or if data was modified
            if operation != "read" and operation != "describe":
                save_path = output_path if output_path else input_path
                save_path = Path(save_path)
                logger.info(f"Saving processed CSV to: {save_path}")
                df.to_csv(save_path, index=False)
                
                return (
                    f"Successfully processed CSV:\n"
                    f"- Input shape: {initial_shape}\n"
                    f"- Output shape: {df.shape}\n"
                    f"- Operation: {operation}\n"
                    f"- Saved to: {save_path}"
                )
            
            return "Operation completed successfully"

        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            return f"Error processing CSV: {str(e)}"


if __name__ == "__main__":
    tool = CSVProcessorTool()
    print(tool.to_markdown())
