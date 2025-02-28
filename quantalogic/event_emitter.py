import asyncio
import inspect
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from loguru import logger


class EventEmitter:
    """A thread-safe event emitter class for managing event listeners and emissions with enhanced features.

    This class allows registering listeners for specific events or all events using a wildcard ('*').
    Listeners can be registered with priorities and metadata for better control and debugging.
    The class is backward compatible with the original EventEmitter and includes additional features
    like error handling and debugging tools.

    Now supports both synchronous and asynchronous listeners (coroutines). Synchronous listeners are
    executed immediately, while asynchronous listeners are scheduled in a background asyncio event loop.
    Note that errors from async listeners may be handled in a background thread, so error handlers must be
    thread-safe if provided.
    """

    def __init__(self) -> None:
        """Initialize an empty EventEmitter instance.

        Creates an empty dictionary to store event listeners,
        where each event can have multiple callable listeners with priorities and metadata.
        Also initializes a list for wildcard listeners that listen to all events.
        Starts a background asyncio event loop in a daemon thread to handle async listeners.
        """
        # Listeners stored as (callable, priority, metadata) tuples
        self._listeners: dict[str, list[Tuple[Callable[..., Any], int, Optional[Dict[str, Any]]]]] = {}
        self._wildcard_listeners: list[Tuple[Callable[..., Any], int, Optional[Dict[str, Any]]]] = []
        self._lock = threading.RLock()
        self.context: dict[str, Any] = {}  # Store context data like task_id

        # Initialize background asyncio event loop
        self._loop = asyncio.new_event_loop()
        self._stop_future = self._loop.create_future()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        """Run the background asyncio event loop until stopped."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._stop_future)

    def _schedule_async_listener(
        self,
        listener: Callable[..., Any],
        event: str,
        listener_args: Tuple[Any, ...],
        error_handler: Optional[Callable[[Exception], None]],
        metadata: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> None:
        """Schedule an async listener in the background loop and handle errors."""
        kwargs = kwargs or {}  # Ensure kwargs is a dict if None
        coro = listener(event, *listener_args, **kwargs)  # Pass event, args, and kwargs
        task = self._loop.create_task(coro)
        if error_handler:
            task.add_done_callback(lambda t: self._handle_task_error(t, error_handler, metadata))

    def _handle_task_error(
        self,
        task: asyncio.Task,
        error_handler: Optional[Callable[[Exception], None]],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Handle exceptions from async listeners."""
        try:
            task.result()
        except Exception as e:
            if error_handler:
                error_handler(e)
            else:
                error_msg = f"Error in async listener {task.get_coro().__name__}: {e}"
                if metadata:
                    error_msg += f" (Metadata: {metadata})"
                logger.error(error_msg)

    def close(self) -> None:
        """Optional method to shut down the background event loop.

        Not required for existing users, as the loop runs in a daemon thread.
        Useful for explicit resource cleanup when using async listeners.
        """
        self._loop.call_soon_threadsafe(lambda: self._stop_future.set_result(None))
        self._thread.join()

    def on(
        self,
        event: str | list[str],
        listener: Callable[..., Any],
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register an event listener for one or more events with optional priority and metadata.

        If event is a list, the listener is registered for each event in the list.

        Parameters:
        - event (str | list[str]): The event name or a list of event names to listen to.
        - listener (Callable): The function to call when the specified event(s) are emitted.
        - priority (int): Priority level (lower number = higher priority), defaults to 0.
        - metadata (dict, optional): Additional info about the listener for debugging or error handling.
        """
        if isinstance(event, str):
            events = [event]
        elif isinstance(event, list):
            events = event
        else:
            raise TypeError("Event must be a string or a list of strings.")

        with self._lock:
            for evt in events:
                if not evt or (evt != "*" and not isinstance(evt, str)):
                    raise ValueError("Event names must be non-empty strings or '*'")
                listener_tuple = (listener, priority, metadata)
                if evt == "*":
                    if listener_tuple not in self._wildcard_listeners:
                        self._wildcard_listeners.append(listener_tuple)
                else:
                    if evt not in self._listeners:
                        self._listeners[evt] = []
                    if listener_tuple not in self._listeners[evt]:
                        self._listeners[evt].append(listener_tuple)

    def once(
        self,
        event: str | list[str],
        listener: Callable[..., Any],
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a one-time event listener for one or more events with optional priority and metadata.

        The listener is removed after it is invoked the first time the event is emitted.

        Parameters:
        - event (str | list[str]): The event name or a list of event names to listen to.
        - listener (Callable): The function to call once when the specified event(s) are emitted.
        - priority (int): Priority level (lower number = higher priority), defaults to 0.
        - metadata (dict, optional): Additional info about the listener for debugging or error handling.
        """
        if inspect.iscoroutinefunction(listener):

            async def wrapper(*args: Any, **kwargs: Any) -> None:
                self.off(event, wrapper)
                await listener(*args, **kwargs)
        else:

            def wrapper(*args: Any, **kwargs: Any) -> None:
                self.off(event, wrapper)
                listener(*args, **kwargs)

        self.on(event, wrapper, priority, metadata)

    def off(self, event: str | list[str] | None = None, listener: Callable[..., Any] = None) -> None:
        """Unregister an event listener.

        If event is None, removes the listener from all events.

        Parameters:
        - event (str | list[str] | None): The name of the event or a list of event names to stop listening to.
                                           If None, removes the listener from all events.
        - listener (Callable): The function to remove from the event listeners.
        """
        with self._lock:
            if event is None:
                # Remove from all specific events
                for evt_list in self._listeners.values():
                    for listener_tuple in list(evt_list):
                        if listener_tuple[0] == listener:
                            evt_list.remove(listener_tuple)
                # Remove from wildcard listeners
                for listener_tuple in list(self._wildcard_listeners):
                    if listener_tuple[0] == listener:
                        self._wildcard_listeners.remove(listener_tuple)
            else:
                if isinstance(event, str):
                    events = [event]
                elif isinstance(event, list):
                    events = event
                else:
                    raise TypeError("Event must be a string, a list of strings, or None.")

                for evt in events:
                    if not evt or (evt != "*" and not isinstance(evt, str)):
                        raise ValueError("Event names must be non-empty strings or '*'")
                    if evt == "*":
                        for listener_tuple in list(self._wildcard_listeners):
                            if listener_tuple[0] == listener:
                                self._wildcard_listeners.remove(listener_tuple)
                    elif evt in self._listeners:
                        for listener_tuple in list(self._listeners[evt]):
                            if listener_tuple[0] == listener:
                                self._listeners[evt].remove(listener_tuple)

    def emit(
        self, event: str, *args: Any, error_handler: Optional[Callable[[Exception], None]] = None, **kwargs: Any
    ) -> None:
        """Emit an event to all registered listeners with optional error handling.

        First, invokes wildcard listeners, then listeners registered to the specific event, sorted by priority.
        Synchronous listeners are executed immediately, while async listeners are scheduled in the background loop.

        Parameters:
        - event (str): The name of the event to emit.
        - args: Positional arguments to pass to the listeners.
        - error_handler (Callable, optional): Function to handle exceptions from listeners.
        - kwargs: Keyword arguments to pass to the listeners.
        """
        if not event or not isinstance(event, str):
            raise ValueError("Event name must be a non-empty string")

        with self._lock:
            # Copy listeners to avoid modification issues during emission
            listeners = list(self._wildcard_listeners)
            if event in self._listeners:
                listeners.extend(self._listeners[event])
            # Sort by priority (lower number = higher priority)
            listeners.sort(key=lambda x: x[1])

        # Execute listeners outside the lock to prevent deadlocks
        for listener_tuple in listeners:
            listener, _, metadata = listener_tuple
            if inspect.iscoroutinefunction(listener):
                self._loop.call_soon_threadsafe(
                    self._schedule_async_listener,
                    listener,
                    event,
                    args,  # Pass args as a tuple
                    error_handler,
                    metadata,
                    kwargs,
                )
            else:
                try:
                    listener(event, *args, **kwargs)
                except Exception as e:
                    if error_handler:
                        error_handler(e)
                    else:
                        # Default error logging with loguru, including metadata if available
                        error_msg = f"Error in listener {listener.__name__}: {e}"
                        if metadata:
                            error_msg += f" (Metadata: {metadata})"
                        logger.error(error_msg)

    def clear(self, event: str) -> None:
        """Clear all listeners for a specific event.

        Parameters:
        - event (str): The name of the event to clear listeners from.
        """
        if not event or not isinstance(event, str):
            raise ValueError("Event name must be a non-empty string")

        with self._lock:
            if event in self._listeners:
                del self._listeners[event]

    def clear_all(self) -> None:
        """Clear all listeners for all events, including wildcard listeners."""
        with self._lock:
            self._listeners.clear()
            self._wildcard_listeners.clear()

    def listeners(self, event: str) -> list[Callable[..., Any]]:
        """Retrieve all listeners registered for a specific event, including wildcard listeners.

        Parameters:
        - event (str): The name of the event.

        Returns:
        - List of callables registered for the event (without priority or metadata).
        """
        if not event or not isinstance(event, str):
            raise ValueError("Event name must be a non-empty string")

        with self._lock:
            result = [listener_tuple[0] for listener_tuple in self._wildcard_listeners]
            if event in self._listeners:
                result.extend(listener_tuple[0] for listener_tuple in self._listeners[event])
            return result

    def has_listener(self, event: str | None, listener: Callable[..., Any]) -> bool:
        """Check if a specific listener is registered for an event.

        Parameters:
        - event (str | None): The name of the event. If None, checks in wildcard listeners.
        - listener (Callable): The listener to check.

        Returns:
        - True if the listener is registered for the event, False otherwise.
        """
        with self._lock:
            if event is None or event == "*":
                return any(listener_tuple[0] == listener for listener_tuple in self._wildcard_listeners)
            else:
                if not event or not isinstance(event, str):
                    raise ValueError("Event name must be a non-empty string")
                return any(listener_tuple[0] == listener for listener_tuple in self._listeners.get(event, []))

    def listener_count(self, event: str) -> int:
        """Return the number of listeners for a specific event, including wildcard listeners.

        Parameters:
        - event (str): The name of the event.

        Returns:
        - Total count of listeners for the event.
        """
        if not event or not isinstance(event, str):
            raise ValueError("Event name must be a non-empty string")

        with self._lock:
            count = len(self._wildcard_listeners)
            if event in self._listeners:
                count += len(self._listeners[event])
            return count

    def debug_info(self) -> Dict[str, Any]:
        """Return a dictionary with the current state of the emitter for debugging purposes.

        Returns:
        - Dict containing wildcard listeners and event-specific listeners.
        """
        with self._lock:
            return {
                "wildcard_listeners": [(l.__name__, p, m) for l, p, m in self._wildcard_listeners],
                "event_listeners": {
                    evt: [(l.__name__, p, m) for l, p, m in listeners] for evt, listeners in self._listeners.items()
                },
            }


if __name__ == "__main__":
    import asyncio

    # Synchronous listener
    def on_data_received(event: str, data: Any):
        print(f"[Sync] Data received: {data}")

    # Asynchronous listener
    async def on_data_async(event: str, data: Any):
        print(f"[Async] Starting async processing for data: {data}")
        await asyncio.sleep(1)
        print(f"[Async] Finished async processing for data: {data}")

    def on_any_event(event: str, data: Any):
        print(f"[Sync] Event '{event}' emitted with data: {data}")

    def custom_error_handler(exc: Exception):
        print(f"Custom error handler caught: {exc}")

    emitter = EventEmitter()

    # Register specific event listeners
    emitter.on("data", on_data_received, priority=1)
    emitter.on("data", on_data_async, priority=2, metadata={"id": "async_listener"})

    # Register wildcard listener
    emitter.on("*", on_any_event, priority=0)

    # Emit 'data' event
    print("Emitting 'data' event...")
    emitter.emit("data", "Sample Data")
    print("Emit completed. Note: Async listeners may still be running.")

    # Wait briefly to see async output
    import time

    time.sleep(2)

    # Register a one-time async listener
    async def once_async_listener(event: str, data: Any):
        print(f"[Async Once] Received: {data}")
        await asyncio.sleep(1)
        print(f"[Async Once] Processed: {data}")

    emitter.once("data", once_async_listener, priority=2, metadata={"id": "once_async"})
    print("Emitting 'data' for once listener...")
    emitter.emit("data", "Once Async Data")
    time.sleep(2)

    # Test error handling with async listener
    async def error_async_listener(event: str, data: Any):
        raise ValueError("Test async error")

    emitter.on("data", error_async_listener, metadata={"id": "error_async"})
    print("Emitting 'data' with error...")
    emitter.emit("data", "Error Data", error_handler=custom_error_handler)
    time.sleep(1)

    # Clean up (optional)
    emitter.close()
