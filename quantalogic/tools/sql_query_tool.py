"""Tool for executing SQL queries and returning paginated results in markdown format."""

from typing import Any, Dict, List

from pydantic import Field, ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from quantalogic.tools.tool import Tool, ToolArgument


class SQLQueryTool(Tool):
    """Tool for executing SQL queries and returning paginated results in markdown format."""

    name: str = "sql_query_tool"
    description: str = (
        "Executes a SQL query and returns results in markdown table format "
        "with pagination support. Results are truncated based on start/end row numbers."
    )
    arguments: list = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="The SQL query to execute",
            required=True,
            example="SELECT * FROM customers WHERE country = 'France'"
        ),
        ToolArgument(
            name="start_row",
            arg_type="int",
            description="1-based starting row number for results",
            required=True,
            example="1",
            default="1"
        ),
        ToolArgument(
            name="end_row",
            arg_type="int",
            description="1-based ending row number for results",
            required=True,
            example="100",
            default="100"
        ),
    ]
    connection_string: str = Field(
        ...,
        description="SQLAlchemy-compatible database connection string",
        example="postgresql://user:password@localhost/mydb"
    )

    def execute(self, query: str, start_row: Any, end_row: Any) -> str:
        """
        Executes a SQL query and returns formatted results.
        
        Args:
            query: SQL query to execute
            start_row: 1-based starting row number (supports various numeric types)
            end_row: 1-based ending row number (supports various numeric types)
            
        Returns:
            str: Markdown-formatted results with pagination metadata
            
        Raises:
            ValueError: For invalid parameters or query errors
            RuntimeError: For database connection issues
        """
        try:
            # Convert and validate row numbers
            start = self._convert_row_number(start_row, "start_row")
            end = self._convert_row_number(end_row, "end_row")
            
            if start > end:
                raise ValueError(f"start_row ({start}) must be <= end_row ({end})")

            # Execute query
            engine = create_engine(self.connection_string)
            with engine.connect() as conn:
                result = conn.execute(text(query))
                columns: List[str] = result.keys()
                all_rows: List[Dict] = [dict(row._mapping) for row in result]

            # Apply pagination
            total_rows = len(all_rows)
            actual_start = max(1, start)
            actual_end = min(end, total_rows)
            
            if actual_start > total_rows:
                return f"No results found (total rows: {total_rows})"

            # Slice results (convert to 0-based index)
            displayed_rows = all_rows[actual_start-1:actual_end]

            # Format results
            markdown = [
                f"**Query Results:** `{actual_start}-{actual_end}` of `{total_rows}` rows",
                self._format_table(columns, displayed_rows)
            ]

            # Add pagination notice
            if actual_end < total_rows:
                remaining = total_rows - actual_end
                markdown.append(f"\n*Showing first {actual_end} rows - {remaining} more row{'s' if remaining > 1 else ''} available*")

            return "\n".join(markdown)

        except SQLAlchemyError as e:
            raise ValueError(f"SQL Error: {str(e)}") from e
        except ValidationError as e:
            raise ValueError(f"Validation Error: {str(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Database Error: {str(e)}") from e

    def _convert_row_number(self, value: Any, field_name: str) -> int:
        """Convert and validate row number input."""
        try:
            # Handle numeric strings and floats
            if isinstance(value, str):
                if "." in value:
                    num = float(value)
                else:
                    num = int(value)
            else:
                num = value

            converted = int(num)
            if converted != num:  # Check if float had decimal part
                raise ValueError("Decimal values are not allowed for row numbers")
                
            if converted <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
                
            return converted
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid value for {field_name}: {repr(value)}") from e

    def _format_table(self, columns: List[str], rows: List[Dict]) -> str:
        """Format results as markdown table with truncation."""
        if not rows:
            return "No results found"

        # Create header
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        
        # Create rows with truncation
        body = []
        for row in rows:
            values = []
            for col in columns:
                val = str(row.get(col, ""))
                # Truncate long values
                values.append(val[:50] + "..." if len(val) > 50 else val)
            body.append("| " + " | ".join(values) + " |")

        return "\n".join([header, separator] + body)



if __name__ == "__main__":
    from quantalogic.tools.utils.create_sample_database import create_sample_database

    # Create and document sample database
    create_sample_database("sample.db")
    tool = SQLQueryTool(connection_string="sqlite:///sample.db")
    print(tool.execute("select * from customers", 1, 10))
    print(tool.execute("select * from customers", 11, 20))
     
    
    