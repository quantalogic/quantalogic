#!/usr/bin/env -S uv run

# /// script
# # requires-python = ">=3.12"
# dependencies = [
#     "pydantic",
#     "litellm",
# ]
# ///

from __future__ import annotations

import asyncio
import copy
import time
import warnings
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveInt,
    model_validator,
)

# --------------------------
# Pydantic Models
# --------------------------


class NodeParams(BaseModel):
    """Base parameters for all nodes"""

    model_config = ConfigDict(extra="forbid", frozen=False)
    max_retries: PositiveInt = Field(1, description="Maximum number of execution retries")
    wait: NonNegativeFloat = Field(0.0, description="Seconds to wait between retries")


class FlowParams(BaseModel):
    """Base parameters for flows"""

    model_config = ConfigDict(extra="forbid")
    stop_on_error: bool = Field(True, description="Stop flow on any node error")


class LLMParams(NodeParams):
    """Parameters for LLM nodes"""

    model_name: str = Field("gemini/gemini-2.0-flash")
    temperature: float = Field(0.7, ge=0.0, le=1.0)
    max_tokens: Optional[PositiveInt] = None


class BatchParams(NodeParams):
    """Parameters for batch processing"""

    batch_size: PositiveInt = Field(32, description="Items per batch")
    fail_fast: bool = Field(True, description="Stop batch on first error")


class AsyncParams(NodeParams):
    """Async-specific parameters"""

    timeout: PositiveInt = Field(30, description="Timeout in seconds")
    concurrent_limit: PositiveInt = Field(10, description="Max concurrent operations")


# --------------------------
# Core Node Classes
# --------------------------

TParams = TypeVar("TParams", bound=NodeParams)


class BaseNode(Generic[TParams]):
    _successors: Dict[str, BaseNode]
    params: TParams

    def __init__(self, params: TParams | Dict[str, Any] = None) -> None:
        """Initialize node with validated parameters"""
        self._successors = {}
        self.set_params(params or {})

    @classmethod
    def get_params_model(cls) -> Type[TParams]:
        """Get the Pydantic model for this node's parameters"""
        return cls.__orig_bases__[0].__args__[0]  # type: ignore

    def set_params(self, params: TParams | Dict[str, Any]) -> None:
        """Validate and set parameters"""
        if not isinstance(params, BaseModel):
            params = self.get_params_model().model_validate(params)
        self.params = params

    def add_successor(self, node: BaseNode, action: str = "default") -> BaseNode:
        """Add a successor node with action key validation"""
        if not isinstance(action, str) or not action.isidentifier():
            raise ValueError(f"Invalid action key: {action}. Must be valid Python identifier")

        if action in self._successors:
            warnings.warn(f"Overwriting successor for action '{action}'")

        self._successors[action] = node
        return node

    def get_successor(self, action: str = "default") -> Optional[BaseNode]:
        """Get successor with type checking"""
        return self._successors.get(action)

    # Execution lifecycle methods
    def prep(self, shared: Dict[str, Any]) -> Any:
        """Preparation phase (sync)"""
        pass

    def exec(self, prep_res: Any) -> Any:
        """Execution phase (sync)"""
        raise NotImplementedError

    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        """Post-processing phase (sync)"""
        pass

    def _execute(self, shared: Dict[str, Any]) -> Any:
        """Internal execution flow"""
        prep_res = self.prep(shared)
        exec_res = self._retry_execute(prep_res)
        return self.post(shared, prep_res, exec_res)

    def _retry_execute(self, prep_res: Any) -> Any:
        """Retry logic with validated parameters"""
        for attempt in range(self.params.max_retries):
            try:
                return self.exec(prep_res)
            except Exception as e:
                if attempt == self.params.max_retries - 1:
                    raise
                if self.params.wait > 0:
                    time.sleep(self.params.wait)
        raise RuntimeError("Execution failed after retries")

    def __rshift__(self, other: BaseNode) -> BaseNode:
        """Operator overload for adding default successor"""
        return self.add_successor(other)

    def __sub__(self, action: str) -> _ConditionalTransition:
        """Operator overload for conditional transitions"""
        return _ConditionalTransition(self, action)


# --------------------------
# Specialized Node Types
# --------------------------


class Node(BaseNode[NodeParams]):
    """Basic synchronous node"""

    def exec(self, prep_res: Any) -> Any:
        """Example implementation"""
        return f"Processed {prep_res}"


class LLMNode(BaseNode[LLMParams]):
    """LLM node with validated parameters"""

    def exec(self, prep_res: str) -> str:
        """Execute LLM call with validated parameters"""
        return call_llm(prep_res, self.params)


class BatchNode(BaseNode[BatchParams]):
    """Batch processing node"""

    def _execute_batch(self, items: List[Any]) -> List[Any]:
        return [self._retry_execute(item) for item in items]

    def exec(self, prep_res: List[Any]) -> List[Any]:
        """Batch execution with size control"""
        return [
            result for batch in self._chunk(prep_res, self.params.batch_size) for result in self._execute_batch(batch)
        ]

    @staticmethod
    def _chunk(lst: List[Any], size: int) -> List[List[Any]]:
        return [lst[i : i + size] for i in range(0, len(lst), size)]


# --------------------------
# Async Implementation
# --------------------------


