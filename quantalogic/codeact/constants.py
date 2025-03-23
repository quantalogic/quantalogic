from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
TEMPLATE_DIR = BASE_DIR / "prompts"
LOG_FILE = "react_agent.log"
DEFAULT_MODEL = "gemini/gemini-2.0-flash"
MAX_TOKENS = 4000