"""Task execution and chat management for CodeActAgent."""

from typing import Dict, List, Optional

from loguru import logger
from nanoid import generate

from .events import ErrorOccurredEvent
from .llm_util import LLMCompletionError, litellm_completion


class TaskManager:
    """Handles task execution and lifecycle management."""
    
    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
    
    def initialize_task_context(
        self,
        task_id: Optional[str],
        working_memory,
        context_vars: Dict,
        conversation_history_manager,
        system_prompt: Optional[str],
        task: str
    ) -> Dict:
        """Initialize context for a new task."""
        if task_id is None:
            task_id = generate(size=21)
            
        task_context = {
            "aborted": False,
            "abort_message": "",
            "abort_step": None,
            "task_id": task_id
        }
        
        working_memory.clear()
        context_vars.clear()
        
        if system_prompt is not None:
            working_memory.system_prompt = system_prompt
        working_memory.task_description = task
        
        # Initialize context_vars with conversation history
        logger.debug(f"Conversation history: {conversation_history_manager.get_history()}")
        context_vars["conversation_history"] = [
            {"role": message.role, "content": message.content, "nanoid": message.nanoid}
            for message in conversation_history_manager.get_history()
        ]
        
        previous_vars = {
            k: v for k, v in context_vars.items()
            if not k.startswith("__") and not callable(v)
        }
        logger.debug(f"Starting task with context_vars: {previous_vars}")
        
        return task_context
    
    def handle_task_abortion(self, task_context: Dict, step: int) -> None:
        """Handle task abortion due to user cancellation."""
        task_context["aborted"] = True
        task_context["abort_message"] = f"Task aborted by user at step {step} - confirmation declined"
        task_context["abort_step"] = step
        logger.debug(f"Task context marked as aborted - {task_context['abort_message']}")
    
    def format_final_result(self, task_context: Dict, working_memory, max_iters: int) -> List[Dict]:
        """Format the final task result based on completion status."""
        if task_context["aborted"]:
            return [
                {
                    "step_number": step.step_number,
                    "thought": step.thought,
                    "action": step.action,
                    "result": step.result.dict() if hasattr(step.result, 'dict') else {},
                    "aborted": True if task_context["abort_step"] and step.step_number == task_context["abort_step"] else False
                }
                for step in working_memory.store
            ] + [{"error": task_context["abort_message"], "aborted": True, "task_status": "aborted"}]
        
        return [
            {
                "step_number": step.step_number,
                "thought": step.thought,
                "action": step.action,
                "result": step.result.dict(),
            }
            for step in working_memory.store
        ]


class ChatManager:
    """Handles chat interactions."""
    
    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
    
    def prepare_chat_messages(
        self,
        working_memory,
        conversation_history_manager,
        message: str
    ) -> List[Dict[str, str]]:
        """Prepare messages for chat completion."""
        messages = [
            {"role": "system", "content": working_memory.system_prompt or "You are a helpful AI assistant."}
        ]
        
        # Include conversation history
        for hist_msg in conversation_history_manager.get_history():
            role = str(hist_msg.role)
            content = str(hist_msg.content)
            messages.append({"role": role, "content": content})
        
        messages.append({"role": "user", "content": str(message)})
        return messages
    
    async def handle_chat_completion(
        self,
        reasoner,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        streaming: bool,
        notify_observers,
        task_id: str
    ) -> str:
        """Handle the actual chat completion request."""
        try:
            response = await litellm_completion(
                model=reasoner.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=streaming,
                notify_event=notify_observers if streaming else None,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                task_id=task_id
            )
            return response.strip()
        except LLMCompletionError as e:
            logger.error(f"Chat failed: {e}")
            await notify_observers(
                ErrorOccurredEvent(
                    event_type="ErrorOccurred",
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    error_message=str(e),
                    step_number=1,
                    task_id=task_id
                )
            )
            raise
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return f"Error: Unable to process chat request due to {str(e)}"
