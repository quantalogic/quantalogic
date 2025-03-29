#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "litellm>=1.59.8",
#     "requests>=2.31.0",
# ]
# ///

import json
import os

import litellm
import requests
from litellm import completion

# Enable verbose output to debug API interactions and track the flow of requests and responses
litellm.set_verbose = True

# Define the weather tool to demonstrate how to integrate external APIs with LLM function calling
# This enables the LLM to make real-time API calls based on user queries
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The name of the city"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

# Implement the weather API function to show how to handle external API calls
# This includes error handling for missing environment variables and API failures
def get_weather(city):
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        return "Error: OPENWEATHER_API_KEY environment variable not set."
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        description = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        return f"The weather in {city} is {description} with a temperature of {temp}°C."
    except requests.RequestException as e:
        return f"Error fetching weather data for {city}: {str(e)}"

# Initial user message
messages = [{"role": "user", "content": "What's the weather in New York? Describe the weather in detail."}]

# First completion call with tools
response = completion(
    model="openrouter/openai/gpt-4o-mini",
    messages=messages,
    tools=tools,
    tool_choice="auto"  # Let the model decide whether to use the tool
)

# Extract the assistant's message from the response
message = response.choices[0].message
print("Initial response from model:")
print(message)

# Check if the model requested a tool call
if message.tool_calls:
    print("Tool calls detected:")
    for tool_call in message.tool_calls:
        print(tool_call)
        if tool_call.function.name == "get_weather":
            # Parse the arguments provided by the model
            arguments = json.loads(tool_call.function.arguments)
            city = arguments["city"]
            # Execute the tool
            weather_result = get_weather(city)
            print("Tool result:", weather_result)
            # Append the assistant's message (with tool call) and the tool's result
            messages.append(message)
            messages.append({
                "role": "tool",
                "content": weather_result,
                "tool_call_id": tool_call.id
            })
    # Second completion call with updated messages to get the final response
    final_response = completion(
        model="openrouter/openai/gpt-4o-mini",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    print("Final response from model:")
    print(final_response.choices[0].message.content)
else:
    print("Direct response from model:")
    print(message.content)