import asyncio
import copy
import time
import warnings
from typing import Any, Dict, List, Optional


class BaseNode:
    def __init__(self) -> None:
        """
        Initialize a BaseNode with empty parameters and successors.

        This method sets up the foundational structure for nodes in a flow,
        allowing for dynamic parameter setting and node connections.
        """
        self.params: Dict[str, Any] = {}
        self.successors: Dict[str, 'BaseNode'] = {}

    def set_params(self, params: Dict[str, Any]) -> None:
        """
        Set parameters for the node.

        Args:
            params (Dict[str, Any]): A dictionary of parameters to configure the node's behavior.
        """
        self.params = params

    def add_successor(self, node: 'BaseNode', action: str = "default") -> 'BaseNode':
        """
        Add a successor node with an optional action.

        Args:
            node (BaseNode): The node to be added as a successor.
            action (str, optional): The action that triggers this successor. Defaults to "default".

        Returns:
            BaseNode: The added successor node.

        Warns:
            Warns if overwriting an existing successor for the same action.
        """
        if action in self.successors:
            warnings.warn(f"Overwriting successor for action '{action}'")
        self.successors[action] = node
        return node

    def prep(self, shared: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Prepare the node for execution by processing shared context.

        Args:
            shared (Dict[str, Any]): Shared context dictionary for the node's execution.

        Returns:
            Optional[Dict[str, Any]]: Prepared data for node execution, or None.
        """
        pass

    def exec(self, prep_res: Any) -> Any:
        """
        Execute the node's core logic using prepared results.

        Args:
            prep_res (Any): Prepared results from the prep method.

        Returns:
            Any: Execution result.
        """
        pass

    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        """
        Post-process the node's execution, potentially modifying shared context.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.
            prep_res (Any): Results from the prep method.
            exec_res (Any): Results from the exec method.

        Returns:
            Any: Post-processing result.
        """
        pass

    def _exec(self, prep_res: Any) -> Any:
        """
        Internal method to execute the node's logic.

        Args:
            prep_res (Any): Prepared results from the prep method.

        Returns:
            Any: Execution result.
        """
        return self.exec(prep_res)

    def _run(self, shared: Dict[str, Any]) -> Any:
        """
        Run the node by executing preparation, execution, and post-processing steps.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the node's execution.
        """
        p = self.prep(shared)
        e = self._exec(p)
        return self.post(shared, p, e)

    def run(self, shared: Dict[str, Any]) -> Any:
        """
        Run the node and warn if successors are present.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the node's execution.

        Warns:
            Warns that successors won't be run. Use Flow for multi-node execution.
        """
        if self.successors:
            warnings.warn("Node won't run successors. Use Flow.")
        return self._run(shared)

    def __rshift__(self, other: 'BaseNode') -> 'BaseNode':
        """
        Overload the right-shift operator to add a successor node.

        Args:
            other (BaseNode): The node to be added as a successor.

        Returns:
            BaseNode: The added successor node.
        """
        return self.add_successor(other)

    def __sub__(self, action: str) -> '_ConditionalTransition':
        """
        Create a conditional transition with a specific action.

        Args:
            action (str): The action that triggers the transition.

        Returns:
            _ConditionalTransition: A transition object for connecting nodes.

        Raises:
            TypeError: If the action is not a string.
        """
        if isinstance(action, str):
            return _ConditionalTransition(self, action)
        raise TypeError("Action must be a string")

class _ConditionalTransition:
    def __init__(self, src: BaseNode, action: str) -> None:
        """
        Initialize a conditional transition.

        Args:
            src (BaseNode): The source node for the transition.
            action (str): The action that triggers the transition.
        """
        self.src = src
        self.action = action

    def __rshift__(self, tgt: BaseNode) -> BaseNode:
        """
        Connect the transition to a target node.

        Args:
            tgt (BaseNode): The target node for the transition.

        Returns:
            BaseNode: The target node.
        """
        return self.src.add_successor(tgt, self.action)

class Node(BaseNode):
    def __init__(self, max_retries: int = 1, wait: float = 0) -> None:
        """
        Initialize a Node with retry and wait settings.

        Args:
            max_retries (int, optional): Maximum number of retries. Defaults to 1.
            wait (float, optional): Wait time between retries. Defaults to 0.
        """
        super().__init__()
        self.max_retries: int = max_retries
        self.wait: float = wait

    def exec_fallback(self, prep_res: Any, exc: Exception) -> Any:
        """
        Execute a fallback action when an exception occurs.

        Args:
            prep_res (Any): Prepared results from the prep method.
            exc (Exception): The exception that occurred.

        Returns:
            Any: Fallback result.
        """
        raise exc

    def _exec(self, prep_res: Any) -> Any:
        """
        Execute the node's logic with retries.

        Args:
            prep_res (Any): Prepared results from the prep method.

        Returns:
            Any: Execution result.
        """
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
        """
        Execute the node's logic on a batch of items.

        Args:
            items (List[Any]): List of items to process.

        Returns:
            List[Any]: List of execution results.
        """
        return [super(BatchNode, self)._exec(i) for i in (items or [])]

class Flow(BaseNode):
    def __init__(self, start: BaseNode) -> None:
        """
        Initialize a Flow with a starting node.

        Args:
            start (BaseNode): The starting node for the flow.
        """
        super().__init__()
        self.start = start

    def get_next_node(self, curr: BaseNode, action: Optional[str]) -> Optional[BaseNode]:
        """
        Get the next node in the flow based on the current node and action.

        Args:
            curr (BaseNode): The current node.
            action (Optional[str]): The action that triggers the transition.

        Returns:
            Optional[BaseNode]: The next node in the flow, or None.
        """
        nxt = curr.successors.get(action or "default")
        if not nxt and curr.successors:
            warnings.warn(f"Flow ends: '{action}' not found in {list(curr.successors)}")
        return nxt

    def _orch(self, shared: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> None:
        """
        Orchestrate the flow by executing nodes in sequence.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.
            params (Optional[Dict[str, Any]], optional): Parameters for the flow. Defaults to None.
        """
        current_node: Optional[BaseNode] = copy.copy(self.start)
        p = params or {**self.params}
        while current_node:
            current_node.set_params(p)
            action_result = current_node._run(shared)
            current_node = copy.copy(self.get_next_node(current_node, action_result))

    def _run(self, shared: Dict[str, Any]) -> Any:
        """
        Run the flow by executing the orchestration method.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the flow's execution.
        """
        pr = self.prep(shared)
        self._orch(shared)
        return self.post(shared, pr, None)

    def exec(self, prep_res: Any) -> Any:
        """
        Execute the flow's core logic.

        Args:
            prep_res (Any): Prepared results from the prep method.

        Raises:
            RuntimeError: Flow cannot be executed directly.
        """
        raise RuntimeError("Flow can't exec.")

class BatchFlow(Flow):
    def _run(self, shared: Dict[str, Any]) -> Any:
        """
        Run the batch flow by executing the orchestration method for each batch.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the batch flow's execution.
        """
        pr = self.prep(shared) or []
        for bp in pr:
            self._orch(shared, {**self.params, **bp})
        return self.post(shared, pr, None)

class AsyncNode(Node):
    def prep(self, shared: Dict[str, Any]) -> Any:
        """
        Prepare the node for asynchronous execution.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Raises:
            RuntimeError: Use prep_async instead.
        """
        raise RuntimeError("Use prep_async.")

    def exec(self, prep_res: Any) -> Any:
        """
        Execute the node's core logic asynchronously.

        Args:
            prep_res (Any): Prepared results from the prep method.

        Raises:
            RuntimeError: Use exec_async instead.
        """
        raise RuntimeError("Use exec_async.")

    def post(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        """
        Post-process the node's asynchronous execution.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.
            prep_res (Any): Results from the prep method.
            exec_res (Any): Results from the exec method.

        Raises:
            RuntimeError: Use post_async instead.
        """
        raise RuntimeError("Use post_async.")

    def exec_fallback(self, prep_res: Any, exc: Exception) -> Any:
        """
        Execute a fallback action when an exception occurs during asynchronous execution.

        Args:
            prep_res (Any): Prepared results from the prep method.
            exc (Exception): The exception that occurred.

        Raises:
            RuntimeError: Use exec_fallback_async instead.
        """
        raise RuntimeError("Use exec_fallback_async.")

    def _run(self, shared: Dict[str, Any]) -> Any:
        """
        Run the node asynchronously.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Raises:
            RuntimeError: Use run_async instead.
        """
        raise RuntimeError("Use run_async.")

    async def prep_async(self, shared: Dict[str, Any]) -> Any:
        """
        Prepare the node for asynchronous execution.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Prepared data for asynchronous execution.
        """
        pass

    async def exec_async(self, prep_res: Any) -> Any:
        """
        Execute the node's core logic asynchronously.

        Args:
            prep_res (Any): Prepared results from the prep method.

        Returns:
            Any: Asynchronous execution result.
        """
        pass

    async def exec_fallback_async(self, prep_res: Any, exc: Exception) -> Any:
        """
        Execute a fallback action when an exception occurs during asynchronous execution.

        Args:
            prep_res (Any): Prepared results from the prep method.
            exc (Exception): The exception that occurred.

        Returns:
            Any: Fallback result.
        """
        raise exc

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Any:
        """
        Post-process the node's asynchronous execution.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.
            prep_res (Any): Results from the prep method.
            exec_res (Any): Results from the exec method.

        Returns:
            Any: Post-processing result.
        """
        pass

    async def _exec(self, prep_res: Any) -> Any:
        """
        Execute the node's logic asynchronously with retries.

        Args:
            prep_res (Any): Prepared results from the prep method.

        Returns:
            Any: Asynchronous execution result.
        """
        for i in range(self.max_retries):
            try:
                return await self.exec_async(prep_res)
            except Exception as e:
                if i == self.max_retries - 1:
                    return await self.exec_fallback_async(prep_res, e)
                if self.wait > 0:
                    await asyncio.sleep(self.wait)

    async def run_async(self, shared: Dict[str, Any]) -> Any:
        """
        Run the node asynchronously and warn if successors are present.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the node's asynchronous execution.

        Warns:
            Warns that successors won't be run. Use AsyncFlow for multi-node execution.
        """
        if self.successors:
            warnings.warn("Node won't run successors. Use AsyncFlow.")
        return await self._run_async(shared)

    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        """
        Run the node asynchronously by executing preparation, execution, and post-processing steps.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the node's asynchronous execution.
        """
        p = await self.prep_async(shared)
        e = await self._exec(p)
        return await self.post_async(shared, p, e)

class AsyncBatchNode(AsyncNode, BatchNode):
    async def _exec(self, items: List[Any]) -> List[Any]:
        """
        Execute the node's logic asynchronously on a batch of items.

        Args:
            items (List[Any]): List of items to process.

        Returns:
            List[Any]: List of asynchronous execution results.
        """
        return [await super(AsyncBatchNode, self)._exec(i) for i in items]

class AsyncParallelBatchNode(AsyncNode, BatchNode):
    async def _exec(self, items: List[Any]) -> List[Any]:
        """
        Execute the node's logic asynchronously on a batch of items in parallel.

        Args:
            items (List[Any]): List of items to process.

        Returns:
            List[Any]: List of asynchronous execution results.
        """
        return await asyncio.gather(*(super(AsyncParallelBatchNode, self)._exec(i) for i in items))

class AsyncFlow(Flow, AsyncNode):
    async def _orch_async(self, shared: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> None:
        """
        Orchestrate the asynchronous flow by executing nodes in sequence.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.
            params (Optional[Dict[str, Any]], optional): Parameters for the flow. Defaults to None.
        """
        current_node: Optional[BaseNode] = copy.copy(self.start)
        p = params or {**self.params}
        while current_node:
            current_node.set_params(p)
            action_result = await current_node._run_async(shared) if isinstance(current_node, AsyncNode) else current_node._run(shared)
            current_node = copy.copy(self.get_next_node(current_node, action_result))

    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        """
        Run the asynchronous flow by executing the orchestration method.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the asynchronous flow's execution.
        """
        p = await self.prep_async(shared)
        await self._orch_async(shared)
        return await self.post_async(shared, p, None)

class AsyncBatchFlow(AsyncFlow, BatchFlow):
    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        """
        Run the asynchronous batch flow by executing the orchestration method for each batch.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the asynchronous batch flow's execution.
        """
        pr = await self.prep_async(shared) or []
        for bp in pr:
            await self._orch_async(shared, {**self.params, **bp})
        return await self.post_async(shared, pr, None)

class AsyncParallelBatchFlow(AsyncFlow, BatchFlow):
    async def _run_async(self, shared: Dict[str, Any]) -> Any:
        """
        Run the asynchronous parallel batch flow by executing the orchestration method for each batch in parallel.

        Args:
            shared (Dict[str, Any]): Shared context dictionary.

        Returns:
            Any: Result of the asynchronous parallel batch flow's execution.
        """
        pr = await self.prep_async(shared) or []
        await asyncio.gather(*(self._orch_async(shared, {**self.params, **bp}) for bp in pr))
        return await self.post_async(shared, pr, None)

def call_llm(prompt: str, model_name: str = "gemini/gemini-2.0-flash") -> Any:
    """
    A simple helper to call an LLM using litellm.

    Args:
        prompt (str): The prompt to pass to the LLM.
        model_name (str, optional): The name of the LLM model. Defaults to "gemini/gemini-2.0-flash".

    Returns:
        Any: The response from the LLM.

    Raises:
        ImportError: If litellm is not installed.
    """
    try:
        from litellm import completion
    except ImportError:
        raise ImportError("litellm is not installed. Please install litellm to use this function.")
    return completion(model=model_name, messages=[{"role": "user", "content": prompt}])

async def call_llm_async(prompt: str, model_name: str = "gemini/gemini-2.0-flash") -> Any:
    """
    A simple async helper to call an LLM using litellm.

    Args:
        prompt (str): The prompt to pass to the LLM.
        model_name (str, optional): The name of the LLM model. Defaults to "gemini/gemini-2.0-flash".

    Returns:
        Any: The response from the LLM.

    Raises:
        ImportError: If litellm is not installed.
    """
    try:
        from litellm import acompletion
    except ImportError:
        raise ImportError("litellm is not installed. Please install litellm to use this function.")
    response = await acompletion(model=model_name, messages=[{"role": "user", "content": prompt}])
    return response

def call_llm_message(messages: List[Dict[str, str]], model_name: str = "gemini/gemini-2.0-flash") -> Any:
    """
    A simple helper to call an LLM using litellm with a list of messages.

    Args:
        messages (List[Dict[str, str]]): A list of messages to pass to the LLM.
        model_name (str, optional): The name of the LLM model. Defaults to "gemini/gemini-2.0-flash".

    Returns:
        Any: The response from the LLM.

    Raises:
        ImportError: If litellm is not installed.
    """
    try:
        from litellm import completion
    except ImportError:
        raise ImportError("litellm is not installed. Please install litellm to use this function.")
    return completion(model=model_name, messages=messages)

async def call_llm_message_async(messages: List[Dict[str, str]], model_name: str = "gemini/gemini-2.0-flash") -> Any:
    """
    A simple async helper to call an LLM using litellm with a list of messages.

    Args:
        messages (List[Dict[str, str]]): A list of messages to pass to the LLM.
        model_name (str, optional): The name of the LLM model. Defaults to "gemini/gemini-2.0-flash".

    Returns:
        Any: The response from the LLM.

    Raises:
        ImportError: If litellm is not installed.
    """
    try:
        from litellm import acompletion
    except ImportError:
        raise ImportError("litellm is not installed. Please install litellm to use this function.")
    response = await acompletion(model=model_name, messages=messages)
    return response

class FluentBuilder:
    """A convenient Fluent interface to build a workflow."""
    def __init__(self) -> None:
        self.start: Optional[BaseNode] = None
        self.current: Optional[BaseNode] = None

    def set_start(self, node: BaseNode) -> 'FluentBuilder':
        """Set the starting node of the workflow."""
        self.start = node
        self.current = node
        return self

    def then(self, node: BaseNode, action: str = "default") -> 'FluentBuilder':
        """Chain the next node to the current node with an optional action."""
        if not self.current:
            raise ValueError("Start node not set. Call set_start() first.")
        self.current.add_successor(node, action)
        self.current = node
        return self

    def branch(self, action: str, node: BaseNode) -> 'FluentBuilder':
        """Add an alternative branch from the current node without moving the current pointer."""
        if not self.current:
            raise ValueError("Start node not set. Call set_start() first.")
        self.current.add_successor(node, action)
        return self

    def build(self) -> 'Flow':
        """Build and return the workflow Flow object."""
        if not self.start:
            raise ValueError("Start node not set. Call set_start() first.")
        return Flow(self.start)