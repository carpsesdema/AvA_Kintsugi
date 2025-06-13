# kintsugi_ava/core/application.py
# The central application class that owns and manages all major components.
# V2: Now handles events and manages state.

from .event_bus import EventBus
from gui.main_window import MainWindow

class Application:
    """
    The main application object. It doesn't handle UI itself,
    but it creates, owns, and orchestrates the UI and services.
    It listens for events and manages the application state.
    """
    def __init__(self):
        # 1. The application owns the event bus.
        self.event_bus = EventBus()

        # 2. The application owns the main window.
        self.main_window = MainWindow(self.event_bus)

        # 3. The application manages the state.
        self.conversation_history = []

        # 4. Connect application logic to events.
        self._connect_events()

    def _connect_events(self):
        """Central place to connect application logic to events from the UI."""
        self.event_bus.subscribe("user_request_submitted", self.handle_user_request)
        # We also listen for the "new session" event to clear our own state
        self.event_bus.subscribe("new_session_requested", self.clear_session)

    def handle_user_request(self, prompt: str, history: list):
        """
        This is the main entry point for the AI workflow.
        It's called when the user submits a request.
        """
        print(f"[Application] Heard 'user_request_submitted' with prompt: '{prompt}'")
        self.conversation_history = history

        # --- PHASE 2 LOGIC WILL GO HERE ---
        # In the future, this method will:
        # 1. Create a CoderService.
        # 2. Pass it the prompt.
        # 3. Get the code back.
        # 4. Emit an "ai_response_ready" event with the code.
        #
        # For now, we'll just log it. The UI is already simulating the response.
        pass

    def clear_session(self):
        """Handles the 'new_session_requested' event by clearing state."""
        print("[Application] Heard 'new_session_requested', clearing internal state.")
        self.conversation_history = []

    def show(self):
        """A simple method to show the main window."""
        self.main_window.show()