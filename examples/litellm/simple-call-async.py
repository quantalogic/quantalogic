import asyncio
import os
import time

import litellm
from litellm import acompletion
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

litellm.set_verbose = False
console = Console()

async def main():
    console.print("[bold green]Starting request...[/bold green]")
    start_time = time.time()
    
    response = await acompletion(
        model="deepseek/deepseek-chat",
        messages=[{"role": "user", "content": "hello from litellm"}],
        stream=True
    )
    
    console.print("\n[bold yellow]Response tokens:[/bold yellow]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Streaming response...", total=None)
        accumulated_content = ""
        
        async for chunk in response:
            content = chunk['choices'][0]['delta'].get('content', '')
            if content:
                accumulated_content += content
                #console.print(content, end="")
                progress.update(task, description=f"[cyan]Received {len(accumulated_content)} chars")
    
    elapsed_time = time.time() - start_time
    console.print(f"\n\n[bold blue]Request completed in {elapsed_time:.2f} seconds[/bold blue]")
    console.print(f"[bold]Total content received:[/bold] {len(accumulated_content)} characters")

if __name__ == "__main__":
    asyncio.run(main())
