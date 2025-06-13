# kintsugi_ava/core/application.py
# V7: Manages the model configuration dialog.

import asyncio
from .event_bus import EventBus
from .llm_client import LLMClient
from gui.main_window import MainWindow
from gui.code_viewer import CodeViewerWindow
from gui.workflow_monitor_window import WorkflowMonitorWindow
from gui.terminals import TerminalsWindow
from gui.model_config_dialog import ModelConfigurationDialog  # <-- Import dialog
from services.coder_service import CoderService


class Application:
    """
    The main application object. It creates, owns, and orchestrates
    all major UI components and services.
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.conversation_history = []

        self.llm_client = LLMClient()
        self.coder_service = CoderService(self.event_bus, self.llm_client)

        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow()
        self.workflow_monitor = WorkflowMonitorWindow()
        self.terminals_window = TerminalsWindow()
        # Create the dialog but don't show it yet
        self.model_config_dialog = ModelConfigurationDialog(self.llm_client)

        self._connect_events()

    def _connect_events(self):
        self.event_bus.subscribe("user_request_submitted", self.on_user_request)
        self.event_bus.subscribe("new_session_requested", self.clear_session)

        self.event_bus.subscribe("show_code_viewer_requested", self.show_code_viewer)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.show_workflow_monitor)
        self.event_bus.subscribe("show_terminals_requested", self.show_terminals)
        # New event for showing the config dialog
        self.event_bus.subscribe("configure_models_requested", self.model_config_dialog.exec)

        self.event_bus.subscribe("code_generation_complete", self.code_viewer.display_code)
        self.event_bus.subscribe("ai_response_ready", self.main_window.chat_interface._add_ai_response)

    def on_user_request(self, prompt: str, history: list):
        print(f"[Application] Heard 'user_request_submitted'. Creating background task.")
        self.conversation_history = history
        asyncio.create_task(self.coder_service.generate_code(prompt))

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
        self.event_bus.emit("ai_response_ready", "New session started. How can I help?")

    def show(self):
        self.main_window.show()