#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "litellm>=1.59.8",
#     "loguru"
# ]
# ///

import inspect
import json
from typing import Any, Dict, List

from litellm import completion
from loguru import logger

# Configure logging
logger.add("function_calling.log", rotation="10 MB")

MODEL_NAME = "ollama/llama3.1:latest"

def add(a: float, b: float) -> float:
    """Add two numbers."""
    return float(a + b)

def subtract(a: float, b: float) -> float:
    """Subtract two numbers."""
    return float(a - b)

def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return float(a * b)

def divide(a: float, b: float) -> float:
    """Divide two numbers."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return float(a / b)

def sqrt(a: float) -> float:
    """Calculate the square root of a number."""
    if a < 0:
        raise ValueError("Cannot calculate square root of negative number")
    return float(a ** 0.5)

def print_answer(answer: str) -> str:
    """Format and return the final answer."""
    return answer

# Function map
function_map = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
    "sqrt": sqrt,
    "print_answer": print_answer
}

def generate_function_schema() -> list:
    """Generate OpenAI-compatible function schemas."""
    functions = []
    for func_name, func in function_map.items():
        params = {}
        signature = inspect.signature(func)
        for param_name, param in signature.parameters.items():
            params[param_name] = {
                "type": "number" if param_name != "answer" else "string",
                "description": f"Parameter {param_name}"
            }
        
        functions.append({
            "name": func_name,
            "description": func.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": params,
                "required": list(params.keys())
            }
        })
    return functions

def generate_system_prompt(functions: list) -> str:
    """Generate the system prompt with function descriptions."""
    prompt = [
        "You are a ReAct agent designed to solve problems through multi-step reasoning and actions.\n",
        "Available functions:\n"
    ]
    
    for func in functions:
        name = func['name']
        params = ', '.join(func['parameters']['properties'].keys())
        desc = func['description']
        prompt.append(f"{name}({params}): {desc}\n")
        prompt.append("   Parameters:\n")
        for param_name, param_info in func['parameters']['properties'].items():
            prompt.append(f"   - {param_name} ({param_info['type']}): {param_info['description']}\n")
        prompt.append("\n")

    prompt.append("""
Guidelines:
1. For calculations, ALWAYS follow these two steps:
   a. First, perform the calculation using the appropriate function
   b. Then, use print_answer to display the result
2. Never skip the print_answer step - it's required to show results
3. Format calculation results clearly, e.g. "The result is 42"

""")
    return ''.join(prompt)

def parse_arguments(arguments: str) -> Dict[str, Any]:
    """Parse and validate function arguments."""
    try:
        args = json.loads(arguments)
        return {k: float(v) if isinstance(v, (int, float)) and k != "answer" else v 
                for k, v in args.items()}
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in function arguments")
    except ValueError as e:
        raise ValueError(f"Error converting arguments: {str(e)}")

def handle_function_call(tool_call: Dict, messages: List) -> tuple[Any, bool]:
    """Execute function call and return result and completion status."""
    function_info = tool_call['function']
    operation = function_info['name']
    arguments = parse_arguments(function_info['arguments'])
    
    result = function_map[operation](**arguments)
    
    if operation == 'print_answer':
        print(f"\nResult: {result}")
        return result, True
    else:
        observation = f"The result of the {operation} operation is: {result}"
        print(f"Observation: {observation}")
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call['id'],
            "content": str(result)
        })
        return result, False

def main():
    functions = generate_function_schema()
    system_prompt = generate_system_prompt(functions)
    messages = [{"role": "system", "content": system_prompt}]
    
    logger.info("Starting ReAct Agent")
    print("Welcome to the ReAct Agent! Type 'exit' to quit.")
    print("\nSystem Prompt:")
    print(system_prompt)

    while True:
        try:
            user_input = input("\nAsk a question or give a task: ").strip()
            
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
            
            messages.append({"role": "user", "content": user_input})
            last_calculation = None
            
            while True:
                try:
                    response = completion(
                        model=MODEL_NAME,
                        messages=messages,
                        tools=[{"type": "function", "function": func} for func in functions]
                    )
                    
                    assistant_message = response['choices'][0]['message']
                    logger.info(f"Assistant Response: {assistant_message}")
                    
                    if not assistant_message.get('tool_calls'):
                        if content := assistant_message.get('content'):
                            print(f"\nAssistant: {content}")
                        break
                    
                    messages.append({
                        "role": "assistant",
                        "tool_calls": assistant_message['tool_calls'],
                        "content": assistant_message.get('content')
                    })
                    
                    result, is_complete = handle_function_call(
                        assistant_message['tool_calls'][0], 
                        messages
                    )
                    
                    if is_complete:
                        messages = [{"role": "system", "content": system_prompt}]
                        break
                    else:
                        last_calculation = result
                        continue
                        
                except Exception as e:
                    logger.error(f"Error in processing: {str(e)}")
                    print(f"Error: {str(e)}")
                    break
                    
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            break
        except Exception as e:
            logger.exception("Unexpected error")
            print(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()