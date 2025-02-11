#!/usr/bin/env -S uv run

# /// script
# # requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "pydantic",
#     "litellm",
#     "PyYAML",
#     "google-search-results",
# ]
# ///

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict

from loguru import logger
from qflow_pydantic import BaseNode, Flow, LLMParams, NodeParams, call_llm
from serpapi import GoogleSearch


# Reuse search_web logic
def search_web(search_term: str) -> Dict[str, Any]:
    logger.info(f"Searching web for: {search_term}")
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
        logger.debug(f"Results: {len(results.get('organic_results', []))} items")
        if "organic_results" in results:
            return {
                "results": [
                    {
                        "title": r.get("title"),
                        "snippet": r.get("snippet"),
                        "link": r.get("link")
                    } for r in results["organic_results"][:3]
                ]
            }
        return {"results": "No results found"}
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return {"error": f"Search failed: {str(e)}"}

# DecideAction node using BaseNode
class DecideAction(BaseNode[LLMParams]):
    def prep(self, shared: Dict[str, Any]) -> Any:
        logger.info(f"Deciding next action for query: {shared['query']}")
        return (shared["query"], shared.get("context", "No previous search"))
    
    def exec(self, inputs: Any) -> Any:
        query, context = inputs
        prompt = f"""
Given input: {query}
Previous search results: {context}

Respond with a decision in XML format between ```xml markers.
Required fields:
- action: exactly "search" or "answer"
- reason: brief explanation
- search_term: only for search action

Your response MUST start with ```xml and end with ```. Example:
```xml
<decision>
    <action>search</action>
    <reason>Need current details</reason>
    <search_term>Nobel Prize Physics 2023</search_term>
</decision>
```

Generate your response in the same format:
```xml"""
        # Call LLM using default LLMParams
        response = call_llm(prompt, self.params)
        content = response if isinstance(response, str) else str(response)
        logger.debug(f"LLM raw response:\n{content}")
        try:
            match = re.search(r"```xml\s*(<decision>.*?</decision>)\s*```", content, re.DOTALL)
            if not match:
                match = re.search(r"(<decision>.*?</decision>)", content, re.DOTALL)
                if not match:
                    raise ValueError("No valid XML section found")
            xml_content = match.group(1) if match.lastindex else match.group(0)
            xml_content = re.sub(r'>\s+<', '><', xml_content.strip())
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError:
                xml_content = f"<decision>{xml_content}</decision>" if not xml_content.startswith('<decision>') else xml_content
                root = ET.fromstring(xml_content)
            result = { child.tag: (child.text or "").strip() for child in root }
            if "action" not in result or "reason" not in result:
                raise ValueError("Missing required fields")
            if result["action"] not in ["search", "answer"]:
                raise ValueError("Invalid action type")
            if result["action"] == "search" and "search_term" not in result:
                raise ValueError("Missing search_term for search")
            logger.info(f"Decision: {result['action']} - {result['reason']}")
            return result
        except Exception as e:
            logger.error(f"Decision parsing failed: {str(e)}")
            return {"action": "answer", "reason": f"Failed to parse: {str(e)}"}
    
    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        if exec_res.get("action") == "search":
            shared["search_term"] = exec_res["search_term"]
        return exec_res["action"]

# SearchWeb node using BaseNode
class SearchWeb(BaseNode[NodeParams]):
    def prep(self, shared: Dict[str, Any]) -> Any:
        logger.info(f"Preparing web search for: {shared['search_term']}")
        return shared["search_term"]
    
    def exec(self, search_term: Any) -> Any:
        return search_web(search_term)
    
    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        prev = shared.get("context", [])
        shared["context"] = prev + [{"term": shared["search_term"], "result": exec_res}]
        return "decide"

# DirectAnswer node using LLMNode behavior by extending call_llm logic
class DirectAnswer(BaseNode[LLMParams]):
    def prep(self, shared: Dict[str, Any]) -> Any:
        logger.info("Generating direct answer")
        return f"Context: {shared.get('context', '')}\nAnswer: {shared['query']}"
    
    def exec(self, prompt: Any) -> Any:
        return call_llm(prompt, self.params)  # self.params holds LLMParams
    
    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        answer = exec_res.strip()
        logger.info(f"Answer generated: {answer}")
        print(answer)
        shared["answer"] = answer
        return "end"

# Connect nodes

llm_params = LLMParams(model_name="gemini/gemini-2.0-flash")

decide = DecideAction(llm_params)
search = SearchWeb(NodeParams())
# Use default LLMParams for DirectAnswer
direct = DirectAnswer(llm_params)

decide - "search" >> search
decide - "answer" >> direct
search - "decide" >> decide  # Loop back

logger.add("workflow.log", rotation="500 MB", level="INFO")
flow = Flow(start_node=decide)
logger.info("Starting pydantic workflow execution")
flow.exec({"query": "Who won the Nobel Prize in Physics 2024?"})
logger.info("Pydantic workflow completed")
