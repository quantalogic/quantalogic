import os

from quantalogic.flow.flow_manager_schema import WorkflowDefinition


def generate_executable_script(workflow_def: WorkflowDefinition, global_vars: dict, output_file: str) -> None:
    """
    Generate an executable Python script from a WorkflowDefinition with global variables.

    Args:
        workflow_def: The WorkflowDefinition object containing the workflow details.
        global_vars: Dictionary of global variables extracted from the source file.
        output_file: The path where the executable script will be written.

    The generated script includes:
    - A shebang using `uv run` for environment management.
    - Metadata specifying the required Python version and dependencies.
    - Global variables from the original script.
    - Embedded functions included directly in the script.
    - Workflow instantiation using direct chaining syntax.
    - A default initial_context matching the example.
    """
    with open(output_file, "w") as f:
        # Write the shebang and metadata
        f.write("#!/usr/bin/env -S uv run\n")
        f.write("# /// script\n")
        f.write('# requires-python = ">=3.12"\n')
        f.write("# dependencies = [\n")
        f.write('#     "loguru",\n')
        f.write('#     "litellm",\n')
        f.write('#     "pydantic>=2.0",\n')
        f.write('#     "anyio",\n')
        f.write('#     "quantalogic>=0.35",\n')
        f.write('#     "jinja2",\n')
        f.write('#     "instructor[litellm]",\n')  # Kept for potential structured LLM support
        f.write("# ]\n")
        f.write("# ///\n\n")

        # Write necessary imports
        f.write("import anyio\n")
        f.write("from typing import List\n")
        f.write("from loguru import logger\n")
        f.write("from quantalogic.flow import Nodes, Workflow\n\n")

        # Write global variables
        for var_name, value in global_vars.items():
            f.write(f"{var_name} = {repr(value)}\n")
        f.write("\n")

        # Embed functions from workflow_def
        for func_name, func_def in workflow_def.functions.items():
            if func_def.type == "embedded":
                f.write(func_def.code + "\n\n")

        # Define workflow using chaining syntax
        f.write("# Define the workflow using simplified syntax with automatic node registration\n")
        f.write("workflow = (\n")
        f.write(f'    Workflow("{workflow_def.workflow.start}")\n')
        for trans in workflow_def.workflow.transitions:
            from_node = trans.from_
            to_node = trans.to
            condition = trans.condition or "None"
            if condition != "None":
                # Ensure condition is formatted as a lambda if not already
                if not condition.startswith("lambda ctx:"):
                    condition = f"lambda ctx: {condition}"
            f.write(f'    .then("{to_node}", condition={condition})\n')
        f.write(")\n\n")

        # Main asynchronous function to run the workflow
        f.write("async def main():\n")
        f.write('    """Main function to run the story generation workflow."""\n')
        f.write("    initial_context = {\n")
        f.write('        "genre": "science fiction",\n')
        f.write('        "num_chapters": 3,\n')
        f.write('        "chapters": [],\n')
        f.write('        "completed_chapters": 0,\n')
        f.write('        "style": "descriptive"\n')
        f.write("    }  # Customize initial_context as needed\n")
        f.write("    engine = workflow.build()\n")
        f.write("    result = await engine.run(initial_context)\n")
        f.write('    logger.info(f"Workflow result: {result}")\n\n')

        # Entry point to execute the main function
        f.write('if __name__ == "__main__":\n')
        f.write("    anyio.run(main)\n")

    # Set executable permissions (rwxr-xr-x)
    os.chmod(output_file, 0o755)
