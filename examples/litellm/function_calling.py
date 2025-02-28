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
import xml.sax.saxutils as sax
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from dotenv import load_dotenv
from litellm import acompletion
from loguru import logger
from pydantic import BaseModel, Field

# MODEL_NAME = "openrouter/openai/gpt-4o-mini"
MODEL_NAME = "lm_studio/virtuoso-lite"
MODEL_NAME = "lm_studio/deepseek-r1-distill-qwen-7b"
MODEL_NAME = "lm_studio/phi-4@8bit"
MODEL_NAME = "lm_studio/qwen2.5-coder-3b-instruct-mlx@8bit"
MODEL_NAME = "lm_studio/llama-3.2-3b-instruct"
# MODEL_NAME = "lm_studio/deepseek-r1-distill-qwen-32b"
# MODEL_NAME = "openrouter/anthropic/claude-3-opus"  # Alternative option

# Load environment variables
load_dotenv()

# Enhanced logging configuration
logger.add(
    f"logs/react_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    rotation="10 MB",
    compression="zip",
    backtrace=True,
    diagnose=True,
    level="DEBUG",
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
        temperature: float = 0.7,
        functions: Optional[List[Callable]] = None,
        stream_handlers: Optional[List[Callable[[str, str], None]]] = None,
    ):
        logger.debug("Initializing ReActAgent")
        logger.debug(f"Model: {model_name}")
        logger.debug(f"Max Steps: {max_steps}")
        logger.debug(f"Temperature: {temperature}")

        self.model_name = model_name
        self.max_steps = max_steps
        self.temperature = temperature
        self.function_map = self._initialize_functions(functions)
        self.functions_schema = self._generate_function_schema()
        self.system_prompt = self._generate_system_prompt()
        self.conversation_history: List[AgentObservation] = []
        self.stream_handlers = stream_handlers or []

        logger.debug(f"Available functions: {list(self.function_map.keys())}")
        logger.debug("Functions schema generated")
        logger.debug(f"Stream handlers registered: {len(self.stream_handlers)}")

    def _initialize_functions(self, functions: Optional[List[Callable]]) -> Dict[str, Callable]:
        """Initialize functions with either provided list or defaults."""
        logger.debug("Initializing agent functions")

        if functions:
            return self._process_custom_functions(functions)
        return self._create_default_functions()

    def _process_custom_functions(self, functions: List[Callable]) -> Dict[str, Callable]:
        """Process user-provided functions with validation."""
        function_map = {}
        for func in functions:
            if not callable(func):
                raise ValueError(f"Provided function {func} is not callable")

            name = getattr(func, "__name__", None)
            if not name:
                raise ValueError(f"Function {func} must have a __name__ attribute")

            # Add metadata if missing
            if not func.__doc__:
                func.__doc__ = f"Execute {name} operation"
                logger.warning(f"Added default docstring to function: {name}")

            function_map[name] = func
            logger.info(f"Registered custom function: {name}")

        # Ensure print_answer is always present
        if "print_answer" not in function_map:
            function_map["print_answer"] = self._create_print_answer()
            logger.info("Added default print_answer function")

        return function_map

    def _create_default_functions(self) -> Dict[str, Callable]:
        """Create default math functions with metadata and type annotations."""

        def add(a: float, b: float) -> float:
            return a + b

        def subtract(a: float, b: float) -> float:
            return a - b

        def multiply(a: float, b: float) -> float:
            return a * b

        def divide(a: float, b: float) -> Optional[float]:
            return a / b if b != 0 else None

        def sqrt(a: float) -> Optional[float]:
            return a**0.5 if a >= 0 else None

        base_functions = {
            "add": add,
            "subtract": subtract,
            "multiply": multiply,
            "divide": divide,
            "sqrt": sqrt,
            "print_answer": self._create_print_answer(),
        }

        for name, func in base_functions.items():
            func.__name__ = name
            func.__doc__ = f"Execute {name} operation: {func.__name__}({inspect.signature(func)})"

        logger.info("Initialized default math functions with type annotations")
        return base_functions

    def _create_print_answer(self) -> Callable:
        """Create standard print_answer function with metadata."""

        def print_answer(answer: Union[str, float, int]) -> str:
            """Format final answer for user presentation."""
            return str(answer)

        print_answer.__name__ = "print_answer"
        return print_answer

    def _generate_function_schema(self) -> List[Dict[str, Any]]:
        """Generate enhanced OpenAI-compatible function schemas."""
        schemas = []
        for func_name, func in self.function_map.items():
            try:
                signature = inspect.signature(func)
            except ValueError:
                logger.warning(f"Could not inspect signature for {func_name}, using default schema")
                signature = inspect.Signature()

            properties = {}
            required = []

            for param_name, param in signature.parameters.items():
                param_type = self._map_param_type(param.annotation)
                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name} for {func_name} operation",
                }
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            schemas.append(
                {
                    "name": func_name,
                    "description": func.__doc__ or f"Execute {func_name} operation",
                    "parameters": {"type": "object", "properties": properties, "required": required},
                }
            )
        return schemas

    def _map_param_type(self, annotation: Any) -> str:
        """Map Python types to JSON schema types."""
        type_map = {int: "number", float: "number", str: "string", bool: "boolean"}
        return type_map.get(annotation, "string")

    def _generate_system_prompt(self) -> str:
        """Generate comprehensive system prompt with enhanced guidelines."""
        function_list = "\n".join(f"- {name}: {func.__doc__}" for name, func in self.function_map.items())

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
   - When streaming:
     * Emit FULL tool parameters in FIRST chunk
     * Maintain valid JSON between updates
     * Never mix text content with tool calls

