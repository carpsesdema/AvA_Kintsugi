# kintsugi_ava/core/application.py
# V10: Graceful task cancellation and streamlined event handling.

import asyncio
from .event_bus import EventBus
from .llm_client import LLMClient
from gui.main_window import MainWindow
from gui.code_viewer import CodeViewerWindow
from gui.workflow_monitor_window import WorkflowMonitorWindow
from gui.terminals import TerminalsWindow
from gui.model_config_dialog import ModelConfigurationDialog
from services.architect_service import ArchitectService


class Application:
    """
    The main application object. It creates, owns, and orchestrates
    all major UI components and services, now with graceful task management.
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.conversation_history = []
        # --- Task Management ---
        # A set to keep track of all running background tasks (like AI generation)
        self.background_tasks = set()

        # --- Service Management ---
        self.llm_client = LLMClient()
        self.architect_service = ArchitectService(self.event_bus, self.llm_client)

        # --- Window Management ---
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow()
        self.workflow_monitor = WorkflowMonitorWindow()
        self.terminals_window = TerminalsWindow()
        self.model_config_dialog = ModelConfigurationDialog(self.llm_client)

        self._connect_events()

    def _connect_events(self):
        self.event_bus.subscribe("user_request_submitted", self.on_user_request)
        self.event_bus.subscribe("new_session_requested", self.clear_session)

        # Window management events
        self.event_bus.subscribe("show_code_viewer_requested", self.show_code_viewer)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.show_workflow_monitor)
        self.event_bus.subscribe("show_terminals_requested", self.show_terminals)
        self.event_bus.subscribe("configure_models_requested", self.model_config_dialog.exec)

        # AI workflow events
        self.event_bus.subscribe("code_generation_complete", self.code_viewer.display_code)

        # --- THIS IS THE FIX for the double response ---
        # The ArchitectService now sends the final "I'm done" message.
        # The ChatInterface should ONLY listen for this single source of truth.
        self.event_bus.subscribe("ai_response_ready", self.main_window.chat_interface._add_ai_response)
        # We no longer need the duplicate subscription here.

        self.event_bus.subscribe("log_message_received", self.terminals_window.add_log_message)

    def on_user_request(self, prompt: str, history: list):
        print(f"[Application] Heard 'user_request_submitted'. Creating background task.")
        self.conversation_history = history

        # --- Graceful Task Creation ---
        task = asyncio.create_task(self.architect_service.create_project(prompt))
        # Add the task to our tracking set
        self.background_tasks.add(task)
        # When the task is done, remove it from the set
        task.add_done_callback(self.background_tasks.discard)

    def cancel_all_tasks(self):
        """Cancels all running background tasks."""
        print(f"[Application] Cancelling {len(self.background_tasks)} background tasks.")
        for task in self.background_tasks:
            task.cancel()

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