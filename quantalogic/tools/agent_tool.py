"""Agent Tool for delegating tasks to another agent."""

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

from quantalogic.tools.tool import Tool, ToolArgument

# Use conditional import to resolve circular dependency
if TYPE_CHECKING:
    from quantalogic.agent import Agent


class AgentTool(Tool):
    """Tool to execute tasks using another agent."""

    name: str = Field(default="agent_tool")
    description: str = Field(
        default=(
            "Executes tasks using a specified agent. "
            "This tool enables an agent to delegate tasks to another agent."
            "A delegate agent doesn't have access to the memory and the conversation of the main agent."
            "Context must be provided by the main agent."
            "You must use variable interpolation syntax to use the context of the main agent."
        )
    )
    agent_role: str = Field(..., description="The role of the agent (e.g., expert, assistant)")
    agent: Any = Field(..., description="The agent to delegate tasks to")

    # Type hint for static type checkers
    if TYPE_CHECKING:
        agent: "Agent"

    # Allow extra fields
    model_config = {"extra": "allow"}

    # Tool Arguments
    arguments: list[ToolArgument] = Field(
        default_factory=lambda: [
            ToolArgument(
                name="task",
                arg_type="string",
                description="The task to delegate to the specified agent.",
                required=True,
                example="Summarize the latest news.",
            ),
        ]
    )

    @model_validator(mode="before")
    def validate_agent(cls, values: dict[str, Any]) -> dict[str, Any]:  # noqa: N805
        """Validate the provided agent and its role."""
        agent = values.get("agent")
        # Lazy import to avoid circular dependency
        from quantalogic.agent import Agent

        if not isinstance(agent, Agent):
            raise ValueError("The agent must be an instance of the Agent class.")
        return values

    def execute(self, task: str) -> str:
        """Execute the tool to delegate a task to the specified agent.

        Args:
            task (str): The task to delegate to the agent.

        Returns:
            str: The result of the delegated task.
        """
        try:
            logging.info(f"Delegating task to agent with role '{self.agent_role}': {task}")
            # Lazy import to avoid circular dependency
            from quantalogic.agent import Agent

            # Ensure the agent is of the correct type
            if not isinstance(self.agent, Agent):
                raise ValueError("The agent must be an instance of the Agent class.")

            # Delegate the task to the agent
            result = self.agent.solve_task(task)

            logging.info(f"Task delegation completed for agent with role '{self.agent_role}'")
            return result

        except Exception as e:
            logging.error(f"Error delegating task to agent: {str(e)}")
            raise
