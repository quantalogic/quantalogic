#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio",
#     "tiktoken",
#     "instructor",
#     "asyncio",
#     "numpy",
#     "openai>=1.0.0",
# ]
# ///

import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager
from functools import partial
from typing import Any, Callable, Dict, List, Tuple

import numpy as np
from litellm import acompletion, embedding
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from tiktoken import encoding_for_model

# Configure logging
logger.add("memgpt.log", rotation="10 MB")

# Default configurations
MODEL_NAME = "gemini/gemini-2.0-flash"
EMBEDDING_MODEL_NAME = "gemini/text-embedding-004"
EXPECTED_EMBEDDING_DIM = 768

class StorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(default="sqlite", pattern="^sqlite$")
    path: str = Field(default="storage.db")

class Config(BaseModel):
    model: str = MODEL_NAME
    context_window: int = Field(default=4000, ge=1000)
    warning_tokens: int = Field(default=2800, ge=500)
    flush_tokens: int = Field(default=4000, ge=1000)
    embedding_model: str = EMBEDDING_MODEL_NAME
    tokenizer_model: str = "gpt-4"
    recall_storage: StorageConfig = Field(default_factory=lambda: StorageConfig(path="recall.db"))
    archival_storage: StorageConfig = Field(default_factory=lambda: StorageConfig(path="archival.db"))

def init_database(db_path: str, reset: bool = False):
    if reset and os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY,
            text TEXT,
            embedding BLOB,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

async def generate_embedding(text: str, model: str) -> np.ndarray:
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: embedding(model=model, input=[text]))
        emb = np.array(response['data'][0]['embedding'], dtype=np.float32)
        logger.debug(f"Generated embedding for '{text[:50]}...': shape={emb.shape}")
        return emb
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

