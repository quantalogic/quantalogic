import asyncio
import copy
import time
import warnings
from typing import Any, Dict, List, Optional


class BaseNode:
    def __init__(self) -> None:
        self.params: Dict[str, Any] = {}
        self.successors: Dict[str, 'BaseNode'] = {}

    def set_params(self, params: Dict[str, Any]) -> None:
        self.params = params

    def add_successor(self, node: 'BaseNode', action: str = "default") -> 'BaseNode':
        if action in self.successors:
            warnings.warn(f"Overwriting successor for action '{action}'")
        self.successors[action] = node
        return node

    def prep(self, shared: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    def exec(self, prep_res: Any) -> Any:
        pass

    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        pass

    def _exec(self, prep_res: Any) -> Any:
        return self.exec(prep_res)

    def _run(self, shared: Dict[str, Any]) -> Any:
        p = self.prep(shared)
        e = self._exec(p)
        return self.post(shared, p, e)

    def run(self, shared: Dict[str, Any]) -> Any:
        if self.successors:
            warnings.warn("Node won't run successors. Use Flow.")
        return self._run(shared)

    def __rshift__(self, other: 'BaseNode') -> 'BaseNode':
        return self.add_successor(other)

    def __sub__(self, action: str) -> '_ConditionalTransition':
        if isinstance(action, str):
            return _ConditionalTransition(self, action)
        raise TypeError("Action must be a string")

class _ConditionalTransition:
    def __init__(self, src: BaseNode, action: str) -> None:
        self.src = src
        self.action = action

    def __rshift__(self, tgt: BaseNode) -> BaseNode:
        return self.src.add_successor(tgt, self.action)

class Node(BaseNode):
    def __init__(self, max_retries: int = 1, wait: float = 0) -> None:
        super().__init__()
        self.max_retries: int = max_retries
        self.wait: float = wait

    def exec_fallback(self, prep_res: Any, exc: Exception) -> Any:
        raise exc

    def _exec(self, prep_res: Any) -> Any:
        for self.cur_retry in range(self.max_retries):
            try:
                return self.exec(prep_res)
            except Exception as e:
                if self.cur_retry == self.max_retries - 1:
                    return self.exec_fallback(prep_res, e)
                if self.wait > 0:
                    time.sleep(self.wait)

class BatchNode(Node):
    def _exec(self, items: List[Any]) -> List[Any]:
        return [super(BatchNode, self)._exec(i) for i in (items or [])]

class Flow(BaseNode):
    def __init__(self, start: BaseNode) -> None:
        super().__init__()
        self.start = start

    def get_next_node(self, curr: BaseNode, action: Optional[str]) -> Optional[BaseNode]:
        nxt = curr.successors.get(action or "default")
        if not nxt and curr.successors:
            warnings.warn(f"Flow ends: '{action}' not found in {list(curr.successors)}")
        return nxt

    def _orch(self, shared: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> None:
        current_node: Optional[BaseNode] = copy.copy(self.start)
        p = params or {**self.params}
        while current_node:
            current_node.set_params(p)
            action_result = current_node._run(shared)
            current_node = copy.copy(self.get_next_node(current_node, action_result))

    def _run(self, shared: Dict[str, Any]) -> Any:
        pr = self.prep(shared)
        self._orch(shared)
        return self.post(shared, pr, None)

    def exec(self, prep_res: Any) -> Any:
        raise RuntimeError("Flow can't exec.")

class BatchFlow(Flow):
    def _run(self, shared: Dict[str, Any]) -> Any:
        pr = self.prep(shared) or []
        for bp in pr:
            self._orch(shared, {**self.params, **bp})
        return self.post(shared, pr, None)

class AsyncNode(Node):
    def prep(self, shared: Dict[str, Any]) -> Any:
        raise RuntimeError("Use prep_async.")

    def exec(self, prep_res: Any) -> Any:
        raise RuntimeError("Use exec_async.")

    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        raise RuntimeError("Use post_async.")

    def exec_fallback(self, prep_res: Any, exc: Exception) -> Any:
        raise RuntimeError("Use exec_fallback_async.")

    def _run(self, shared: Dict[str, Any]) -> Any:
        raise RuntimeError("Use run_async.")

    async def prep_async(self, shared: Dict[str, Any]) -> Any:
        pass

    async def exec_async(self, prep_res: Any) -> Any:
        pass

    async def exec_fallback_async(self, prep_res: Any, exc: Exception) -> Any:
        raise exc

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        pass

    async def _exec(self, prep_res: Any) -> Any:
        for i in range(self.max_retries):
            try:
                return await self.exec_async(prep_res)
            except Exception as e:
                if i == self.max_retries - 1:
                    return await self.exec_fallback_async(prep_res, e)
                if self.wait > 0:
                    await asyncio.sleep(self.wait)

    async def run_async(self, shared: Dict[str, Any]) -> Any:
        if self.successors:
            warnings.warn("Node won't run successors. Use AsyncFlow.")
        return await self._run_async(shared)

    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        p = await self.prep_async(shared)
        e = await self._exec(p)
        return await self.post_async(shared, p, e)

class AsyncBatchNode(AsyncNode, BatchNode):
    async def _exec(self, items: List[Any]) -> List[Any]:
        return [await super(AsyncBatchNode, self)._exec(i) for i in items]

class AsyncParallelBatchNode(AsyncNode, BatchNode):
    async def _exec(self, items: List[Any]) -> List[Any]:
        return await asyncio.gather(*(super(AsyncParallelBatchNode, self)._exec(i) for i in items))

class AsyncFlow(Flow, AsyncNode):
    async def _orch_async(self, shared: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> None:
        current_node: Optional[BaseNode] = copy.copy(self.start)
        p = params or {**self.params}
        while current_node:
            current_node.set_params(p)
            action_result = await current_node._run_async(shared) if isinstance(current_node, AsyncNode) else current_node._run(shared)
            current_node = copy.copy(self.get_next_node(current_node, action_result))

    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        p = await self.prep_async(shared)
        await self._orch_async(shared)
        return await self.post_async(shared, p, None)

class AsyncBatchFlow(AsyncFlow, BatchFlow):
    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        pr = await self.prep_async(shared) or []
        for bp in pr:
            await self._orch_async(shared, {**self.params, **bp})
        return await self.post_async(shared, pr, None)

class AsyncParallelBatchFlow(AsyncFlow, BatchFlow):
    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        pr = await self.prep_async(shared) or []
        await asyncio.gather(*(self._orch_async(shared, {**self.params, **bp}) for bp in pr))
        return await self.post_async(shared, pr, None)

def call_llm(prompt: str, model_name: str = "gemini/gemini-2.0-flash") -> Any:
    """
    A simple helper to call an LLM using litellm.
    Ensure your API key is set appropriately.
    """
    try:
        from litellm import completion
    except ImportError:
        raise ImportError("litellm is not installed. Please install litellm to use this function.")
    return completion(model=model_name, messages=[{"role": "user", "content": prompt}])

async def call_llm_async(prompt: str, model_name: str = "gemini/gemini-2.0-flash") -> Any:
    """
    A simple async helper to call an LLM using litellm.
    Ensure your API key is set appropriately.
    """
    try:
        from litellm import acompletion
    except ImportError:
        raise ImportError("litellm is not installed. Please install litellm to use this function.")
    response = await acompletion(model=model_name, messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content
