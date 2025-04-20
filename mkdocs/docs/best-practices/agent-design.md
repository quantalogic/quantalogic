# Agent Design Best Practices

Learn how to design effective and efficient agents in QuantaLogic. This guide summarizes key principles, patterns, anti-patterns, and practical examples.

---

## Principles
- **Clarity First:** Write simple, readable code. Prefer clear logic over clever tricks.
- **Single Responsibility:** Each agent or tool should do one thing well (≤20 lines per function, ≤3 parameters).
- **Explicit Error Handling:** Always handle errors and edge cases. Use try/except and provide helpful messages.
- **Logging:** Use `loguru` for structured, actionable logs. Log important events, errors, and decisions.
- **Security:** Sandbox code execution. Never trust user input blindly.
- **Environment Awareness:** Check for required API keys and dependencies before running tasks.
- **Documentation:** Document WHY decisions are made, not just WHAT the code does.

---

## Patterns
- **Reason-Act Loop:** Alternate between reasoning and action until the task is complete.
- **Tool Modularity:** Build reusable, composable tools. Keep tool logic isolated from agent logic.
- **Fail Fast:** Validate input and environment early. Exit gracefully on missing prerequisites.
- **Context Propagation:** Pass relevant context (memory, logs, results) through the agent and tools.
- **Consistent Interfaces:** Use clear, typed function signatures and class interfaces.

---

## Anti-patterns
- **God Objects:** Avoid agents or tools that try to do too much.
- **Silent Failures:** Never swallow exceptions without logging.
- **Hardcoded Secrets:** Never hardcode API keys or credentials. Use environment variables or `.env` files.
- **Duplicate Logic:** Refactor repeated code into shared utilities or tools.
- **Unbounded Loops:** Always set sensible defaults for iterations and resource limits.

---

## Examples

### Minimal Agent with Error Handling
```python
from quantalogic import Agent
from loguru import logger
import os

if not os.environ.get("DEEPSEEK_API_KEY"):
    logger.error("DEEPSEEK_API_KEY is missing. Set it as an environment variable.")
    raise SystemExit(1)

agent = Agent(model_name="deepseek/deepseek-chat")
try:
    result = agent.solve_task("Write a function to check palindromes")
    print(result)
except Exception as e:
    logger.exception("Agent failed to solve task: {}", e)
```

### Good Tool Design
```python
from quantalogic.tools import Tool

class CountWordsTool(Tool):
    name = "count_words"
    description = "Counts words in a string."

    def run(self, input: str) -> int:
        return len(input.split())
```

---

## See Also
- [Core Concepts](../core-concepts.md)
- [Tool Development Guide](tool-development.md)
- [Quick Start](../quickstart.md)
