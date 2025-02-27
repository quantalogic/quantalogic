"""Tool for generating comprehensive database documentation reports."""

from pydantic import Field, ValidationError

from quantalogic.tools.tool import Tool
from quantalogic.tools.utils.generate_database_report import generate_database_report


class GenerateDatabaseReportTool(Tool):
    """Tool for generating database documentation reports from a connection string."""

    name: str = "generate_database_report_tool"
    description: str = (
        "Generates a comprehensive Markdown database documentation report with ER diagram. "
    )
    arguments: list = []  # No execution arguments - connection string is configured during tool setup
    connection_string: str = Field(
        ...,
        description="SQLAlchemy-compatible database connection string (e.g., 'sqlite:///database.db')",
        example="postgresql://user:password@localhost/mydatabase"
    )

    def execute(self) -> str:
        """Generates a database documentation report using the configured connection string.

        Returns:
            str: Markdown-formatted database report

        Raises:
            ValueError: For invalid connection strings or database connection errors
            RuntimeError: For errors during report generation
        """
        try:
            return generate_database_report(self.connection_string)
        except ValidationError as e:
            raise ValueError(f"Invalid connection configuration: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Database report generation failed: {e}") from e


if __name__ == "__main__":

    from quantalogic.tools.utils.create_sample_database import create_sample_database

    # Create and document sample database
    create_sample_database("sample.db")

    # Example usage
    tool = GenerateDatabaseReportTool(
        connection_string="sqlite:///sample.db"
    )
    print(tool.execute())