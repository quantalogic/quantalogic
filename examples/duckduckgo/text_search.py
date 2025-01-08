from duckduckgo_search import DDGS
import json

def search_text(query: str, max_results: int = 5):
    """Search DuckDuckGo for text results and return as JSON"""
    results = DDGS().text(query, max_results=max_results)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    search_text("python programming")
