#!/usr/bin/env python

import json
import os
import time

import requests
import typer
from litellm import completion
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.theme import Theme

custom_theme = Theme({
    'info': 'bold cyan',
    'warning': 'bold yellow',
    'error': 'bold red',
    'success': 'bold green',
    'tool': 'bold magenta'
})

console = Console(theme=custom_theme)

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
    question: str = typer.Option("What is the weather at Oxford?", "--question", "-q", help="The question to ask the AI model. Example: 'What's the weather in Paris?'"),
    model: str = typer.Option("openrouter/openai/gpt-4o-mini", "--model", "-m", help="The AI model to use. Options: 'openrouter/openai/gpt-4o-mini', 'deepseek/deepseek-chat', etc."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output and processing information")
):
    """Interact with an AI model using natural language and tools."""
    messages = [{"role": "user", "content": question}]
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            task = progress.add_task("[cyan]Processing...", total=1)
            
            # First completion call with tools
            response = completion(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            progress.update(task, completed=1)
            
            message = response.choices[0].message
            console.print("\n[info]Initial response:[/info]")
            console.print(str(message))
            
            # Handle tool calls if present
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "get_weather":
                        arguments = json.loads(tool_call.function.arguments)
                        console.print(f"[tool]Executing tool: {tool_call.function.name}[/tool]")
                        weather_result = get_weather(arguments["city"])
                        messages.append(message)
                        messages.append({
                            "role": "tool",
                            "content": weather_result,
                            "tool_call_id": tool_call.id
                        })
                        
                        # Second completion call with tool results
                        with progress:
                            task = progress.add_task("[cyan]Processing tool response...", total=1)
                            final_response = completion(
                                model=model,
                                messages=messages,
                                tools=tools,
                                tool_choice="auto"
                            )
                            progress.update(task, completed=1)
                        
                        console.print("\n[success]Final response:[/success]")
                        console.print(final_response.choices[0].message.content)
            else:
                console.print("\n[success]Direct response:[/success]")
                console.print(message.content)
                
    except Exception as e:
        console.print(f"[error]Error: {str(e)}[/error]", style="error")

if __name__ == "__main__":
    app()