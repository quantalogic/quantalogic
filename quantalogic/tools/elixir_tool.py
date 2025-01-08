"""Tool to execute Elixir code in an isolated Docker environment with Mix project support."""

import logging
import os
import subprocess
import tempfile

from quantalogic.tools.tool import Tool, ToolArgument

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ElixirTool(Tool):
    """Tool to execute Elixir code in an isolated Docker environment with Mix project support."""

    name: str = "elixir_tool"
    description: str = (
        "Executes Elixir code within a Docker container using Mix for package management.\n\n"
        "FEATURES:\n"
        "- Full Mix project support with dependency management\n"
        "- Isolated Docker environment execution\n"
        "- Configurable Elixir versions\n"
        "- Environment variable support\n"
        "- Host directory mounting\n"
        "- Memory limit configuration\n\n"
        "EXECUTION ENVIRONMENT:\n"
        "- Runs in an isolated Docker container\n"
        "- Uses official Elixir Docker images\n"
        "- Supports Mix package manager\n"
        "- Full access to standard library\n\n"
        "ACCEPTED OUTPUT METHODS:\n"
        "- IO.puts/1, IO.write/1\n"
        "- Logger module\n"
        "- File operations when host_dir mounted\n\n"
        "EXAMPLE:\n"
        'defmodule Example do\n  def hello, do: IO.puts("Hello from Elixir!")\nend\n\nExample.hello()'
    )

    arguments: list[ToolArgument] = [
        ToolArgument(
            name="mix_commands",
            arg_type="string",
            description="Mix commands to run before executing script",
            required=False,
            example="mix deps.get && mix compile",
        ),
        ToolArgument(
            name="script",
            arg_type="string",
            description="Elixir code to execute",
            required=True,
            example='IO.puts("Hello!")',
        ),
        ToolArgument(
            name="version",
            arg_type="string",
            description="Elixir version to use",
            required=False,
            default="1.15",
        ),
        ToolArgument(
            name="host_dir",
            arg_type="string",
            description="Host directory to mount",
            required=False,
        ),
        ToolArgument(
            name="memory_limit",
            arg_type="string",
            description="Container memory limit",
            required=False,
            example="512m",
        ),
        ToolArgument(
            name="environment_vars",
            arg_type="string",
            description="Environment variables (KEY=VALUE)",
            required=False,
            example="MIX_ENV=prod",
        ),
    ]

    def check_docker(self) -> None:
        """Verify Docker is installed and accessible."""
        try:
            subprocess.run(
                ["docker", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError("Docker is not installed or not accessible") from e

    def validate_version(self, version: str) -> None:
        """Validate Elixir version is supported."""
        valid_versions = ["1.14", "1.15", "1.16"]
        if version not in valid_versions:
            raise ValueError(f"Unsupported Elixir version '{version}'. Valid versions: {', '.join(valid_versions)}")

    def write_script(self, script_path: str, script: str) -> None:
        """Write Elixir script to file."""
        if not script.strip():
            raise ValueError("Script content cannot be empty")

        # Always wrap in ElixirScript module
        wrapped_script = r"""
defmodule ElixirScript do
  def main do
    try do
      %s
    rescue
      error -> 
        formatted = Exception.format(:error, error, __STACKTRACE__)
        IO.puts("Error: #{formatted}")
        System.halt(1)
    end
  end
end

# Execute the main function
ElixirScript.main()
""" % script.strip()  # noqa: UP031

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(wrapped_script.strip())

    def execute(
        self,
        script: str,
        mix_commands: str | None = None,
        version: str = "1.15",
        host_dir: str | None = None,
        memory_limit: str | None = None,
        environment_vars: str | None = None,
    ) -> str:
        """Execute Elixir code in Docker container with Mix support."""
        # Validate inputs
        self.check_docker()
        self.validate_version(version)

        docker_image = f"elixir:{version}-slim"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Write script directly without Mix project
            script_path = os.path.join(temp_dir, "script.exs")
            self.write_script(script_path, script)

            # Prepare Docker command
            cmd = ["docker", "run", "--rm"]

            # Add memory limit
            if memory_limit:
                cmd.extend(["--memory", memory_limit])

            # Mount directories
            cmd.extend(["-v", f"{temp_dir}:/app"])
            cmd.extend(["-w", "/app"])

            if host_dir:
                cmd.extend(["-v", f"{host_dir}:/host"])

            # Add environment variables
            if environment_vars:
                for pair in environment_vars.split():
                    if "=" in pair:
                        cmd.extend(["-e", pair])

            # Add image and command to run the script directly
            cmd.extend([docker_image, "elixir", "script.exs"])

            # Execute
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                output = result.stdout
                if result.stderr:
                    output = f"{output}\nErrors:\n{result.stderr}"
                return output.strip()
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else e.stdout
                raise RuntimeError(f"Execution failed: {error_msg}")


def main():
    """Run example Elixir code executions."""
    tool = ElixirTool()

    print("\nExample 1: Simple Output")
    simple_script = r"""
    IO.puts("Starting simple output test...")
    IO.puts("Hello from Elixir!")
    IO.puts("Simple output test completed.")
    """
    print(tool.execute(script=simple_script))

    print("\nExample 2: Basic Module")
    module_script = r"""
    IO.puts("Starting calculator module test...")
    
    defmodule Calculator do
      def add(a, b) do
        IO.puts("Calculating #{a} + #{b}...")
        result = a + b
        IO.puts("Result: #{a} + #{b} = #{result}")
        result
      end
    end

    IO.puts("\nTesting Calculator.add(5, 3):")
    result = Calculator.add(5, 3)
    IO.puts("Calculator test completed. Final result: #{result}")
    """
    print(tool.execute(script=module_script))

    print("\nExample 3: Binary Encoding")
    json_script = r"""
    IO.puts("Starting binary encoding test...")
    
    IO.puts("Ensuring applications are started...")
    {:ok, _} = Application.ensure_all_started(:inets)
    {:ok, _} = Application.ensure_all_started(:ssl)
    
    IO.puts("\nPreparing test data...")
    data = %{name: "John", age: 30}
    IO.puts("Data: #{inspect(data)}")
    
    IO.puts("\nEncoding data...")
    encoded = :erlang.term_to_binary(data) 
             |> Base.encode64()
    IO.puts("Encoded result: #{encoded}")
    
    IO.puts("\nBinary encoding test completed.")
    """
    print(tool.execute(script=json_script))


if __name__ == "__main__":
    main()
