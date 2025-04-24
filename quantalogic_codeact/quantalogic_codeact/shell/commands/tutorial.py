from typing import List


async def tutorial_command(shell, args: List[str]) -> str:
    """Show tutorial: /tutorial"""
    tutorial_text = (
        f"Tutorial for Quantalogic Shell in {shell.agent_config.mode} mode:\n"
        f"1. Use /chat or plain messages (in chat mode) to interact with the agent.\n"
        f"2. Use /solve or plain messages (in codeact mode) to solve tasks.\n"
        f"3. Type /help for a list of commands."
    )
    return tutorial_text