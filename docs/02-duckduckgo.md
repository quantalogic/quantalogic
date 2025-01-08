# DuckDuckGo Search API Documentation

## Introduction
The `duckduckgo-search` library provides a Python interface to the DuckDuckGo search engine. It supports text search, image search, video search, news search, and AI chat capabilities.

**Disclaimer**: This library is not affiliated with DuckDuckGo and is for educational purposes only.

## Installation
```bash
pip install -U duckduckgo-search
```

## Basic Usage

### Text Search
```python
from duckduckgo_search import DDGS

results = DDGS().text("python programming", max_results=5)
print(results)
```

### Image Search
```python
results = DDGS().images("butterfly", max_results=3)
print(results)
```

### Video Search
```python
results = DDGS().videos("cars", max_results=3)
print(results)
```

### News Search
```python
results = DDGS().news("sun", max_results=3)
print(results)
```

### AI Chat
```python
results = DDGS().chat("summarize Daniel Defoe's The Consolation of Philosophy")
print(results)
```

## Advanced Usage

### Search Operators
```python
results = DDGS().text("cats filetype:pdf", region="wt-wt")
results = DDGS().text("dogs site:example.com", region="wt-wt")
results = DDGS().text("intitle:dogs", region="wt-wt")
```

### Regions
Supported regions: `wt-wt`, `us-en`, `uk-en`, `ru-ru`
```python
results = DDGS().text("python programming", region="us-en")
```

### Proxy Support
```python
ddgs = DDGS(proxy="tb", timeout=20)  # Using Tor Browser as a proxy
results = ddgs.text("something you need", max_results=50)
```

### Exceptions
```python
try:
    results = DDGS().text("python programming", max_results=5)
except DuckDuckGoSearchException as e:
    print(f"An error occurred: {e}")
```

## Examples

### Search for PDFs
```python
results = DDGS().text("economics filetype:pdf", region="wt-wt")
```

### Image Search with Filters
```python
results = DDGS().images(
    keywords="butterfly",
    region="wt-wt",
    safesearch="off",
    size="Large",
    color="Monochrome"
)
```

### News Search with Filters
```python
results = DDGS().news(keywords="sun", region="wt-wt", safesearch="moderate")
```

### Video Search with Filters
```python
results = DDGS().videos(
    keywords="cars",
    region="wt-wt",
    safesearch="off",
    timelimit="w",
    resolution="high",
    duration="medium"
)
```

### AI Chat with Custom Model
```python
results = DDGS().chat("summarize Daniel Defoe's The Consolation of Philosophy", model="gpt-4o-mini")
```

## CLI Usage

### Basic CLI Commands
```bash
ddgs text -k "Assyrian siege of Jerusalem"
```

### Advanced CLI Commands
```bash
ddgs text -k "Economics in one lesson filetype:pdf" -r wt-wt
ddgs images -k "beware of false prophets" -r wt-wt -type photo
ddgs news -k "sanctions" -m 100 -t d -o json
```

## API Reference

### DDGS Class
```python
from duckduckgo_search import DDGS

ddgs = DDGS(proxy="http://user:pass@example.com:3128", timeout=10)
results = ddgs.text("python programming", max_results=5)
```

### Methods
```python
results = DDGS().text(
    keywords="live free or die",
    region="wt-wt",
    safesearch="moderate",
    timelimit="d",
    max_results=10
)
```

## Disclaimer
This library is not affiliated with DuckDuckGo and is for educational purposes only. It is not intended for commercial use or any purpose that violates DuckDuckGo's Terms of Service.

## Additional Resources
- [PyPI page](https://pypi.org/project/duckduckgo-search/)
- [DuckDuckGo official website](https://duckduckgo.com)