3. OBSERVATION:
   - Analyze function results
   - Track intermediate steps
   - Update your understanding

4. REFLECTION:
   - Verify if the solution is complete
   - Consider if additional steps are needed
   - Use print_answer only for final results

Available Functions:
{function_list}

Remember: ALWAYS use print_answer as the final step to display results.
"""

    async def process_step(
        self, messages: List[Dict[str, str]], prev_observation: Optional[AgentObservation] = None
    ) -> Union[str, AgentAction]:
        """Process a single step in the reasoning chain with enhanced error handling."""
        logger.info(f"Processing step with model: {self.model_name}")
        logger.debug(f"Messages: {messages}")

        try:
            if self.stream_handlers:
                return await self._process_streaming_step(messages)
            return await self._process_non_streaming_step(messages)

        except Exception as e:
            logger.exception(f"Error in process_step: {str(e)}")
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

    async def _process_streaming_step(self, messages: List[Dict[str, str]]) -> Union[str, AgentAction]:
        """Handle streaming response with token callbacks."""
        logger.debug("Processing streaming response")

        # Block Ollama models from streaming function calls
        if "ollama" in self.model_name.lower():
            logger.error("Ollama models don't support function calling in stream mode")
            raise RuntimeError("Streaming function calls not supported with Ollama models")

        stream = await acompletion(
            model=self.model_name,
            messages=messages,
            tools=[{"type": "function", "function": func} for func in self.functions_schema],
            temperature=self.temperature,
            stream=True,
            extra_headers={"HTTP-Referer": os.getenv("OR_SITE_URL", ""), "X-Title": os.getenv("OR_APP_NAME", "")},
        )

        content = []
        tool_calls = []
        async for chunk in stream:
            delta = chunk.choices[0].delta

            # Handle content streaming
            if delta.content:
                token = delta.content
                content.append(token)
                for handler in self.stream_handlers:
                    handler("token_stream", token)

            # Handle tool call streaming
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    index = tool_call.index
                    if index >= len(tool_calls):
                        tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}, "type": "function"})
                    current_call = tool_calls[index]

                    # Process tool call components
                    if tool_call.id:
                        current_call["id"] += tool_call.id
                        for handler in self.stream_handlers:
                            handler("tool_id_stream", tool_call.id)
                    if tool_call.function.name:
                        current_call["function"]["name"] += tool_call.function.name
                        for handler in self.stream_handlers:
                            handler("tool_name_stream", tool_call.function.name)
                    if tool_call.function.arguments:
                        # Validate incremental JSON to maintain parser state
                        try:
                            current_args = current_call["function"]["arguments"]
                            test_args = current_args + tool_call.function.arguments
                            json.loads(test_args)  # Validate JSON integrity
                            current_call["function"]["arguments"] = test_args
                        except json.JSONDecodeError:
                            # If invalid, append raw data but warn
                            current_call["function"]["arguments"] += tool_call.function.arguments
                            logger.warning("Partial JSON arguments failed validation")

                        for handler in self.stream_handlers:
                            handler("tool_args_stream", tool_call.function.arguments)

        # Construct final message
        assistant_message = type(
            "obj",
            (),
            {
                "content": "".join(content),
                "tool_calls": [
                    type(
                        "obj",
                        (),
                        {
                            "id": tc["id"],
                            "function": type(
                                "obj", (), {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                            ),
                            "type": "function",
                        },
                    )
                    for tc in tool_calls
                ]
                if tool_calls
                else None,
            },
        )

        return self._parse_assistant_message(assistant_message)

    async def _process_non_streaming_step(self, messages: List[Dict[str, str]]) -> Union[str, AgentAction]:
        """Handle standard non-streaming response."""
        logger.debug("Processing non-streaming response")
        response = await acompletion(
            model=self.model_name,
            messages=messages,
            tools=[{"type": "function", "function": func} for func in self.functions_schema],
            temperature=self.temperature,
            extra_headers={"HTTP-Referer": os.getenv("OR_SITE_URL", ""), "X-Title": os.getenv("OR_APP_NAME", "")},
        )
        return self._parse_assistant_message(response.choices[0].message)

    def _parse_assistant_message(self, message: Any) -> Union[str, AgentAction]:
        """Parse assistant message structure."""
        logger.debug(f"Assistant message content: {getattr(message, 'content', '')}")
        logger.debug(f"Tool calls present: {bool(getattr(message, 'tool_calls', None))}")

        if getattr(message, "tool_calls", None):
            tool_call = message.tool_calls[0]
            logger.info("Function call detected")
            logger.debug(f"Function name: {tool_call.function.name}")
            logger.debug(f"Function arguments: {tool_call.function.arguments}")

            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse function arguments: {e}")
                arguments = {"error": "Invalid JSON parameters"}

            return AgentAction(thought=message.content or "", action=tool_call.function.name, action_input=arguments)

        logger.info("Returning text response")
        return message.content or ""

    async def run(self, query: str) -> str:
        """Execute the ReAct agent's reasoning chain."""
        logger.info(f"Starting agent run with query: {query}")
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": query}]

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
                    messages.append(
                        {
                            "role": "assistant",
                            "content": result.thought,
                            "tool_calls": [
                                {
                                    "id": f"call_{steps_taken}",
                                    "function": {"name": result.action, "arguments": json.dumps(result.action_input)},
                                    "type": "function",
                                }
                            ],
                        }
                    )

                    observation = self._execute_action(result)
                    last_observation = observation
                    self.conversation_history.append(observation)

                    messages.append(
                        {"role": "tool", "content": observation.content, "tool_call_id": f"call_{steps_taken}"}
                    )

                    logger.debug(f"Action executed: {result.action}")
                    logger.debug(f"Observation: {observation.content}")

                    if result.action == "print_answer":
                        return observation.content.split(":")[-1].strip()

                    if result.action == "add" and "result" in observation.content.lower():
                        answer = observation.content.split(":")[-1].strip()
                        return await self._trigger_final_answer(answer, messages)

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
                content=f"Action '{action.action}' completed with result: {result}",
            )

        except Exception as e:
            logger.exception(f"Action execution failed: {action.action}")
            return AgentObservation(
                thought_type=ThoughtProcess.REFLECTION, content=f"Error executing {action.action}: {str(e)}"
            )

    async def _trigger_final_answer(self, answer: str, messages: list) -> str:
        """Force final answer formatting when numerical result is detected."""
        try:
            messages.append({"role": "user", "content": "Please format this final answer using print_answer"})

            result = await self.process_step(messages)
            if isinstance(result, AgentAction) and result.action == "print_answer":
                return result.action_input.get("answer", answer)
            return answer
        except Exception as e:
            logger.error(f"Final answer formatting failed: {str(e)}")
            return answer


