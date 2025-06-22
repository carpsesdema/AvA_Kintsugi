from collections import defaultdict

class EventBus:
    """A simple, synchronous, in-process event bus for decoupling components."""

    def __init__(self):
        """Initializes a dictionary to hold subscribers for each event."""
        self._subscribers = defaultdict(list)

    def subscribe(self, event_name: str, callback):
        """
        Subscribes a function (callback) to an event.
        When the event is emitted, this function will be called.
        """
        print(f"[EventBus] Subscribing '{callback.__name__}' to event '{event_name}'")
        self._subscribers[event_name].append(callback)

    def emit(self, event_name: str, *args, **kwargs):
        """
        Emits an event, calling all subscribed callbacks with the given arguments.
        """
        print(f"[EventBus] Emitting event '{event_name}'")
        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"[EventBus] Error in callback for event '{event_name}': {e}")