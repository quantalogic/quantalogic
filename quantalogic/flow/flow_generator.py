import os
import pprint

from quantalogic.flow.flow_manager_schema import WorkflowDefinition


def generate_executable_script(workflow_def: WorkflowDefinition, output_file: str) -> None:
    """
    Generate an executable Python script from a WorkflowDefinition.

    Args:
        workflow_def: The WorkflowDefinition object containing the workflow details.
        output_file: The path where the executable script will be written.

    The generated script includes:
    - A shebang using `uv run` for environment management.
    - Metadata specifying the required Python version and dependencies.
    - Support for embedded functions (included directly in the script).
    - Support for external Python modules (via imports handled by WorkflowManager).
    - Workflow instantiation and execution logic using WorkflowManager.
    """
    with open(output_file, 'w') as f:
        # Write the shebang and metadata
        f.write('#!/usr/bin/env -S uv run\n')
        f.write('# /// script\n')
        f.write('# requires-python = ">=3.12"\n')
        f.write('# dependencies = [\n')
        f.write('#     "loguru",\n')
        f.write('#     "litellm",\n')
        f.write('#     "pydantic>=2.0",\n')
        f.write('#     "anyio",\n')
        f.write('#     "quantalogic>=0.35",\n')
        f.write('#     "jinja2",\n')
        f.write('#     "instructor[litellm]",\n')
        f.write('# ]\n')
        f.write('# ///\n\n')

        # Write necessary imports
        f.write('import asyncio\n')
        f.write('from loguru import logger\n')
        f.write('from quantalogic.flow import Nodes, Workflow, WorkflowEngine\n')
        f.write('from quantalogic.flow.flow_manager import WorkflowManager\n')
        f.write('from quantalogic.flow.flow_manager_schema import WorkflowDefinition\n\n')

        # Embed functions from workflow_def
        for func_name, func_def in workflow_def.functions.items():
            if func_def.type == "embedded":
                f.write(func_def.code + '\n\n')

        # Serialize workflow_def to a nicely formatted dictionary string
        workflow_def_str: str = pprint.pformat(workflow_def.model_dump(), indent=4)

        # Main asynchronous function to run the workflow
        f.write('async def main():\n')
        f.write(f'    workflow_def_data = {workflow_def_str}\n')
        f.write('    workflow_def = WorkflowDefinition.model_validate(workflow_def_data)\n')
        f.write('    manager = WorkflowManager(workflow_def)\n')
        f.write('    workflow = manager.instantiate_workflow()\n')
        f.write('    # Set initial_context based on workflow requirements, e.g., {"genre": "science fiction", "num_chapters": 3}\n')
        f.write('    initial_context = {}\n')
        f.write('    engine = workflow.build()\n')
        f.write('    result = await engine.run(initial_context)\n')
        f.write('    logger.info(f"Workflow result: {{result}}")\n\n')

        # Entry point to execute the main function
        f.write('if __name__ == "__main__":\n')
        f.write('    asyncio.run(main())\n')

    # Set executable permissions (rwxr-xr-x)
    os.chmod(output_file, 0o755)