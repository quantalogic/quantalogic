#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio",
#     "quantalogic>=0.35",
#     "jinja2",
#     "instructor[litellm]",
# ]
# ///

import anyio
from typing import List
from loguru import logger
from quantalogic.flow import Nodes, Workflow

MY_CONSTANT = 42

@Nodes.define(output='greeting')
async def greet(name): return f'Hello, {name}!'

@Nodes.define(output='condition')
async def check(name): return len(name) > 3

@Nodes.define(output='farewell')
async def end(greeting): return f'{greeting} Goodbye!'

# Define the workflow with branch, converge, and loop support
workflow = (
    Workflow("greet")
    .node("greet", inputs_mapping={'name': 'user_name'})
    .node("check")
    .node("end")
    .branch([("check", lambda ctx: ctx['name'] == 'Alice')])
    .converge("end")
)

async def main():
    """Main function to run the workflow."""
    # Customize initial_context as needed
    # Inferred required inputs:
    # name, user_name
    initial_context = {
        'name': '',
        'user_name': '',
    }
    engine = workflow.build()
    result = await engine.run(initial_context)
    logger.info(f"Workflow result: {result}")

if __name__ == "__main__":
    anyio.run(main)