def evaluate_expression(expression: str) -> float:
    """Evaluate mathematical expressions safely.
    Supports basic arithmetic operations (+-*/) and parentheses.
    Example: evaluate_expression('(3+5)*2') -> 16.0
    """
    try:
        return float(eval(expression))
    except:
        return "Error: Invalid expression"


def think(
    step_progression: str, envisioned_plan: str, problem_to_solve: str, constraints: str, expected_results: str
) -> str:
    """
    Generates a detailed XML representation of the agent's thought process.
    """
    # Escape special XML characters
    step_progression = sax.escape(step_progression)
    envisioned_plan = sax.escape(envisioned_plan)
    problem_to_solve = sax.escape(problem_to_solve)
    constraints = sax.escape(constraints)
    expected_results = sax.escape(expected_results)

    return f"""
    <thought_process>
        <problem_to_solve>{problem_to_solve}</problem_to_solve>
        <constraints>{constraints}</constraints>
        <envisioned_plan>{envisioned_plan}</envisioned_plan>
        <expected_results>{expected_results}</expected_results>
        <step_progression>
            {step_progression}
        </step_progression>
        <detailed_reasoning>
            <step_breakdown>
                <reasoning_step>
                    <description>Initial Problem Analysis</description>
                    <details>Analyzed the problem statement to understand requirements</details>
                </reasoning_step>
                <reasoning_step>
                    <description>Plan Development</description>
                    <details>Developed a step-by-step approach to solve the problem</details>
                </reasoning_step>
                <reasoning_step>
                    <description>Constraints Consideration</description>
                    <details>Reviewed constraints to ensure compliance</details>
                </reasoning_step>
            </step_breakdown>
            <action_plan>
                <planned_actions>
                    <action>Execute Step 1</action>
                    <action>Execute Step 2</action>
                    <action>Execute Step 3</action>
                </planned_actions>
            </action_plan>
            <risk_assessment>
                <potential_risks>Identified potential risks and developed mitigation strategies</potential_risks>
            </risk_assessment>
        </detailed_reasoning>
        <observations>
            <observation>Observed that the initial approach is feasible</observation>
            <observation>Noted potential areas for optimization</observation>
        </observations>
        <reflection>
            <reflection_step>
                <description>Self-Assessment</description>
                <details>Assessed the effectiveness of the current approach</details>
            </reflection_step>
            <reflection_step>
                <description>Result Evaluation</description>
                <details>Evaluated the results against expected outcomes</details>
            </reflection_step>
        </reflection>
        <final_assessment>
            <conclusion>The proposed plan is viable and aligns with expected results</conclusion>
            <recommendations>
                <recommendation>Proceed with the planned steps</recommendation>
                <recommendation>Monitor for potential risks</recommendation>
            </recommendations>
        </final_assessment>
    </thought_process>
    """


async def main():
    try:
        validate_openrouter_config()
    except ValueError as e:
        logger.error(str(e))
        return

    # Enhanced stream handler with type annotations
    def console_stream_handler(event: str, token: str) -> None:
        """Basic console output for streaming events with type hints"""
        if event == "token_stream":
            print(token, end="", flush=True)
        elif event.startswith("tool_"):
            logger.debug(f"Tool call chunk: {event} - {repr(token)}")

    agent = ReActAgent(
        functions=[think, evaluate_expression],
        stream_handlers=[console_stream_handler],  # Enable streaming
    )

    logger.info("ReAct Agent initialized")

    while True:
        try:
            query = input("\nEnter your query (or 'exit' to quit): ").strip()

            if query.lower() == "exit":
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
