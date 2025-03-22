from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent / "prompts"
LOG_FILE = "react_agent.log"
DEFAULT_MODEL = "gemini/gemini-2.0-flash"
MAX_TOKENS = 4000