@asynccontextmanager
async def memory_scope(config: Config, storage_type: str = "recall"):
    storage_config = config.recall_storage if storage_type == "recall" else config.archival_storage
    init_database(storage_config.path)
    conn = sqlite3.connect(storage_config.path)
    queue = []
    tokenizer = encoding_for_model(config.tokenizer_model)

    async def _count_tokens(text: str) -> int:
        return len(tokenizer.encode(text))

    async def _trim_queue():
        total = sum(await asyncio.gather(*map(_count_tokens, queue)))
        if total > config.flush_tokens:
            to_summarize = queue[:max(1, len(queue)//10)]
            summary = await summarize_messages(to_summarize, config.model)
            queue[:len(to_summarize)] = [summary]

    async def _insert(text: str):
        try:
            emb = await generate_embedding(text, config.embedding_model)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO memory (text, embedding) VALUES (?, ?)",
                           (text, emb.tobytes()))
            conn.commit()
            queue.append(text)
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            raise

    async def _search(query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        try:
            query_emb = await generate_embedding(query, config.embedding_model)
            cursor = conn.cursor()
            cursor.execute("SELECT id, text, embedding FROM memory")
            results = []
            for row in cursor.fetchall():
                id, text, emb_bytes = row
                stored_emb = np.frombuffer(emb_bytes, dtype=np.float32)
                if stored_emb.shape != query_emb.shape:
                    stored_emb = await generate_embedding(text, config.embedding_model)
                    cursor.execute("UPDATE memory SET embedding = ? WHERE id = ?",
                                   (stored_emb.tobytes(), id))
                    conn.commit()
                similarity = cosine_similarity(query_emb, stored_emb)
                results.append((text, similarity))
            return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    yield {
        "insert": _insert,
        "search": _search,
        "queue": queue,
        "trim": _trim_queue,
        "conn": conn
    }
    conn.close()

async def summarize_messages(messages: List[str], model: str) -> str:
    prompt = "Concise summary of these messages:\n" + "\n".join(messages)
    try:
        response = await acompletion(model=model, messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return "Summary unavailable"

class FunctionDescriptor:
    def __init__(self, func: Callable):
        self.func = func

    def __set_name__(self, owner, name):
        owner._functions[name] = self.func

    def __get__(self, obj, objtype=None):
        return partial(self.func, obj) if obj else self.func

class MemGPT:
    _functions: Dict[str, Callable] = {}

    def __init__(self, config: Config = Config()):
        self.config = config
        self.context = None
        self.system_prompt = (
            "You are an AI assistant with memory capabilities. "
            "Use these information sources:\n"
            "1. Current Context: {context}\n"
            "2. Conversation History: {history}\n"
            "3. Relevant Memories:\n{search_results}\n\n"
            "Respond naturally while incorporating relevant information "
            "from memory when appropriate."
        )

    @FunctionDescriptor
    async def search_memory(self, query: str, storage_type: str = "recall") -> List[Tuple[str, float]]:
        async with memory_scope(self.config, storage_type) as mem:
            return await mem["search"](query)

    @FunctionDescriptor
    async def save_memory(self, text: str, storage_type: str = "archival") -> str:
        async with memory_scope(self.config, storage_type) as mem:
            await mem["insert"](text)
            return "Information saved successfully"

    @FunctionDescriptor
    async def update_context(self, context: str) -> str:
        self.context = context
        return f"Context updated: {context}"

    async def _hybrid_search(self, query: str) -> List[Tuple[str, float]]:
        recall_results = await self.search_memory(query, "recall")
        archival_results = await self.search_memory(query, "archival")
        combined = recall_results + archival_results
        
        # Time-weighted scoring
        time_weight = 0.2
        weighted_results = []
        for idx, (text, score) in enumerate(combined):
            freshness = 1 / (idx + 1)
            weighted_score = (1 - time_weight) * score + time_weight * freshness
            weighted_results.append((text, weighted_score))
        
        return sorted(weighted_results, key=lambda x: x[1], reverse=True)[:5]

    async def _build_prompt(self, message: str, history: List[str], search_results: List[Tuple[str, float]]) -> str:
        context_str = f"Current Context: {self.context}" if self.context else "No specific context"
        results_str = "\n".join([f"• {text} (relevance: {score:.2f})" for text, score in search_results[:3]])
        
        return self.system_prompt.format(
            context=context_str,
            history="\n".join(history[-3:]),
            search_results=results_str
        ) + f"\n\nUser: {message}"

    async def process(self, message: str) -> str:
        if message.startswith("/"):
            command, *args = message[1:].split(" ", 1)
            command = command.lower()
            args = args[0] if args else ""

            if command == "search":
                storage_type = "recall"
                query = args
                if " in " in args.lower():
                    query, storage = args.split(" in ", 1)
                    storage_type = "archival" if "archival" in storage.lower() else "recall"
                results = await self.search_memory(query, storage_type)
                return "\n".join(f"{i+1}. {text} ({score:.2f})" for i, (text, score) in enumerate(results))
            
            elif command == "save":
                storage_type = "archival"
                text = args
                if " in " in args.lower():
                    text, storage = args.split(" in ", 1)
                    storage_type = "recall" if "recall" in storage.lower() else "archival"
                await self.save_memory(text, storage_type)
                return f"Saved in {storage_type} storage: {text}"
            
            elif command == "context":
                await self.update_context(args)
                return f"Context updated: {args}"
            
            elif command == "help":
                return ("Available commands:\n"
                        "/search <query> [in archival] - Search memory\n"
                        "/save <text> [in recall] - Store information\n"
                        "/context <text> - Set current focus\n"
                        "/help - Show this message")
            
            else:
                return "Unrecognized command"
        
        async with memory_scope(self.config, "recall") as mem:
            await mem["insert"](f"user: {message}")
            await mem["trim"]()
            
            search_query = message.split("?")[0].strip() if "?" in message else message
            search_results = await self._hybrid_search(search_query)
            
            if self.context:
                context_emb = await generate_embedding(self.context, self.config.embedding_model)
                enhanced_results = []
                for text, score in search_results:
                    text_emb = await generate_embedding(text, self.config.embedding_model)
                    context_sim = cosine_similarity(text_emb, context_emb)
                    enhanced_score = score * (1 + context_sim)
                    enhanced_results.append((text, enhanced_score))
                search_results = sorted(enhanced_results, key=lambda x: x[1], reverse=True)
            
            prompt = await self._build_prompt(
                message=message,
                history=mem["queue"],
                search_results=search_results
            )
            
            try:
                response = await acompletion(
                    model=self.config.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                output = response.choices[0].message.content
                await mem["insert"](f"assistant: {output}")
                return output
            except Exception as e:
                logger.error(f"Processing failed: {e}")
                return "Error processing request"

async def main():
    config = Config(
        model=os.environ.get("MEMGPT_MODEL", MODEL_NAME),
        context_window=8000,
        warning_tokens=6000,
        flush_tokens=7500,
        embedding_model=os.environ.get("MEMGPT_EMBEDDING_MODEL", EMBEDDING_MODEL_NAME),
        recall_storage=StorageConfig(path="recall.db"),
        archival_storage=StorageConfig(path="archival.db")
    )
    
    memgpt = MemGPT(config)
    init_database(config.recall_storage.path, reset=True)
    init_database(config.archival_storage.path, reset=True)

    interactions = [
        "What am I working on?",
        "/save The project deadline is March 15, 2025 in archival",
        "/search project deadline in archival",
        "/context Data preprocessing pipeline",
        "What's the current focus?",
        "When is the project deadline?"
    ]

    for query in interactions:
        print(f"\nUser: {query}")
        response = await memgpt.process(query)
        print(f"Assistant: {response}")

if __name__ == "__main__":
    asyncio.run(main())