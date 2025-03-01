"""Tool for executing SQL queries and performing database operations with safety checks."""

import json
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import Field
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from quantalogic.tools.tool import Tool, ToolArgument


class QueryType(Enum):
    """Supported SQL query types"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"


class SQLQueryToolAdvanced(Tool):
    """Tool for executing SQL queries and performing database operations safely."""

    name: str = "sql_query_tool"
    description: str = (
        "Executes SQL operations including queries, inserts, updates, and schema modifications "
        "with built-in safety checks and pagination support for queries."
    )
    arguments: list = [
        ToolArgument(
            name="query",
            arg_type="string",
            description="The SQL query/statement to execute",
            required=True,
            example="SELECT * FROM customers WHERE country = :country"
        ),
        ToolArgument(
            name="params",
            arg_type="string",
            description="JSON string containing named parameters for SQL query binding (e.g., '{\"country\": \"France\"}')",
            required=False,
            example='{"country": "France"}'
        ),
        ToolArgument(
            name="start_row",
            arg_type="int",
            description="1-based starting row number for SELECT results",
            required=False,
            example="1",
            default="1"
        ),
        ToolArgument(
            name="end_row",
            arg_type="int", 
            description="1-based ending row number for SELECT results",
            required=False,
            example="100",
            default="100"
        ),
    ]
    connection_string: str = Field(
        ...,
        description="SQLAlchemy-compatible database connection string",
        example="postgresql://user:password@localhost/mydb"
    )
    _engine: Optional[Engine] = None

    def __init__(self, **data):
        super().__init__(**data)
        self._engine = create_engine(self.connection_string)
        logger.info(f"Initialized SQL tool with engine for {self.connection_string}")

    def execute(
        self, 
        query: str, 
        params: Optional[str] = None,
        start_row: Optional[Any] = 1,
        end_row: Optional[Any] = 100
    ) -> str:
        """
        Executes a SQL operation with parameter binding and appropriate handling based on query type.
        
        Args:
            query: SQL query/statement to execute
            params: JSON string containing named parameters for query binding
            start_row: Starting row for SELECT pagination
            end_row: Ending row for SELECT pagination
            
        Returns:
            str: Operation results in markdown format
            
        Raises:
            ValueError: For invalid parameters or query errors
            RuntimeError: For database connection issues
        """
        try:
            # Parse params JSON if provided
            params_dict = json.loads(params) if params else {}
            
            query_type = self._detect_query_type(query)
            logger.debug(f"Executing {query_type} operation")

            if query_type == QueryType.SELECT:
                return self._execute_select(query, params_dict, start_row, end_row)
            else:
                return self._execute_modification(query, params_dict, query_type)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid params JSON: {str(e)}")
            raise ValueError(f"Invalid params JSON: {str(e)}")
        except Exception as e:
            logger.error(f"SQL operation failed: {str(e)}")
            raise

    def _detect_query_type(self, query: str) -> QueryType:
        """Detect the type of SQL operation from the query string."""
        first_word = query.strip().split()[0].upper()
        try:
            return QueryType(first_word)
        except ValueError:
            raise ValueError(f"Unsupported SQL operation: {first_word}")

    def _execute_select(
        self, 
        query: str,
        params: Dict[str, Any],
        start_row: Any,
        end_row: Any
    ) -> str:
        """Execute a SELECT query with pagination."""
        start = self._convert_row_number(start_row, "start_row")
        end = self._convert_row_number(end_row, "end_row")
        
        if start > end:
            raise ValueError(f"start_row ({start}) must be <= end_row ({end})")

        with self._engine.connect() as conn:
            result = conn.execute(text(query), params)
            columns: List[str] = result.keys()
            all_rows: List[Dict] = [dict(row._mapping) for row in result]

        total_rows = len(all_rows)
        actual_start = max(1, start)
        actual_end = min(end, total_rows)
        
        if actual_start > total_rows:
            return f"No results found (total rows: {total_rows})"

        displayed_rows = all_rows[actual_start-1:actual_end]
        
        markdown = [
            f"**SELECT Results:** `{actual_start}-{actual_end}` of `{total_rows}` rows",
            self._format_table(columns, displayed_rows)
        ]

        if actual_end < total_rows:
            remaining = total_rows - actual_end
            markdown.append(f"\n*Showing first {actual_end} rows - {remaining} more row{'s' if remaining > 1 else ''} available*")

        return "\n".join(markdown)

    def _execute_modification(
        self,
        query: str,
        params: Dict[str, Any],
        query_type: QueryType
    ) -> str:
        """Execute a database modification operation within a transaction."""
        with self._engine.begin() as conn:
            try:
                if query_type in [QueryType.CREATE, QueryType.ALTER, QueryType.DROP]:
                    self._validate_schema_operation(query)
                
                result = conn.execute(text(query), params)
                row_count = result.rowcount
                
                operation = query_type.value.capitalize()
                message = f"**{operation} Operation Successful**\n"
                
                if row_count >= 0:  # Not all operations return a row count
                    message += f"Affected rows: `{row_count}`"
                
                logger.info(f"{operation} operation completed successfully")
                return message

            except Exception as e:
                logger.error(f"Modification operation failed: {str(e)}")
                raise

    def _validate_schema_operation(self, query: str):
        """Validate schema modification operations for safety."""
        # Basic validation - could be extended based on requirements
        query_lower = query.lower()
        if "drop database" in query_lower:
            raise ValueError("DROP DATABASE operations are not allowed")
        
        inspector = inspect(self._engine)
        _existing_tables = inspector.get_table_names()
        
        # Additional safety checks could be added here
        logger.debug("Schema validation passed for operation")

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
    tool = SQLQueryToolAdvanced(connection_string="sqlite:///sample.db")
    print(tool.execute("select * from customers", 1, 10))
    print(tool.execute("select * from customers", 11, 20))