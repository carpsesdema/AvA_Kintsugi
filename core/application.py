# kintsugi_ava/core/application.py
# V14: Integrates the ProjectManager for full project lifecycle support.

import asyncio
from pathlib import Path
from PySide6.QtWidgets import QFileDialog

from .event_bus import EventBus
from .llm_client import LLMClient
from .project_manager import ProjectManager
from gui.main_window import MainWindow
from gui.code_viewer import CodeViewerWindow
from gui.workflow_monitor_window import WorkflowMonitorWindow
from gui.terminals import TerminalsWindow
from gui.model_config_dialog import ModelConfigurationDialog
from services.architect_service import ArchitectService
from services.reviewer_service import ReviewerService


class Application:
    def __init__(self):
        self.event_bus = EventBus()
        self.background_tasks = set()

        self.llm_client = LLMClient()
        self.project_manager = ProjectManager()
        self.architect_service = ArchitectService(self.event_bus, self.llm_client, self.project_manager)

        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow()
        self.workflow_monitor = WorkflowMonitorWindow()
        self.terminals_window = TerminalsWindow()
        self.model_config_dialog = ModelConfigurationDialog(self.llm_client)

        self._connect_events()

    def _connect_events(self):
        # User Actions
        self.event_bus.subscribe("user_request_submitted", self.on_user_request)
        self.event_bus.subscribe("new_session_requested", self.clear_session)
        self.event_bus.subscribe("new_project_requested", self.on_new_project)
        self.event_bus.subscribe("load_project_requested", self.on_load_project)

        # Window Management
        self.event_bus.subscribe("show_code_viewer_requested", self.show_code_viewer)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.show_workflow_monitor)
        self.event_bus.subscribe("show_terminals_requested", self.show_terminals)
        self.event_bus.subscribe("configure_models_requested", self.model_config_dialog.exec)

        # AI Workflow
        self.event_bus.subscribe("prepare_for_generation", self.code_viewer.prepare_for_generation)
        self.event_bus.subscribe("stream_code_chunk", self.code_viewer.stream_code_chunk)
        self.event_bus.subscribe("code_generation_complete", self.code_viewer.display_code)
        self.event_bus.subscribe("ai_response_ready", self.main_window.chat_interface._add_ai_response)

        # Logging & Monitoring
        self.event_bus.subscribe("log_message_received", self.terminals_window.add_log_message)
        self.event_bus.subscribe("node_status_changed", self.workflow_monitor.update_node_status)

        # Project Lifecycle
        self.event_bus.subscribe("project_created", self.on_project_loaded)
        self.event_bus.subscribe("project_loaded", self.on_project_loaded)

    def on_user_request(self, prompt: str, history: list):
        self.workflow_monitor.scene.setup_layout()
        task = asyncio.create_task(self.architect_service.create_project(prompt))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def on_new_project(self):
        # This will be triggered by the sidebar button
        self.project_manager.create_new_project()
        self.event_bus.emit("project_created", str(self.project_manager.current_project_path))

    def on_load_project(self):
        # Uses a native file dialog to select a folder
        directory = QFileDialog.getExistingDirectory(self.main_window, "Select Project Folder")
        if directory:
            loaded_path = self.project_manager.load_project(directory)
            if loaded_path:
                self.event_bus.emit("project_loaded", str(loaded_path))

    def on_project_loaded(self, path_str: str):
        """Updates the UI when a project is created or loaded."""
        project_path = Path(path_str)
        self.main_window.sidebar.update_project_display(project_path.name)
        # We can also load the files into the code viewer automatically
        self.code_viewer.load_project(str(project_path))

    async def cancel_all_tasks(self):
        if not self.background_tasks: return
        tasks_to_cancel = list(self.background_tasks)
        for task in tasks_to_cancel: task.cancel()
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

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