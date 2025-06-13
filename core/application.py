# kintsugi_ava/core/application.py
# The central application class that owns and manages all major components.

from .event_bus import EventBus
from gui.main_window import MainWindow

class Application:
    """
    The main application object. It doesn't handle UI itself,
    but it creates, owns, and orchestrates the UI and services.
    """
    def __init__(self):
        # 1. The application owns the event bus.
        self.event_bus = EventBus()

        # 2. The application owns the main window.
        #    We pass the event bus to the window so it can be passed down
        #    to all child components. This is called "dependency injection".
        self.main_window = MainWindow(self.event_bus)

    def show(self):
        """A simple method to show the main window."""
        self.main_window.show()