"""Server-based validation handler for the QuantaLogic agent."""

import asyncio
from typing import Optional
from loguru import logger

class ServerValidationHandler:
    """Handles validation requests through the FastAPI server."""

    def __init__(self, agent_state):
        """Initialize the validation handler with agent state."""
        self.agent_state = agent_state
        self.validation_timeout = 300.0  # Increased to 5 minutes

    async def ask_for_validation(self, question: str, validation_id: Optional[str] = None) -> bool:
        """
        Request user validation through the server.
        
        Args:
            question: The validation question to ask the user
            validation_id: Optional validation ID. If not provided, will be extracted from question
            
        Returns:
            bool: True if validated, False otherwise
        """
        try:
            logger.debug("Starting validation request process")
            if validation_id is None:
                # Assuming validation ID is enclosed in square brackets at the end of the question
                start_idx = question.rfind('[')
                end_idx = question.rfind(']')
                if start_idx != -1 and end_idx != -1:
                    validation_id = question[start_idx + 1:end_idx]
                    logger.debug(f"Extracted validation ID from question: {validation_id}")
                else:
                    logger.error("Validation ID not found in question")
                    raise ValueError("Validation ID not found in question")

            logger.debug(f"Creating response queue for validation ID: {validation_id}")
            response_queue = asyncio.Queue()
            
            # Store the validation request and queue
            self.agent_state.validation_responses[validation_id] = response_queue
            logger.debug(f"Stored response queue. Current queues: {list(self.agent_state.validation_responses.keys())}")
            
            # Get task_id from validation request
            task_id = None
            if validation_id in self.agent_state.validation_requests:
                task_id = self.agent_state.validation_requests[validation_id].task_id
                logger.debug(f"Found task_id for validation: {task_id}")
            
            # Create event data
            event_data = {
                "validation_id": validation_id,
                "question": question,
                "task_id": task_id,
                "tool_name": "validation",
                "arguments": {"question": question}
            }
            logger.debug(f"Created event data: {event_data}")
            
            # Broadcast validation request event
            logger.debug("Broadcasting validation start event")
            self.agent_state.broadcast_event(
                "tool_execute_validation_start",
                event_data,
                task_id=task_id
            )
            
            try:
                # Wait for response with timeout
                logger.info(f"Waiting for validation response for ID: {validation_id}")
                response = await asyncio.wait_for(
                    response_queue.get(), 
                    timeout=self.validation_timeout
                )
                logger.info(f"Received validation response: {response}")
                
                # Broadcast validation end event
                end_event_data = {
                    "validation_id": validation_id,
                    "granted": response,
                    "task_id": task_id,
                    "tool_name": "validation",
                    "arguments": {"question": question},
                    "result": "approved" if response else "rejected"
                }
                logger.debug(f"Broadcasting end event data: {end_event_data}")
                
                # First broadcast the end event
                self.agent_state.broadcast_event(
                    "tool_execute_validation_end",
                    end_event_data,
                    task_id=task_id
                )
                
                # Then clean up the validation queue
                if validation_id in self.agent_state.validation_responses:
                    logger.debug(f"Cleaning up validation queue {validation_id}")
                    del self.agent_state.validation_responses[validation_id]
                    logger.debug(f"Remaining validation queues: {list(self.agent_state.validation_responses.keys())}")
                
                return response
                
            except asyncio.TimeoutError:
                logger.warning(f"Validation request {validation_id} timed out")
                # Broadcast timeout event
                timeout_event_data = {
                    "validation_id": validation_id,
                    "task_id": task_id,
                    "error": "Validation request timed out",
                    "tool_name": "validation"
                }
                self.agent_state.broadcast_event(
                    "tool_execute_validation_end",
                    timeout_event_data,
                    task_id=task_id
                )
                return False
                
        except Exception as e:
            logger.error(f"Error in validation request: {str(e)}", exc_info=True)
            # Broadcast error event
            error_event_data = {
                "validation_id": validation_id,
                "task_id": task_id,
                "error": str(e),
                "tool_name": "validation"
            }
            self.agent_state.broadcast_event(
                "tool_execute_validation_end",
                error_event_data,
                task_id=task_id
            )
            return False
