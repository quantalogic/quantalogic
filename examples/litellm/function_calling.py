#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "litellm>=1.59.8",
#     "loguru",
#     "pydantic>=2.0.0",
#     "python-dotenv"
# ]
# ///

import inspect
import json
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from litellm import Router, acompletion
from loguru import logger
from pydantic import BaseModel, Field

MODEL_NAME = "openrouter/openai/gpt-4o-mini"

# Load environment variables
load_dotenv()

# Enhanced logging configuration
logger.add(
    f"logs/react_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    rotation="10 MB",
    compression="zip",
    backtrace=True,
    diagnose=True,
    level="DEBUG"
)

def validate_openrouter_config():
    """Validate OpenRouter API configuration."""
    logger.debug("Validating OpenRouter configuration")
    api_key = os.getenv("OPENROUTER_API_KEY")
    site_url = os.getenv("OR_SITE_URL", "https://github.com/raphaelmansuy/quantalogic")
    app_name = os.getenv("OR_APP_NAME", "QuantaLogic ReAct Agent")
    
    logger.debug(f"Site URL: {site_url}")
    logger.debug(f"App Name: {app_name}")
    
    if not api_key:
        logger.error("""
        ❌ OpenRouter API Configuration Error
        
        Required steps:
        1. Sign up at https://openrouter.ai/
        2. Create an API key in your account settings
        3. Set environment variables:
           - OPENROUTER_API_KEY: Your OpenRouter API key
           - Optional: OR_SITE_URL (default: GitHub repo)
           - Optional: OR_APP_NAME (default: QuantaLogic ReAct Agent)
        
        Example .env file:
        OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        OR_SITE_URL=https://github.com/raphaelmansuy/quantalogic
        OR_APP_NAME=QuantaLogic ReAct Agent
        """)
        raise ValueError("OpenRouter API Key is required. Please configure your environment.")
    
    # Set environment variables for LiteLLM
    os.environ["OPENROUTER_API_KEY"] = api_key
    os.environ["OR_SITE_URL"] = site_url
    os.environ["OR_APP_NAME"] = app_name
    
    logger.info(f"OpenRouter configuration validated successfully")
    logger.debug(f"API Key present: {bool(api_key)}")
    logger.debug(f"Site URL: {site_url}")
    logger.debug(f"App Name: {app_name}")

class ThoughtProcess(str, Enum):
    REASONING = "reasoning"
    OBSERVATION = "observation"
    ACTION = "action"
    REFLECTION = "reflection"

class AgentAction(BaseModel):
    thought: str = Field(..., description="Current reasoning step")
    action: str = Field(..., description="Function to execute")
    action_input: Dict[str, Any] = Field(..., description="Function parameters")
    
class AgentObservation(BaseModel):
    thought_type: ThoughtProcess
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

