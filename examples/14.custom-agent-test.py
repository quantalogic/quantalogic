
if __name__ == "__main__":
    # Example usage
    tools_config = [
        {"type": "duck_duck_go_search", "parameters": {}},
        {"type": "write_file_tool", "parameters": {}},
        {"type": "file_tracker_tool", "parameters": {}},
    ]
    
    agent = create_custom_agent(
        model_name="openrouter/openai/gpt-4o-mini",
        specific_expertise="General purpose assistant",
        tools=tools_config
    )
    print(f"Created agent with {len(agent.tools.tool_names())} tools")
    
    # Display all tool names
    print("Agent Tools:")
    for tool_name in agent.tools.tool_names():
        print(f"- {tool_name}")

    # Set up event monitoring to track agent's lifecycle
    # The event system provides:
    # 1. Real-time observability into the agent's operations
    # 2. Debugging and performance monitoring
    # 3. Support for future analytics and optimization efforts
    agent.event_emitter.on(
        event=[
            "task_complete",
            "task_think_start",
            "task_think_end",
            "tool_execution_start",
            "tool_execution_end",
            "error_max_iterations_reached",
            "memory_full",
            "memory_compacted",
            "memory_summary",
        ],
        listener=console_print_events,
    )

    # Enable token streaming for detailed output
    agent.event_emitter.on(event=["stream_chunk"], listener=console_print_token)

    # Solve task with streaming enabled
    result = agent.solve_task("Who is the Prime Minister of France in 2025 ?", max_iterations=10, streaming=True)
    print(result)