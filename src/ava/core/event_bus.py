# src/ava/core/event_bus.py
import asyncio
import inspect
from collections import defaultdict


class EventBus:
    """A simple, in-process event bus for decoupling components, now with async support."""

    def __init__(self):
        self._subscribers = defaultdict(list)

    def subscribe(self, event_name: str, callback):
        print(f"[EventBus] Subscribing '{getattr(callback, '__name__', 'lambda')}' to event '{event_name}'")
        self._subscribers[event_name].append(callback)

    def emit(self, event_name: str, *args, **kwargs):
        """
        Emits an event, calling all subscribed callbacks with the given arguments.
        Correctly handles both synchronous and asynchronous (coroutine) callbacks.
        """
        print(f"[EventBus] Emitting event '{event_name}'")

        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                try:
                    if inspect.iscoroutinefunction(callback):
                        # If the callback is an async def function, schedule it on the event loop
                        asyncio.create_task(callback(*args, **kwargs))
                    else:
                        # Otherwise, call it synchronously
                        callback(*args, **kwargs)
                except Exception as e:
                    import traceback
                    print(f"[EventBus] Error in callback for event '{event_name}': {e}")
                    traceback.print_exc()