class ReActAgent:
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_steps: int = 10,
        temperature: float = 0.7
    ):
        logger.debug(f"Initializing ReActAgent")
        logger.debug(f"Model: {model_name}")
        logger.debug(f"Max Steps: {max_steps}")
        logger.debug(f"Temperature: {temperature}")
        
        self.model_name = model_name
        self.max_steps = max_steps
        self.temperature = temperature
        self.function_map = self._initialize_functions()
        self.functions_schema = self._generate_function_schema()
        self.system_prompt = self._generate_system_prompt()
        self.conversation_history: List[AgentObservation] = []
        
        logger.debug(f"Available functions: {list(self.function_map.keys())}")
        logger.debug(f"Functions schema generated")
        
    def _initialize_functions(self) -> Dict[str, callable]:
        """Initialize available functions with enhanced error handling."""
        logger.debug("Initializing agent functions")
        base_functions = {
            "add": lambda a, b: float(a + b),
            "subtract": lambda a, b: float(a - b),
            "multiply": lambda a, b: float(a * b),
            "divide": lambda a, b: float(a / b) if b != 0 else None,
            "sqrt": lambda a: float(a ** 0.5) if a >= 0 else None,
            "print_answer": lambda answer: str(answer)
        }
        
        # Add function metadata
        for name, func in base_functions.items():
            func.__name__ = name
            func.__doc__ = f"Execute {name} operation"
            
        logger.debug(f"Initialized {len(base_functions)} base functions")
        return base_functions

    def _generate_function_schema(self) -> List[Dict[str, Any]]:
        """Generate enhanced OpenAI-compatible function schemas."""
        schemas = []
        for func_name, func in self.function_map.items():
            signature = inspect.signature(func)
            
            properties = {}
            required = []
            
            for param_name, param in signature.parameters.items():
                param_type = "number" if param_name != "answer" else "string"
                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name} for {func_name} operation"
                }
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
            
            schemas.append({
                "name": func_name,
                "description": func.__doc__ or f"Execute {func_name} operation",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })
        return schemas

    def _generate_system_prompt(self) -> str:
        """Generate comprehensive system prompt with enhanced guidelines."""
        return f"""You are an advanced ReAct (Reasoning + Acting) agent that excels at:
1. Breaking down complex problems into steps
2. Maintaining a clear thought process
3. Using available tools effectively
4. Learning from previous steps

Follow these guidelines for each interaction:

1. REASONING:
   - Always explain your thought process
   - Break down complex calculations
   - Consider edge cases

2. ACTION:
   - Use appropriate functions for calculations
   - Validate inputs before operations
   - Handle errors gracefully

3. OBSERVATION:
   - Analyze function results
   - Track intermediate steps
   - Update your understanding

4. REFLECTION:
   - Verify if the solution is complete
   - Consider if additional steps are needed
   - Use print_answer only for final results

Available Functions:
{json.dumps(self._generate_function_schema(), indent=2)}

Remember: ALWAYS use print_answer as the final step to display results.
"""

    async def process_step(
        self,
        messages: List[Dict[str, str]],
        prev_observation: Optional[AgentObservation] = None
    ) -> Union[str, AgentAction]:
        """Process a single step in the reasoning chain with enhanced error handling."""
        logger.info(f"Processing step with model: {self.model_name}")
        logger.debug(f"Messages: {messages}")
        
        try:
            logger.debug("Attempting async completion")
            response = await acompletion(
                model=self.model_name,
                messages=messages,
                tools=[{"type": "function", "function": func} for func in self.functions_schema],
                temperature=self.temperature,
                # Add OpenRouter-specific parameters
                extra_headers={
                    "HTTP-Referer": os.getenv("OR_SITE_URL", ""),
                    "X-Title": os.getenv("OR_APP_NAME", "")
                }
            )
            
            # Log raw response details
            logger.debug(f"Completion response received")
            logger.debug(f"Response choices: {len(response.choices)}")
            
            # Extract the first choice message from the response
            assistant_message = response.choices[0].message
            
            logger.debug(f"Assistant message content: {assistant_message.content}")
            logger.debug(f"Tool calls present: {bool(assistant_message.tool_calls)}")
            
            if tool_calls := assistant_message.tool_calls:
                tool_call = tool_calls[0]
                logger.info("Function call detected")
                logger.debug(f"Function name: {tool_call.function.name}")
                logger.debug(f"Function arguments: {tool_call.function.arguments}")
                
                return AgentAction(
                    thought=assistant_message.content or '',
                    action=tool_call.function.name,
                    action_input=json.loads(tool_call.function.arguments)
                )
            
            logger.info("Returning text response")
            return assistant_message.content or ''
            
        except Exception as e:
            # Log detailed error information
            logger.exception(f"Error in process_step: {str(e)}")
            
            # Specific error handling for common LiteLLM/OpenRouter issues
            if "APIError" in str(type(e)):
                logger.error("""
                OpenRouter API Error Troubleshooting:
                1. Verify API key is correct and active
                2. Check your account balance
                3. Confirm model availability
                4. Check network connectivity
                5. Verify OpenRouter service status
                """)
            
            raise RuntimeError(f"Process step failed: {str(e)}")

    async def run(self, query: str) -> str:
        """Execute the ReAct agent's reasoning chain."""
        logger.info(f"Starting agent run with query: {query}")
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.append({"role": "user", "content": query})
        
        logger.debug("Initial message stack prepared")
        
        steps_taken = 0
        last_observation = None
        
        while steps_taken < self.max_steps:
            logger.debug(f"Reasoning step {steps_taken + 1}")
            
            try:
                result = await self.process_step(messages, last_observation)
                
                if isinstance(result, str):
                    logger.info("Final result obtained")
                    return result
                
                if isinstance(result, AgentAction):
                    # Execute action and record observation
                    observation = self._execute_action(result)
                    last_observation = observation
                    self.conversation_history.append(observation)
                    
                    logger.debug(f"Action executed: {result.action}")
                    logger.debug(f"Observation: {observation.content}")
                    
                    if observation.thought_type == ThoughtProcess.REFLECTION:
                        logger.info("Reflection reached, returning result")
                        return observation.content
                
                steps_taken += 1
                
            except Exception as e:
                logger.exception(f"Error in reasoning chain at step {steps_taken}")
                raise
        
        logger.warning(f"Max steps ({self.max_steps}) reached without resolution")
        return "Unable to complete task within maximum steps"

    def _execute_action(self, action: AgentAction) -> AgentObservation:
        """Execute an action and return an observation."""
        try:
            func = self.function_map[action.action]
            result = func(**action.action_input)
            
            return AgentObservation(
                thought_type=ThoughtProcess.OBSERVATION,
                content=f"Action '{action.action}' completed with result: {result}"
            )
            
        except Exception as e:
            logger.exception(f"Action execution failed: {action.action}")
            return AgentObservation(
                thought_type=ThoughtProcess.REFLECTION,
                content=f"Error executing {action.action}: {str(e)}"
            )

async def main():
    try:
        validate_openrouter_config()
    except ValueError as e:
        logger.error(str(e))
        return
    
    agent = ReActAgent()
    logger.info("ReAct Agent initialized")
    
    while True:
        try:
            query = input("\nEnter your query (or 'exit' to quit): ").strip()
            
            if query.lower() == 'exit':
                break
                
            result = await agent.run(query)
            print(f"\nResult: {result}")
            
        except KeyboardInterrupt:
            logger.info("Agent terminated by user")
            break
        except Exception as e:
            logger.exception("Unexpected error in main loop")
            print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())