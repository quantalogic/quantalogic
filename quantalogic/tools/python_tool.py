"""Tool to execute Python scripts in an isolated Docker environment."""

import logging
import os
import subprocess
import tempfile

from quantalogic.tools.tool import Tool, ToolArgument

# Configure logging for the module
logger = logging.getLogger(__name__)


class PythonTool(Tool):
    """Tool to execute Python scripts in an isolated Docker environment."""

    name: str = "python_tool"
    description: str = (
        "Executes a Python 3.11 script that print statements on the console within a Docker container using pip for package management.\n\n"
        "CONSOLE OUTPUT REQUIREMENTS:\n"
        "1. Only Python code that produces text output via print() statements is accepted\n"
        "2. No GUI, no plots, no visualizations - strictly console/terminal output\n"
        "3. No file operations or external resources unless explicitly authorized\n\n"
        "EXECUTION ENVIRONMENT:\n"
        "- Runs in an isolated Docker container\n"
        "- Python version can be specified (default: Python 3.x)\n"
        "- Required packages can be installed via pip\n"
        "- Standard library modules are available\n\n"
        "- Host directory mounting\n"
        "  - If provided, the host directory is mounted inside the Docker container at /usr/src/host_data\n"
        "  - This allows access to files on the host of the user\n"
        "- Memory limit configuration\n"
        "  - The memory limit can be configured for the Docker container\n"
        "- Network access\n"
        "  - The Docker container has full network access\n\n"
        "ACCEPTED OUTPUT METHODS:\n"
        "✓ print()\n"
        "✓ sys.stdout.write()\n"
        "✗ No matplotlib, tkinter, or other GUI libraries\n"
        "✗ No external file generation\n"
        "✗ No web servers or network services\n\n"
        "EXAMPLE:\n"
        "print('Hello, World!')  # ✓ Valid\n"
        "plt.show()             # ✗ Invalid\n"
    )
    need_validation: bool = True
    arguments: list[ToolArgument] = [
        ToolArgument(
            name="install_commands",
            arg_type="string",
            description=(
                "Commands to install Python packages before running the script. "
                "Use one command per line or separate packages with spaces."
            ),
            required=False,
            example="pip install rich requests",
        ),
        ToolArgument(
            name="script",
            arg_type="string",
            description=(
                "The Python script to execute."
                "The script must use /usr/src/host_data/ as the working directory."
                "Host data is the directory provided in the host_dir argument."
                "The script must produce text output via print() statements."
            ),
            required=True,
            example='print("Hello, World!")\nprint("This is a Python interpreter tool.")',
        ),
        ToolArgument(
            name="version",
            arg_type="string",
            description=("The Python version to use in the Docker container. " "For example: '3.11', '3.12'."),
            required=True,
            default="3.11",
            example="3.11",
        ),
        ToolArgument(
            name="host_dir",
            arg_type="string",
            description=(
                "The absolute path on the host machine to mount for file access. "
                "Provide this path if you want to access files on the host of the user."
            ),
            required=True,
            default=None,
            example="./demo01/",
        ),
        ToolArgument(
            name="memory_limit",
            arg_type="string",
            description=(
                "Optional memory limit for the Docker container (e.g., '512m', '2g'). "
                "If not specified, Docker's default memory limit applies."
            ),
            required=False,
            default=None,
            example="1g",
        ),
        ToolArgument(
            name="environment_vars",
            arg_type="string",
            description=(
                "Environment variables to set inside the Docker container. "
                "Provide as KEY=VALUE pairs separated by spaces."
            ),
            required=False,
            default=None,
            example="ENV=production DEBUG=False",
        ),
    ]

    def execute(
        self,
        install_commands: str | None = None,
        script: str = "",
        version: str = "3.12",
        host_dir: str | None = None,
        memory_limit: str | None = None,
        environment_vars: str | None = None,
    ) -> str:
        """Executes a Python script within a Docker container using pip for package management.

        Args:
            install_commands (str | None): Installation commands for dependencies.
            script (str): The Python script to execute.
            version (str): Python version to use.
            host_dir (str | None): Host directory to mount for file access.
            memory_limit (str | None): Memory limit for Docker container (e.g., '512m', '2g').
            environment_vars (str | None): Environment variables for the Docker container.

        Returns:
            str: The output of the executed script or error messages.

        Raises:
            ValueError: If the Python version is unsupported or inputs are invalid.
            RuntimeError: If Docker commands fail or Docker is not available.
        """
        # Validate inputs
        self._check_docker_availability()
        self._validate_python_version(version)

        # Prepare Docker image based on Python version
        # Use the new uv Docker image family
        docker_image = "ghcr.io/astral-sh/uv:bookworm"

        # Ensure the Docker image is available locally
        if not self._is_docker_image_present(docker_image):
            self._pull_docker_image(docker_image)

        # Create a temporary directory to store the script
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write the script to a file
            script_path = os.path.join(temp_dir, "script.py")
            self._write_script(script_path, script)

            # Prepare pip install commands
            pip_install_cmd = self._prepare_install_commands(install_commands)

            # Run the Docker command and return the output
            return self._run_docker_command(
                docker_image=docker_image,
                temp_dir=temp_dir,
                host_dir=host_dir,
                pip_install_cmd=pip_install_cmd,
                memory_limit=memory_limit,
                environment_vars=environment_vars,
            )

    def _validate_python_version(self, version: str) -> None:
        """Validates whether the specified Python version is supported.

        Args:
            version (str): Python version to validate.

        Raises:
            ValueError: If the Python version is unsupported.
        """
        valid_versions = ["3.8", "3.9", "3.10", "3.11", "3.12"]
        if version not in valid_versions:
            error_msg = f"Unsupported Python version '{version}'. " f"Supported versions: {', '.join(valid_versions)}."
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.debug(f"Python version '{version}' is supported.")

    def _check_docker_availability(self) -> None:
        """Checks if Docker is installed and accessible.

        Raises:
            RuntimeError: If Docker is not available.
        """
        try:
            subprocess.run(
                ["docker", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug("Docker is installed and available.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            error_msg = "Docker is not installed or not accessible. Please install Docker and ensure it's running."
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _write_script(self, path: str, script: str) -> None:
        """Writes the provided Python script to a specified file.

        Args:
            path (str): The path to write the script.
            script (str): The content of the script.

        Raises:
            ValueError: If the script content is empty.
        """
        if not script.strip():
            error_msg = "The provided Python script is empty."
            logger.error(error_msg)
            raise ValueError(error_msg)

        with open(path, "w", encoding="utf-8") as script_file:
            script_file.write(script)
            logger.debug(f"Python script written to {path}")

    def _prepare_install_commands(self, install_commands: str | None) -> str:
        """Prepares installation commands for pip.

        Args:
            install_commands (str | None): Installation commands provided by the user.

        Returns:
            str: A single pip install command string.
        """
        if install_commands:
            packages = set()  # Use a set to handle duplicates
            for line in install_commands.splitlines():
                parts = line.strip().split()
                if parts and parts[0].lower() == "pip" and parts[1].lower() == "install":
                    packages.update(parts[2:])  # Add all packages after "pip install"
                else:
                    packages.update(parts)

            if packages:
                install_command = "uv venv && source .venv/bin/activate && uv pip install --upgrade pip " + " ".join(
                    packages
                )
                logger.debug(f"Prepared pip install command: {install_command}")
                return install_command

        logger.debug("No installation commands provided.")
        return ""

    def _pull_docker_image(self, docker_image: str) -> None:
        """Pulls the specified Docker image.

        Args:
            docker_image (str): The name of the Docker image to pull.

        Raises:
            RuntimeError: If pulling the Docker image fails.
        """
        try:
            logger.info(f"Pulling Docker image: {docker_image}")
            subprocess.run(
                ["docker", "pull", docker_image],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug(f"Successfully pulled Docker image '{docker_image}'.")
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to pull Docker image '{docker_image}': {e.stderr.strip()}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _is_docker_image_present(self, docker_image: str) -> bool:
        """Checks if the specified Docker image is already present locally.

        Args:
            docker_image (str): The Docker image to check.

        Returns:
            bool: True if the image is present, False otherwise.
        """
        try:
            result = subprocess.run(
                ["docker", "images", "-q", docker_image],
                check=True,
                capture_output=True,
                text=True,
            )
            is_present = bool(result.stdout.strip())
            logger.debug(f"Docker image '{docker_image}' present locally: {is_present}")
            return is_present
        except subprocess.CalledProcessError as e:
            logger.error(f"Error checking Docker images: {e.stderr.strip()}")
            return False

    def _run_docker_command(
        self,
        docker_image: str,
        temp_dir: str,
        host_dir: str | None,
        pip_install_cmd: str,
        memory_limit: str | None,
        environment_vars: str | None,
    ) -> str:
        """Constructs and runs the Docker command to execute the Python script.

        Args:
            docker_image (str): The Docker image to use.
            temp_dir (str): Temporary directory containing the script.
            host_dir (str | None): Host directory to mount, or None to run without it.
            pip_install_cmd (str): Command string for installing packages.
            memory_limit (str | None): Memory limit for Docker container.
            environment_vars (str | None): Environment variables for the Docker container.

        Returns:
            str: The output from executing the command.

        Raises:
            RuntimeError: If executing the Docker command fails.
        """
        docker_run_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{temp_dir}:/usr/src/app",  # Mount temporary directory for scripts
            "-w",
            "/usr/src/app",
        ]

        # Handle optional host directory mounting
        if host_dir:
            if not os.path.isdir(host_dir):
                error_msg = f"Host directory '{host_dir}' does not exist or is not a directory."
                logger.error(error_msg)
                raise ValueError(error_msg)
            docker_run_cmd += ["-v", f"{os.path.abspath(host_dir)}:/usr/src/host_data"]
            docker_run_cmd += ["-v", f"{os.path.abspath(host_dir)}:{os.path.abspath(host_dir)}"]

        # Apply memory limit if specified
        if memory_limit:
            docker_run_cmd += ["-m", memory_limit]
            logger.debug(f"Setting Docker memory limit: {memory_limit}")

        # Set environment variables if provided
        if environment_vars:
            env_pairs = self._parse_environment_vars(environment_vars)
            for key, value in env_pairs.items():
                docker_run_cmd += ["-e", f"{key}={value}"]
            logger.debug(f"Setting Docker environment variables: {env_pairs}")

        # Specify the Docker image and command to execute
        docker_run_cmd.append(docker_image)

        # Construct the command to execute inside the container
        if pip_install_cmd:
            command_with_install = f"{pip_install_cmd} && python3 script.py"
            docker_run_cmd += ["bash", "-c", command_with_install]
            logger.debug("Added installation and execution commands to Docker run command.")
        else:
            # Use bash -c to execute shell commands properly
            venv_and_run = "uv venv && . .venv/bin/activate && python3 script.py"
            docker_run_cmd += ["bash", "-c", venv_and_run]
            logger.debug("Added script execution command to Docker run command.")

        logger.debug(f"Executing Docker command: {' '.join(docker_run_cmd)}")
        try:
            result = subprocess.run(
                docker_run_cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            logger.debug("Docker command executed successfully.")
            result = result.stdout.strip()
            if result == "":
                result = "Script executed successfully."
            return result
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"Docker command failed with return code {e.returncode}.\n"
                f"Docker Command: {' '.join(docker_run_cmd)}\n"
                f"Standard Output:\n{e.stdout}\n"
                f"Standard Error:\n{e.stderr}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except subprocess.TimeoutExpired as e:
            error_msg = "Docker command timed out."
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _parse_environment_vars(self, env_vars_str: str) -> dict:
        """Parses environment variables from a string of KEY=VALUE pairs.

        Args:
            env_vars_str (str): Environment variables string.

        Returns:
            dict: Dictionary of environment variables.

        Raises:
            ValueError: If the environment variables string is malformed.
        """
        env_vars = {}
        for pair in env_vars_str.split():
            if "=" not in pair:
                error_msg = f"Invalid environment variable format: '{pair}'. Expected 'KEY=VALUE'."
                logger.error(error_msg)
                raise ValueError(error_msg)

            key, value = pair.split("=", 1)
            env_vars[key] = value
        logger.debug(f"Parsed environment variables: {env_vars}")
        return env_vars


if __name__ == "__main__":
    # Example usage of PythonTool
    tool = PythonTool()
    install_commands = "pip install rich requests"
    script = """\
from rich import print
print("Hello, World!")
print("This is a Python interpreter tool.")
    """
    version = "3.12"
    host_directory = None  # Replace with actual path if needed
    memory_limit = "1g"  # Example: '512m', '2g'
    environment_variables = "ENV=production DEBUG=False"

    try:
        output = tool.execute(
            install_commands=install_commands,
            script=script,
            version=version,
            host_dir=host_directory,
            memory_limit=memory_limit,
            environment_vars=environment_variables,
        )
        print("Script Output:")
        print(output)
    except Exception as e:
        logger.error(f"An error occurred during script execution: {e}")
        print(f"An error occurred: {e}")

    # Example of writing to host directory
    tool = PythonTool()
    host_directory = "/usr/src/host_data"  # Path inside container mapped to demo03/files
    script = """\
# Write a sample text file to the host directory
with open('/usr/src/host_data/sample.txt', 'w') as f:
    f.write('This is a sample text file created by PythonTool\\n')
print('Successfully wrote sample.txt to host directory')
    """
    try:
        output = tool.execute(
            script=script,
            version="3.12",
            host_dir="./demo03/files",
        )
        print("File Write Output:")
        print(output)
    except Exception as e:
        logger.error(f"An error occurred during file write: {e}")
        print(f"An error occurred: {e}")
