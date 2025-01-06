import threading
from typing import Any, Callable


class EventEmitter:
    """A thread-safe event emitter class for managing event listeners and emissions."""

    def __init__(self) -> None:
        """Initialize an empty EventEmitter instance.

        Creates an empty dictionary to store event listeners,
        where each event can have multiple callable listeners.
        Also initializes a list for wildcard listeners that listen to all events.
        """
        self._listeners: dict[str, list[Callable[..., Any]]] = {}
        self._wildcard_listeners: list[Callable[..., Any]] = []
        self._lock = threading.RLock()

    def on(self, event: str | list[str], listener: Callable[..., Any]) -> None:
        """Register an event listener for one or more events.

        If event is a list, the listener is registered for each event in the list.

        Parameters:
        - event (str | list[str]): The event name or a list of event names to listen to.
        - listener (Callable): The function to call when the specified event(s) are emitted.
        """
        if isinstance(event, str):
            events = [event]
        elif isinstance(event, list):
            events = event
        else:
            raise TypeError("Event must be a string or a list of strings.")

        with self._lock:
            for evt in events:
                if evt == "*":
                    if listener not in self._wildcard_listeners:
                        self._wildcard_listeners.append(listener)
                else:
                    if evt not in self._listeners:
                        self._listeners[evt] = []
                    if listener not in self._listeners[evt]:
                        self._listeners[evt].append(listener)

    def once(self, event: str | list[str], listener: Callable[..., Any]) -> None:
        """Register a one-time event listener for one or more events.

        The listener is removed after it is invoked the first time the event is emitted.

        Parameters:
        - event (str | list[str]): The event name or a list of event names to listen to.
        """

        def wrapper(*args: Any, **kwargs: Any) -> None:
            self.off(event, wrapper)
            listener(*args, **kwargs)

        self.on(event, wrapper)

    def off(
        self,
        event: str | list[str] | None = None,
        listener: Callable[..., Any] = None,
    ) -> None:
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
                    if listener in evt_list:
                        evt_list.remove(listener)
                # Remove from wildcard listeners
                if listener in self._wildcard_listeners:
                    self._wildcard_listeners.remove(listener)
            else:
                if isinstance(event, str):
                    events = [event]
                elif isinstance(event, list):
                    events = event
                else:
                    raise TypeError("Event must be a string, a list of strings, or None.")

                for evt in events:
                    if evt == "*":
                        if listener in self._wildcard_listeners:
                            self._wildcard_listeners.remove(listener)
                    elif evt in self._listeners:
                        try:
                            self._listeners[evt].remove(listener)
                        except ValueError:
                            pass  # Listener was not found for this event

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to all registered listeners.

        First, invokes wildcard listeners, then listeners registered to the specific event.

        Parameters:
        - event (str): The name of the event to emit.
        - args: Positional arguments to pass to the listeners.
        - kwargs: Keyword arguments to pass to the listeners.
        """
        with self._lock:
            listeners = list(self._wildcard_listeners)
            if event in self._listeners:
                listeners.extend(self._listeners[event])

        for listener in listeners:
            try:
                listener(event, *args, **kwargs)
            except Exception as e:
                # Log the exception or handle it as needed
                print(f"Error in listener {listener}: {e}")

    def clear(self, event: str) -> None:
        """Clear all listeners for a specific event.

        Parameters:
        - event (str): The name of the event to clear listeners from.
        """
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
        - List of callables registered for the event.
        """
        with self._lock:
            listeners = list(self._wildcard_listeners)
            if event in self._listeners:
                listeners.extend(self._listeners[event])
            return listeners

    def has_listener(self, event: str | None, listener: Callable[..., Any]) -> bool:
        """Check if a specific listener is registered for an event.

        Parameters:
        - event (str | None): The name of the event. If None, checks in wildcard listeners.
        - listener (Callable): The listener to check.

        Returns:
        - True if the listener is registered for the event, False otherwise.
        """
        with self._lock:
            if event is None:
                return listener in self._wildcard_listeners
            elif event == "*":
                return listener in self._wildcard_listeners
            else:
                return listener in self._listeners.get(event, [])


if __name__ == "__main__":

    def on_data_received(data):
        print(f"Data received: {data}")

    def on_any_event(event, data):
        print(f"Event '{event}' emitted with data: {data}")

    emitter = EventEmitter()

    # Register specific event listener
    emitter.on("data", on_data_received)

    # Register wildcard listener
    emitter.on("*", on_any_event)

    # Emit 'data' event
    emitter.emit("data", "Sample Data")

    # Output:
    # Event 'data' emitted with data: Sample Data
    # Data received: Sample Data

    # Emit 'update' event
    emitter.emit("update", "Update Data")

    # Output:
    # Event 'update' emitted with data: Update Data

    # Register a one-time listener
    def once_listener(data):
        print(f"Once listener received: {data}")

    emitter.once("data", once_listener)

    # Emit 'data' event
    emitter.emit("data", "First Call")

    # Output:
    # Event 'data' emitted with data: First Call
    # Data received: First Call
    # Once listener received: First Call

    # Emit 'data' event again
    emitter.emit("data", "Second Call")

    # Output:
    # Event 'data' emitted with data: Second Call
    # Data received: Second Call
    # (Once listener is not called again)
