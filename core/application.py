# kintsugi_ava/core/application.py
# V12: Implements intelligent request routing (Command vs. Chat).

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
    The main application object. It now intelligently routes user requests
    to either the project generator or a simple chat handler.
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.background_tasks = set()
        self.llm_client = LLMClient()
        self.architect_service = ArchitectService(self.event_bus, self.llm_client)
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow()
        self.workflow_monitor = WorkflowMonitorWindow()
        self.terminals_window = TerminalsWindow()
        self.model_config_dialog = ModelConfigurationDialog(self.llm_client)
        self._connect_events()

        # Keywords that trigger the project generation workflow.
        self.COMMAND_KEYWORDS = ["make", "create", "build", "generate", "write", "develop"]

    def _connect_events(self):
        self.event_bus.subscribe("user_request_submitted", self.on_user_request)
        self.event_bus.subscribe("new_session_requested", self.clear_session)
        self.event_bus.subscribe("show_code_viewer_requested", self.show_code_viewer)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.show_workflow_monitor)
        self.event_bus.subscribe("show_terminals_requested", self.show_terminals)
        self.event_bus.subscribe("configure_models_requested", self.model_config_dialog.exec)
        self.event_bus.subscribe("code_generation_complete", self.code_viewer.display_code)
        self.event_bus.subscribe("ai_response_ready", self.main_window.chat_interface._add_ai_response)
        self.event_bus.subscribe("node_status_changed", self.workflow_monitor.update_node_status)

    def on_user_request(self, prompt: str, history: list):
        """
        Intelligently routes the user's request.
        """
        if self._is_command(prompt):
            # This is a request to build something, use the ArchitectService.
            print("[Application] Command detected. Routing to ArchitectService.")
            self.workflow_monitor.scene.setup_layout()
            task = asyncio.create_task(self.architect_service.create_project(prompt))
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)
        else:
            # This is a conversational message, handle it with a simple chat call.
            print("[Application] Chat message detected. Routing to simple chat handler.")
            task = asyncio.create_task(self.handle_chat_message(prompt))
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

    def _is_command(self, prompt: str) -> bool:
        """Determines if a prompt is a command or a chat message."""
        first_word = prompt.strip().lower().split()[0]
        return first_word in self.COMMAND_KEYWORDS

    async def handle_chat_message(self, prompt: str):
        """
        Handles a simple conversational message by calling the 'chat' model.
        """
        provider, model = self.llm_client.get_model_for_role("chat")
        if not provider or not model:
            self.event_bus.emit("ai_response_ready", "Sorry, no model is configured for the Chat role.")
            return

        full_response = ""
        async for chunk in self.llm_client.stream_chat(provider, model, prompt):
            full_response += chunk

        self.event_bus.emit("ai_response_ready", full_response)

    async def cancel_all_tasks(self):
        if not self.background_tasks: return
        print(f"[Application] Cancelling {len(self.background_tasks)} background tasks.")
        tasks_to_cancel = list(self.background_tasks)
        for task in tasks_to_cancel:
            task.cancel()
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        print("[Application] All background tasks have been cancelled.")

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
        self.event_bus.emit("ai_response_ready", "New session started. How can I help?")

    def show(self):
        self.main_window.show()