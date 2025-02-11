#!/usr/bin/env -S uv run

# /// script
# # requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "markitdown", 
#     "litellm",
#     "PyYAML",
#     "google-search-results"  # SerpApi package
# ]
# ///

import os
import re  # added import for regex
import xml.etree.ElementTree as ET  # Add this import
from typing import Any, Dict

from loguru import logger
from qflow import Flow, Node, call_llm
from serpapi import GoogleSearch

MODEL_NAME = "gemini/gemini-2.0-flash"

def search_web(search_term: str) -> Dict[str, Any]:
    """
    Search the web using SerpApi.
    
    Args:
        search_term: The search query
        
    Returns:
        Dict containing search results
    """
    logger.info(f"Searching web for: {search_term}")
    try:
        # Get API key from environment
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise ValueError("SERPAPI_API_KEY environment variable not set")
            
        search = GoogleSearch({
            "q": search_term,
            "api_key": api_key,
            "num": 3  # Limit to top 3 results
        })
        
        results = search.get_dict()
        logger.debug(f"Search results received: {len(results.get('organic_results', []))} items")
        
        # Extract organic results
        if "organic_results" in results:
            return {
                "results": [
                    {
                        "title": r.get("title"),
                        "snippet": r.get("snippet"),
                        "link": r.get("link")
                    }
                    for r in results["organic_results"][:3]
                ]
            }
        return {"results": "No results found"}
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return {"error": f"Search failed: {str(e)}"}

class DecideAction(Node):
    def prep(self, shared):
        logger.info(f"Deciding next action for query: {shared['query']}")
        context = shared.get("context", "No previous search")
        query = shared["query"]
        return query, context
        
    def exec(self, inputs):
        query, context = inputs
        logger.debug(f"Generating decision prompt with context length: {len(str(context))}")
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
    <reason>Need to search for current information</reason>
    <search_term>Nobel Prize Physics 2023</search_term>
</decision>
```

Generate your response in the same format:
```xml"""

        resp = call_llm(prompt)
        content = resp.content if hasattr(resp, 'content') else str(resp)
        logger.debug(f"Raw LLM response:\n{content}")
        
        try:
            # Try extraction using a regex with a capturing group
            match = re.search(r"```xml\s*(<decision>.*?</decision>)\s*```", content, re.DOTALL)
            if not match:
                # Fallback: use regex without a capturing group
                match = re.search(r"(<decision>.*?</decision>)", content, re.DOTALL)
                if not match:
                    raise ValueError("No valid XML section found in response")
            
            # Use captured group if available, otherwise the full match
            xml_content = match.group(1) if match.lastindex else match.group(0)
            xml_content = xml_content.strip()
            xml_content = re.sub(r'>\s+<', '><', xml_content)
            xml_content = re.sub(r'^\s+|\s+$', '', xml_content, flags=re.MULTILINE)
            
            logger.debug(f"Cleaned XML content:\n{xml_content}")
            
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError as xml_err:
                xml_content = f"<decision>{xml_content}</decision>" if not xml_content.startswith('<decision>') else xml_content
                root = ET.fromstring(xml_content)
            
            result = {}
            for child in root:
                result[child.tag] = (child.text or '').strip()
            
            if "action" not in result or "reason" not in result:
                raise ValueError("Missing required fields in response")
            
            if result["action"] not in ["search", "answer"]:
                raise ValueError("Invalid action type")
            
            if result["action"] == "search" and "search_term" not in result:
                raise ValueError("Missing search term for search action")
            
            logger.info(f"Decision made: {result['action']} - {result['reason']}")
            return result
            
        except Exception as e:
            logger.error(f"Decision parsing failed: {str(e)}")
            return {
                "action": "answer",
                "reason": f"Failed to parse decision: {str(e)}",
            }

    def post(self, shared, prep_res, exec_res):
        if exec_res["action"] == "search":
            shared["search_term"] = exec_res["search_term"]
        return exec_res["action"]

class SearchWeb(Node):
    def prep(self, shared):
        logger.info(f"Preparing web search for term: {shared['search_term']}")
        return shared["search_term"]
        
    def exec(self, search_term):
        return search_web(search_term)
    
    def post(self, shared, prep_res, exec_res):
        logger.debug("Updating search context")
        prev_searches = shared.get("context", [])
        shared["context"] = prev_searches + [
            {"term": shared["search_term"], "result": exec_res}
        ]
        return "decide"

def clean_llm_response(response: Any) -> str:
    """Extract the clean content from an LLM response."""
    # Handle ModelResponse object
    if hasattr(response, 'choices') and response.choices:
        # Get first choice's message content
        if hasattr(response.choices[0], 'message'):
            content = response.choices[0].message.content
        else:
            content = str(response.choices[0])
    # Fallback to content attribute
    elif hasattr(response, 'content'):
        content = response.content
    else:
        content = str(response)
    
    # Clean up the content
    content = content.strip()
    
    # Remove common prefixes
    prefixes = ['A:', 'Answer:', 'Response:']
    for prefix in prefixes:
        if content.startswith(prefix):
            content = content.replace(prefix, '', 1).strip()
    
    return content

class DirectAnswer(Node):
    def prep(self, shared):
        logger.info("Generating direct answer")
        return shared["query"], shared.get("context", "")
        
    def exec(self, inputs):
        query, context = inputs
        logger.debug(f"Generating answer for query with context length: {len(str(context))}")
        return call_llm(f"Context: {context}\nAnswer: {query}")

    def post(self, shared, prep_res, exec_res):
        clean_response = clean_llm_response(exec_res)
        logger.info(f"Generated answer: {clean_response[:100]}...")  # Log first 100 chars
        print(f"{clean_response}")  # Simplified output
        shared["answer"] = clean_response

# Connect nodes
decide = DecideAction()
search = SearchWeb()
answer = DirectAnswer()

decide - "search" >> search
decide - "answer" >> answer
search - "decide" >> decide  # Loop back

# Configure logger
logger.add("workflow.log", rotation="500 MB", level="INFO")

flow = Flow(start=decide)
logger.info("Starting workflow execution")
flow.run({"query": "Who won the Nobel Prize in Physics 2024?"})
logger.info("Workflow execution completed")
