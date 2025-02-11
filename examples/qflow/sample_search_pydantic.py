#!/usr/bin/env -S uv run

# /// script
# # requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "pydantic",
#     "litellm",
#     "google-search-results"  # SerpApi package
# ]
# ///

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict

from loguru import logger

# Import pydantic base node and flow components from qflow_pydantic
from qflow_pydantic import BaseNode, Flow, SharedContext, call_llm
from serpapi import GoogleSearch
from pydantic import BaseModel, Field
from qflow_pydantic import BaseNode, NodeParams, SharedContext

# Parameter models
class SearchParams(NodeParams):
    query: str = ""
    max_results: int = Field(default=10, gt=0)

class DecideParams(NodeParams):
    threshold: float = Field(default=0.5, ge=0, le=1.0)

# --- Utility Function ---
def search_web(search_term: str) -> Dict[str, Any]:
    try:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise ValueError("SERPAPI_API_KEY environment variable not set")
        search = GoogleSearch({
            "q": search_term,
            "api_key": api_key,
            "num": 3
        })
        results = search.get_dict()
        organic = results.get("organic_results", [])
        return {"results": [
            {"title": r.get("title"), "snippet": r.get("snippet"), "link": r.get("link")}
            for r in organic[:3]
        ]}
    except Exception as e:
        logger.error(f"Web search failed: {str(e)}")
        return {"error": str(e)}

# --- Node Implementations ---
class DecideActionPydantic(BaseNode[DecideParams, SharedContext]):
    _params_model = DecideParams  # Specify the params model

    def prep(self, context: SharedContext) -> Any:
        query = context.data.get("query")
        prev_context = context.data.get("context", "No previous search")
        logger.info(f"Deciding action for query: {query}")
        return (query, prev_context)

    def exec(self, prep_result: Any) -> Any:
        query, prev_context = prep_result
        prompt = f"""Given input: {query}
Previous search results: {prev_context}

Respond with XML in the following format:
```xml
<decision>
    <action>search</action>
    <reason>Explanation</reason>
    <search_term>Term if needed</search_term>
</decision>
```"""
        # For simplicity, using empty dict as parameters
        response = call_llm(prompt, {})
        match = re.search(r"```xml\s*(<decision>.*?</decision>)\s*```", response, re.DOTALL)
        if not match:
            match = re.search(r"(<decision>.*?</decision>)", response, re.DOTALL)
            if not match:
                return {"action": "answer", "reason": "Failed to parse decision"}
        xml_content = match.group(1).strip()
        try:
            root = ET.fromstring(xml_content)
            result = {child.tag: (child.text or "").strip() for child in root}
            if "action" not in result or "reason" not in result:
                return {"action": "answer", "reason": "Missing fields in decision"}
            return result
        except Exception as e:
            return {"action": "answer", "reason": f"XML parsing error: {str(e)}"}

    def post(self, context: SharedContext, exec_result: Any) -> Any:
        if exec_result.get("action") == "search":
            context.data["search_term"] = exec_result.get("search_term")
        return exec_result.get("action")

class SearchWebPydantic(BaseNode[SearchParams, SharedContext]):
    _params_model = SearchParams  # Specify the params model

    def prep(self, context: SharedContext) -> Any:
        term = context.data.get("search_term")
        logger.info(f"Preparing web search for term: {term}")
        return term

    def exec(self, prep_result: Any) -> Any:
        return search_web(prep_result)

    def post(self, context: SharedContext, exec_result: Any) -> Any:
        prev = context.data.get("context", [])
        context.data["context"] = prev + [{"term": context.data.get("search_term"), "result": exec_result}]
        return "decide"

class DirectAnswerPydantic(BaseNode):
    def prep(self, context: SharedContext) -> Any:
        query = context.data.get("query")
        prev_context = context.data.get("context", "")
        logger.info("Generating direct answer")
        return (query, prev_context)

    def exec(self, prep_result: Any) -> Any:
        query, ctx = prep_result
        prompt = f"Context: {ctx}\nAnswer: {query}"
        return call_llm(prompt, {})

    def post(self, context: SharedContext, exec_result: Any) -> Any:
        answer = exec_result.strip()
        logger.info(f"Answer generated: {answer[:100]}...")
        print(answer)
        context.data["answer"] = answer
        return None

# --- Node Chaining ---
decide = DecideActionPydantic({"threshold": 0.7})
search = SearchWebPydantic({"query": "python examples", "max_results": 5})
answer = DirectAnswerPydantic({})

decide.add_successor(search, "search")
decide.add_successor(answer, "answer")
search.add_successor(decide, "decide")

# --- Flow Execution ---
if __name__ == "__main__":
    # Initialize shared context with initial data
    initial_data = {"query": "Who won the Nobel Prize in Physics 2024?", "context": []}
    context = SharedContext(data=initial_data)
    flow = Flow(start_node=decide)
    # Flow.exec expects a dict; it wraps it into its own SharedContext
    flow.exec(context.data)
