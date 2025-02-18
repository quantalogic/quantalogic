#!/usr/bin/env -S uv run

# /// script
# # requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "markitdown",
#     "litellm",
# ]
# ///

import asyncio

from qflow import AsyncFlow, AsyncNode


class AgentNode(AsyncNode):
    async def prep_async(self, _):
        message_queue = self.params["messages"]
        message = await message_queue.get()
        print(f"Agent received: {message}")
        return message

# Create node and flow
agent = AgentNode()
agent >> agent  # connect to self
flow = AsyncFlow(start=agent)

# Create heartbeat sender
async def send_system_messages(message_queue):
    counter = 0
    messages = [
        "System status: all systems operational",
        "Memory usage: normal",
        "Network connectivity: stable",
        "Processing load: optimal"
    ]
    
    while True:
        message = f"{messages[counter % len(messages)]} | timestamp_{counter}"
        await message_queue.put(message)
        counter += 1
        await asyncio.sleep(1)

async def main():
    message_queue = asyncio.Queue()
    shared = {}
    flow.set_params({"messages": message_queue})
    
    # Run both coroutines
    await asyncio.gather(
        flow.run_async(shared),
        send_system_messages(message_queue)
    )
    
asyncio.run(main())
