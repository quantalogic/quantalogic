from abc import ABC, abstractmethod
from typing import Tuple

from loguru import logger

from .events import ExecutionResult
from .llm_util import litellm_completion
from .templates import jinja_env


class CompletionEvaluator(ABC):
    """Abstract base class for evaluating task completion."""
    
    @abstractmethod
    async def evaluate_completion(
        self,
        task: str,
        formatted_history: str,
        result: ExecutionResult,
        success_criteria: str | None,
        model: str,
        temperature: float
    ) -> Tuple[bool, str]:
        """Evaluate whether the task is complete based on the provided inputs.

        Args:
            task: The task being evaluated.
            formatted_history: Formatted history of previous steps.
            result: The execution result from the latest step.
            success_criteria: Optional string to check against the result.
            model: The language model identifier for LLM verification.
            temperature: Sampling temperature for LLM calls.

        Returns:
            Tuple[bool, str]: (is_complete, final_answer)
        """
        pass


class DefaultCompletionEvaluator(CompletionEvaluator):
    """Default implementation of task completion evaluation."""
    
    async def evaluate_completion(
        self,
        task: str,
        formatted_history: str,
        result: ExecutionResult,
        success_criteria: str | None,
        model: str,
        temperature: float
    ) -> Tuple[bool, str]:
        """Check if the task is complete based on execution result and criteria."""
        try:
            if result.execution_status != "success":
                logger.info(f"Task not complete at step due to execution error: {result.error}")
                return False, ""

            task_status = result.task_status
            final_answer = result.result or ""

            # Use LLM to verify completion if task is marked as completed
            if task_status == "completed":
                template = jinja_env.get_template("is_task_complete.j2")
                verification_prompt = template.render(
                    task=task,
                    final_answer=final_answer,
                    task_status=task_status,
                    reason="Task marked as completed by execution result",
                    history=formatted_history
                )
                verification = await litellm_completion(
                    model=model,
                    messages=[{"role": "user", "content": verification_prompt}],
                    max_tokens=20,
                    temperature=temperature,
                    stream=False
                )
                verification = verification.lower().strip()
                if verification == "yes":
                    logger.info(f"Task verified as complete: {final_answer}")
                    return True, final_answer
                elif verification == "not_solvable":
                    logger.info(f"Task deemed unsolvable: {final_answer}")
                    return True, f"Task is unsolvable: {final_answer}"
                elif verification == "no":
                    logger.info(f"LLM judge indicates task is not complete: '{verification}'")
                    return False, ""
                else:
                    logger.warning(f"Unexpected judge response: '{verification}', treating as 'no'")
                    return False, ""

            # Check success criteria if provided
            if success_criteria and final_answer and success_criteria in final_answer:
                logger.info(f"Task completed based on success criteria: {success_criteria}")
                return True, final_answer

            logger.info("Task not complete: in progress or no criteria met")
            return False, ""
        except Exception as e:
            logger.error(f"Error checking task completion: {e}")
            return False, ""