class AsyncNode(BaseNode[AsyncParams]):
    """Asynchronous node base class"""

    async def prep_async(self, shared: Dict[str, Any]) -> Any:
        """Async preparation phase"""
        pass

    async def exec_async(self, prep_res: Any) -> Any:
        """Async execution phase"""
        raise NotImplementedError

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        """Async post-processing phase"""
        pass

    async def _execute_async(self, shared: Dict[str, Any]) -> Any:
        """Internal async execution flow"""
        prep_res = await self.prep_async(shared)
        exec_res = await self._retry_execute_async(prep_res)
        return await self.post_async(shared, prep_res, exec_res)

    async def _retry_execute_async(self, prep_res: Any) -> Any:
        """Async retry logic with timeout"""
        for attempt in range(self.params.max_retries):
            try:
                return await asyncio.wait_for(self.exec_async(prep_res), timeout=self.params.timeout)
            except Exception as e:
                if attempt == self.params.max_retries - 1:
                    raise
                if self.params.wait > 0:
                    await asyncio.sleep(self.params.wait)
        raise RuntimeError("Async execution failed after retries")


class AsyncLLMNode(AsyncNode):
    """Async LLM node with rate limiting"""

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def validate_concurrency(self):
        if self.params.concurrent_limit > 10:
            warnings.warn("High concurrency may cause rate limiting")
        return self

    async def exec_async(self, prep_res: str) -> str:
        """Execute async LLM call with concurrency control"""
        async with Semaphore(self.params.concurrent_limit):
            return await call_llm_async(prep_res, self.params)


# --------------------------
# Flow Control
# --------------------------


class Flow(BaseNode[FlowParams]):
    """Workflow orchestrator"""

    def __init__(self, start_node: BaseNode, params: FlowParams | Dict[str, Any] = None):
        super().__init__(params)
        self.start_node = start_node

    def _orchestrate(self, shared: Dict[str, Any]) -> None:
        """Execute workflow with validated parameters"""
        current = copy.copy(self.start_node)
        while current:
            result = current._execute(shared)
            current = current.get_successor(str(result))

    def exec(self, prep_res: Dict[str, Any]) -> None:
        """Execute full workflow"""
        try:
            self._orchestrate(prep_res)
        except Exception as e:
            if self.params.stop_on_error:
                raise
            warnings.warn(f"Flow continued after error: {str(e)}")


class AsyncFlow(Flow):
    """Asynchronous workflow orchestrator"""

    async def _orchestrate_async(self, shared: Dict[str, Any]) -> None:
        """Async workflow execution"""
        current = copy.copy(self.start_node)
        while current:
            if isinstance(current, AsyncNode):
                result = await current._execute_async(shared)
            else:
                result = current._execute(shared)
            current = current.get_successor(str(result))

    async def exec_async(self, prep_res: Dict[str, Any]) -> None:
        """Execute async workflow"""
        try:
            await self._orchestrate_async(prep_res)
        except Exception as e:
            if self.params.stop_on_error:
                raise
            warnings.warn(f"Async flow continued after error: {str(e)}")


# --------------------------
# Helper Classes/Functions
# --------------------------


class _ConditionalTransition:
    def __init__(self, src: BaseNode, action: str) -> None:
        self.src = src
        self.action = action

    def __rshift__(self, tgt: BaseNode) -> BaseNode:
        return self.src.add_successor(tgt, self.action)


class Semaphore:
    """Context manager for async rate limiting"""

    def __init__(self, concurrency: int):
        self.semaphore = asyncio.Semaphore(concurrency)

    async def __aenter__(self):
        """
        Asynchronous context manager entry method.

        This magic method is called when entering an async context manager block.
        It acquires the semaphore before allowing execution to proceed.

        Returns:
            self: Returns the instance itself to be used as the context manager.

        Raises:
            Any exceptions that may occur during semaphore acquisition.
        """
        await self.semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Exit the asynchronous context manager and release the semaphore.

        This method is called when exiting the async context manager (i.e., at the end of an 'async with' block).
        It releases the semaphore that was acquired in __aenter__, allowing other tasks to proceed.

        Args:
            exc_type: Type of the exception that caused the context to be exited (None if no exception)
            exc: Exception instance that caused the context to be exited (None if no exception)
            tb: Traceback of the exception that caused the context to be exited (None if no exception)

        Returns:
            None
        """
        self.semaphore.release()


def call_llm(prompt: str, params: LLMParams) -> str:
    """Execute LLM call with validated parameters"""
    try:
        from litellm import completion
    except ImportError:
        raise ImportError("litellm required for LLM calls")
    
    response = completion(
        model=params.model_name,
        messages=[{
            "role": "user", 
            "content": prompt
        }],
    )
    return response.choices[0].message.content


async def call_llm_async(prompt: str, params: LLMParams) -> str:
    """Execute async LLM call with validated parameters"""
    try:
        from litellm import acompletion
    except ImportError:
        raise ImportError("litellm required for LLM calls")

    response = await acompletion(
        model=params.model_name,
        messages=[{
            "role": "user", 
            "content": [{"text": prompt}]  # Vertex AI expects content as a list with text
        }],
        temperature=params.temperature,
        max_tokens=params.max_tokens,
    )
    return response.choices[0].message.content


async def call_llm_messages(messages: List[Dict[str, str]], params: LLMParams) -> str:
    """Execute async LLM call with multiple messages"""
    try:
        from litellm import acompletion
    except ImportError:
        raise ImportError("litellm required for LLM calls")

    response = await acompletion(
        model=params.model_name,
        messages=messages,
        temperature=params.temperature,
        max_tokens=params.max_tokens,
    )
    return response.choices[0].message.content


async def call_llm_message_async(messages: List[Dict[str, str]], params: LLMParams) -> str:
    """Execute async LLM call with multiple messages"""
    try:
        from litellm import acompletion
    except ImportError:
        raise ImportError("litellm required for LLM calls")

    response = await acompletion(
        model=params.model_name,
        messages=messages,
        temperature=params.temperature,
        max_tokens=params.max_tokens,
    )
    return response.choices[0].message.content


