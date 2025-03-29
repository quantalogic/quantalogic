#!/usr/bin/env python

import typer
from litellm import completion
import json
import os
import requests

app = typer.Typer()

# Weather tool definition
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

def get_weather(city):
    if isinstance(city, dict):
        city = city.get('city', 'Oxford')
    
    api_key = os.environ.get('OPENWEATHER_API_KEY')
    if not api_key:
        return 'Error: OPENWEATHER_API_KEY environment variable not set.'
    
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        description = data['weather'][0]['description']
        temp = data['main']['temp']
        return f'The weather in {city} is {description} with a temperature of {temp}°C.'
    except requests.RequestException as e:
        return f'Error fetching weather data for {city}: {str(e)}'

@app.command()
def ask(
    question: str = typer.Option("What is the weather at Oxford?", "--question", "-q", help="The question to ask"),
    model: str = typer.Option("openrouter/openai/gpt-4o-mini", "--model", "-m", help="The AI model to use")
):
    """Ask a question to the AI model with weather tool capability."""
    
    messages = [{"role": "user", "content": question}]
    
    try:
        # First completion call with tools
        response = completion(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        typer.echo("Initial response:")
        typer.echo(str(message))
        
        # Handle tool calls if present
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.function.name == "get_weather":
                    arguments = json.loads(tool_call.function.arguments)
                    weather_result = get_weather(arguments["city"])
                    messages.append(message)
                    messages.append({
                        "role": "tool",
                        "content": weather_result,
                        "tool_call_id": tool_call.id
                    })
                    
                    # Second completion call with tool results
                    final_response = completion(
                        model=model,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto"
                    )
                    typer.echo("\nFinal response:")
                    typer.echo(final_response.choices[0].message.content)
        else:
            typer.echo("\nDirect response:")
            typer.echo(message.content)
            
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)

if __name__ == "__main__":
    app()