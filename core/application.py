# kintsugi_ava/core/application.py
# V5: Now integrates a placeholder AI service.

from .event_bus import EventBus
from gui.main_window import MainWindow
from gui.code_viewer import CodeViewerWindow
from gui.workflow_monitor_window import WorkflowMonitorWindow
from gui.terminals import TerminalsWindow
from services.coder_service import CoderService  # <-- Import the service


class Application:
    """
    The main application object. It creates, owns, and orchestrates
    all major UI components and services.
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.conversation_history = []

        # --- Service Management ---
        # The application creates and owns the services.
        self.coder_service = CoderService(self.event_bus)

        # --- Window Management ---
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow()
        self.workflow_monitor = WorkflowMonitorWindow()
        self.terminals_window = TerminalsWindow()

        self._connect_events()

    def _connect_events(self):
        """Central place to connect application logic to events from the UI."""
        self.event_bus.subscribe("user_request_submitted", self.handle_user_request)
        self.event_bus.subscribe("new_session_requested", self.clear_session)

        # Connect UI components to events
        self.event_bus.subscribe("show_code_viewer_requested", self.show_code_viewer)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.show_workflow_monitor)
        self.event_bus.subscribe("show_terminals_requested", self.show_terminals)

        # The Code Viewer now listens for the result from the CoderService
        self.event_bus.subscribe("code_generation_complete", self.code_viewer.display_code)

    def handle_user_request(self, prompt: str, history: list):
        """
        This is the main entry point for the AI workflow.
        It now calls our placeholder service.
        """
        print(f"[Application] Heard 'user_request_submitted'. Delegating to CoderService.")
        self.conversation_history = history

        # --- This is the full workflow in action! ---
        # Application tells the service to do its job.
        self.coder_service.generate_code(prompt)

    def show_window(self, window):
        if not window.isVisible():
            window.show()
        else:
            window.activateWindow()

    def show_code_viewer(self):
        self.show_window(self.code_viewer)

    def show_workflow_monitor(self):
        self.show_window(self.workflow_monitor)

    def show_terminals(self):
        self.show_window(self.terminals_window)

    def clear_session(self):
        print("[Application] Heard 'new_session_requested', clearing internal state.")
        self.conversation_history = []

    def show(self):
        self.main_window.show()