from duckduckgo_search import DDGS
import json


def search_files(query: str, filetype: str = "pdf", max_results: int = 3):
    """Search DuckDuckGo for specific file types and return as JSON"""
    results = DDGS().text(f"{query} filetype:{filetype}", max_results=max_results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    search_files("economics", filetype="pdf")
