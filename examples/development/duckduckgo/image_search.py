from duckduckgo_search import DDGS
import json


def search_images(query: str, max_results: int = 3):
    """Search DuckDuckGo for images and return as JSON"""
    results = DDGS().images(query, max_results=max_results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    search_images("butterfly")
