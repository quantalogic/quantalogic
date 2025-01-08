"""Tool to execute Node.js scripts in an isolated Docker environment."""

import json
import logging
import os
import subprocess
import tempfile

from quantalogic.tools.tool import Tool, ToolArgument

# Configure logging for the module
logger = logging.getLogger(__name__)


class NodeJsTool(Tool):
    """Tool to execute Node.js scripts in an isolated Docker environment."""

    name: str = "nodejs_tool"
    description: str = (
        "Executes a Node.js script (ESM or CommonJS) within a Docker container using npm for package management.\n\n"
        "CONSOLE OUTPUT REQUIREMENTS:\n"
        "1. Only Node.js code that produces text output via console.log() statements is accepted\n"
        "2. No GUI, no plots, no visualizations - strictly console/terminal output\n"
        "3. No file operations or external resources unless explicitly authorized\n\n"
        "EXECUTION ENVIRONMENT:\n"
        "- Runs in an isolated Docker container\n"
        "- Node.js version can be specified (default: Node.js LTS)\n"
        "- Required packages can be installed via npm\n"
        "- Standard Node.js modules are available\n\n"
        "ACCEPTED OUTPUT METHODS:\n"
        "✓ console.log()\n"
        "✓ console.info()\n"
        "✓ process.stdout.write()\n"
        "✗ No browser-based output\n"
        "✗ No external file generation\n"
        "✗ No web servers or network services\n\n"
        "EXAMPLE:\n"
        "console.log('Hello, World!')  # ✓ Valid\n"
        "window.alert()                # ✗ Invalid\n"
    )
    need_validation: bool = True
    arguments: list[ToolArgument] = [
        ToolArgument(
            name="install_commands",
            arg_type="string",
            description=(
                "Commands to install Node.js packages before running the script. "
                "Use one command per line or separate packages with spaces."
            ),
            required=False,
            example="npm install chalk axios",
        ),
        ToolArgument(
            name="script",
            arg_type="string",
            description=(
                "The Node.js script to execute. The script must print to the console. "
                "Use import statements for ESM or require statements for CommonJS."
            ),
            required=True,
            example='import fs from "fs";\nconsole.log("Hello, World!");\nconsole.log("This is a Node.js interpreter tool.");',
        ),
        ToolArgument(
            name="version",
            arg_type="string",
            description=("The Node.js version to use in the Docker container. " "For example:  '18', '20', 'lts'."),
            required=True,
            default="lts",
            example="20",
        ),
        ToolArgument(
            name="host_dir",
            arg_type="string",
            description=(
                "The absolute path on the host machine to mount for file access. "
                "Provide this path if you want to access files on the host."
            ),
            required=False,
            default=os.getcwd(),
            example="./project/",
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
            example="NODE_ENV=production DEBUG=false",
        ),
        # New Argument for Module Type
        ToolArgument(
            name="module_type",
            arg_type="string",
            description=("The module system to use: 'esm' for ECMAScript Modules or 'commonjs' for CommonJS."),
            required=True,
            default="esm",
            example="commonjs",
        ),
    ]

    def execute(
        self,
        install_commands: str | None = None,
        script: str = "",
        version: str = "lts",
        host_dir: str | None = None,
        memory_limit: str | None = None,
        environment_vars: str | None = None,
        module_type: str = "esm",
    ) -> str:
        """Executes a Node.js script (ESM or CommonJS) within a Docker container using npm for package management.

        Args:
            install_commands (str | None): Installation commands for dependencies.
            script (str): The Node.js script to execute.
            version (str): Node.js version to use.
            host_dir (str | None): Host directory to mount for file access.
            memory_limit (str | None): Memory limit for Docker container (e.g., '512m', '2g').
            environment_vars (str | None): Environment variables for the Docker container.
            module_type (str): The module system to use ('esm' or 'commonjs').

        Returns:
            str: The output of the executed script or error messages.

        Raises:
            ValueError: If the Node.js version is unsupported or inputs are invalid.
            RuntimeError: If Docker commands fail or Docker is not available.
        """
        self._check_docker_availability()
        self._validate_nodejs_version(version)
        self._validate_module_type(module_type)

        # Determine Docker image based on Node.js version
        docker_image = f"node:{version}-slim"

        if not self._is_docker_image_present(docker_image):
            self._pull_docker_image(docker_image)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Determine script filename based on module type
            script_extension = "mjs" if module_type == "esm" else "cjs"
            script_filename = f"script.{script_extension}"
            script_path = os.path.join(temp_dir, script_filename)
            self._write_script(script_path, script, module_type)

            # Create package.json if installing dependencies or to specify module type
            if install_commands or module_type:
                self._create_package_json(temp_dir, module_type)

            # Prepare npm install commands
            npm_install_cmd = self._prepare_install_commands(install_commands)

            # Run the Docker command and return the output
            return self._run_docker_command(
                docker_image=docker_image,
                temp_dir=temp_dir,
                host_dir=host_dir,
                npm_install_cmd=npm_install_cmd,
                memory_limit=memory_limit,
                environment_vars=environment_vars,
                script_filename=script_filename,
                module_type=module_type,
            )

    def _validate_nodejs_version(self, version: str) -> None:
        """Validates whether the specified Node.js version is supported.

        Args:
            version (str): Node.js version to validate.

        Raises:
            ValueError: If the Node.js version is unsupported.
        """
        valid_versions = ["16", "18", "20", "lts"]
        if version not in valid_versions:
            error_msg = f"Unsupported Node.js version '{version}'. " f"Supported versions: {', '.join(valid_versions)}."
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.debug(f"Node.js version '{version}' is supported.")

    def _validate_module_type(self, module_type: str) -> None:
        """Validates whether the specified module type is supported.

        Args:
            module_type (str): Module type to validate.

        Raises:
            ValueError: If the module type is unsupported.
        """
        valid_module_types = ["esm", "commonjs"]
        if module_type not in valid_module_types:
            error_msg = (
                f"Unsupported module type '{module_type}'. " f"Supported types: {', '.join(valid_module_types)}."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.debug(f"Module type '{module_type}' is supported.")

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

    def _write_script(self, path: str, script: str, module_type: str) -> None:
        """Writes the provided Node.js script to a specified file.

        Args:
            path (str): The path to write the script.
            script (str): The content of the script.
            module_type (str): The module system ('esm' or 'commonjs').

        Raises:
            ValueError: If the script content is empty.
        """
        if not script.strip():
            error_msg = "The provided Node.js script is empty."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Optional: Provide warnings if the script doesn't match the module type
        if module_type == "esm":
            if not any(script.lstrip().startswith(keyword) for keyword in ("import ", "export ")):
                logger.warning("ESM module type selected, but the script does not contain import/export statements.")
        elif module_type == "commonjs":
            if "require(" not in script and not any(
                script.lstrip().startswith(keyword) for keyword in ("const ", "let ", "var ")
            ):
                logger.warning("CommonJS module type selected, but the script does not contain require statements.")

        with open(path, "w", encoding="utf-8") as script_file:
            script_file.write(script)
            logger.debug(f"Node.js script written to {path}")

    def _create_package_json(self, dir_path: str, module_type: str) -> None:
        """Creates a package.json file in the specified directory, specifying the module type.

        Args:
            dir_path (str): Directory where package.json should be created.
            module_type (str): The module system ('esm' or 'commonjs').
        """
        package_json = {
            "name": "script",
            "version": "1.0.0",
            "description": "Temporary Node.js script",
            "main": f"script.{ 'mjs' if module_type == 'esm' else 'cjs' }",
            "type": "module" if module_type == "esm" else "commonjs",
        }

        # For CommonJS, it's usually optional to set 'type', but in Node.js, 'type' defaults to CommonJS
        # However, to ensure compatibility, we remove 'type' if 'commonjs' is chosen
        if module_type == "commonjs":
            del package_json["type"]

        with open(os.path.join(dir_path, "package.json"), "w", encoding="utf-8") as f:
            json.dump(package_json, f, indent=2)
        logger.debug(f"Created package.json in {dir_path} with module type '{module_type}'.")

    def _prepare_install_commands(self, install_commands: str | None) -> str:
        """Prepares installation commands for npm.

        Args:
            install_commands (str | None): Installation commands provided by the user.

        Returns:
            str: A single npm install command string.
        """
        if install_commands:
            packages = set()
            for line in install_commands.splitlines():
                parts = line.strip().split()
                if parts and parts[0].lower() == "npm" and parts[1].lower() == "install":
                    packages.update(parts[2:])
                else:
                    packages.update(parts)

            if packages:
                install_command = "npm install " + " ".join(packages)
                logger.debug(f"Prepared npm install command: {install_command}")
                return install_command

        logger.debug("No installation commands provided.")
        return ""

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

    def _pull_docker_image(self, docker_image: str) -> None:
        """Pulls the specified Docker image.

        Args:
            docker_image (str): The name of the Docker image to pull.

        Raises:
            RuntimeError: If pulling the Docker image fails.
        """
        try:
            logger.debug(f"Pulling Docker image: {docker_image}")
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

    def _run_docker_command(
        self,
        docker_image: str,
        temp_dir: str,
        host_dir: str | None,
        npm_install_cmd: str,
        memory_limit: str | None,
        environment_vars: str | None,
        script_filename: str,
        module_type: str,
    ) -> str:
        """Constructs and runs the Docker command to execute the Node.js script.

        Args:
            docker_image (str): The Docker image to use.
            temp_dir (str): Temporary directory containing the script.
            host_dir (str | None): Host directory to mount, or None to run without it.
            npm_install_cmd (str): Command string for installing packages.
            memory_limit (str | None): Memory limit for Docker container.
            environment_vars (str | None): Environment variables for the Docker container.
            script_filename (str): The name of the script file.
            module_type (str): The module system ('esm' or 'commonjs').

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
            f"{temp_dir}:/usr/src/app",
            "-w",
            "/usr/src/app",
        ]

        if host_dir:
            if not os.path.isdir(host_dir):
                error_msg = f"Host directory '{host_dir}' does not exist or is not a directory."
                logger.error(error_msg)
                raise ValueError(error_msg)
            docker_run_cmd += ["-v", f"{os.path.abspath(host_dir)}:/usr/src/host_data"]

        if memory_limit:
            docker_run_cmd += ["-m", memory_limit]

        if environment_vars:
            env_pairs = self._parse_environment_vars(environment_vars)
            for key, value in env_pairs.items():
                docker_run_cmd += ["-e", f"{key}={value}"]

        docker_run_cmd.append(docker_image)

        # Determine the command to run based on module type
        if npm_install_cmd:
            command_with_install = f"{npm_install_cmd} 1>2 && node {script_filename}"
            docker_run_cmd += ["sh", "-c", command_with_install]
        else:
            docker_run_cmd += ["node", script_filename]

        logger.debug(f"Docker run command: {' '.join(docker_run_cmd)}")

        try:
            result = subprocess.run(
                docker_run_cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            logger.debug(f"Docker command stdout: {result.stdout}")
            logger.debug(f"Docker command stderr: {result.stderr}")
            return result.stdout
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


if __name__ == "__main__":
    # Example usage of NodeJsTool
    tool = NodeJsTool()
    install_commands = "npm install chalk"

    # Example ESM script
    esm_script = """\
import chalk from 'chalk';
console.log(chalk.blue('Hello, ESM World!'));
console.log('This is a Node.js interpreter tool using ESM.');
    """

    # Example CommonJS script
    commonjs_script = """\
const chalk = require('chalk');
console.log(chalk.green('Hello, CommonJS World!'));
console.log('This is a Node.js interpreter tool using CommonJS.');
    """

    version = "20"
    host_directory = None
    memory_limit = "1g"
    environment_variables = "NODE_ENV=production DEBUG=false"

    # Choose the module type and corresponding script
    module_type = "esm"  # Change to "commonjs" for CommonJS scripts
    script = esm_script if module_type == "esm" else commonjs_script

    try:
        output = tool.execute(
            install_commands=install_commands,
            script=script,
            version=version,
            host_dir=host_directory,
            memory_limit=memory_limit,
            environment_vars=environment_variables,
            module_type=module_type,
        )
        print("Script Output:")
        print(output)
    except Exception as e:
        logger.error(f"An error occurred during script execution: {e}")
        print(f"An error occurred: {e}")
