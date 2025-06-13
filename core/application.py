# kintsugi_ava/core/application.py
# V22: Integrates TerminalService to power the IDE's command center.

import asyncio
from pathlib import Path
from PySide6.QtWidgets import QFileDialog

from .event_bus import EventBus
from .llm_client import LLMClient
from .project_manager import ProjectManager
from core.execution_engine import ExecutionEngine  # Import ExecutionEngine
from gui.main_window import MainWindow
from gui.code_viewer import CodeViewerWindow
from gui.workflow_monitor_window import WorkflowMonitorWindow
from gui.terminals import TerminalsWindow
from gui.model_config_dialog import ModelConfigurationDialog
from services.architect_service import ArchitectService
from services.project_analyzer import ProjectAnalyzer
from services.rag_manager import RAGManager
from services.terminal_service import TerminalService  # Import TerminalService


class Application:
    """
    The main application object. It acts as the lead engineer, orchestrating
    all components and services, including the new integrated terminal.
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.background_tasks = set()

        # --- Initialize all components and services ---
        self.project_manager = ProjectManager()
        self.llm_client = LLMClient()
        self.project_analyzer = ProjectAnalyzer()
        self.execution_engine = ExecutionEngine(self.project_manager)
        self.rag_manager = RAGManager(self.event_bus)
        self.terminal_service = TerminalService(self.event_bus, self.project_manager, self.execution_engine)
        self.architect_service = ArchitectService(self.event_bus, self.llm_client, self.project_manager,
                                                  self.rag_manager.rag_service)

        # --- Window Management ---
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow(self.event_bus)
        self.workflow_monitor = WorkflowMonitorWindow()
        self.terminals_window = TerminalsWindow()
        self.model_config_dialog = ModelConfigurationDialog(self.llm_client)

        self._connect_events()
        self.rag_manager.start_async_initialization()

    def _connect_events(self):
        # User Actions from the UI
        self.event_bus.subscribe("user_request_submitted", self.on_user_request)
        self.event_bus.subscribe("new_project_requested", self.on_new_project)
        self.event_bus.subscribe("load_project_requested", self.on_load_project)
        self.event_bus.subscribe("new_session_requested", self.clear_session)

        # Window Management Events
        self.event_bus.subscribe("show_code_viewer_requested", lambda: self.show_window(self.code_viewer))
        self.event_bus.subscribe("show_workflow_monitor_requested", lambda: self.show_window(self.workflow_monitor))
        self.event_bus.subscribe("show_terminals_requested", lambda: self.show_window(self.terminals_window))
        self.event_bus.subscribe("configure_models_requested", self.model_config_dialog.exec)

        # AI Workflow & UI Update Events
        self.event_bus.subscribe("prepare_for_generation", self.code_viewer.prepare_for_generation)
        self.event_bus.subscribe("stream_code_chunk", self.code_viewer.stream_code_chunk)
        self.event_bus.subscribe("code_generation_complete", self.code_viewer.display_code)
        self.event_bus.subscribe("ai_response_ready", self.main_window.chat_interface._add_ai_response)

        # Project Lifecycle Events
        self.event_bus.subscribe("project_loaded", self.on_project_loaded)

        # RAG Events
        self.event_bus.subscribe("scan_directory_requested", self.on_scan_directory_requested)
        self.event_bus.subscribe("add_active_project_to_rag_requested", self.on_add_active_project_to_rag)

        # Terminal Events
        self.event_bus.subscribe("terminal_command_entered", self.on_terminal_command)

        # Logging & Monitoring Events
        self.event_bus.subscribe("log_message_received", self.terminals_window.add_log_message)
        self.event_bus.subscribe("node_status_changed", self.workflow_monitor.update_node_status)

    def on_terminal_command(self, command: str):
        """Handles commands from the integrated terminal and executes them."""
        task = asyncio.create_task(self.terminal_service.execute_command(command))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def on_user_request(self, prompt: str, history: list):
        self.workflow_monitor.scene.setup_layout()
        existing_files_context = None

        if self.project_manager.is_existing_project:
            self.event_bus.emit("log_message_received", "Application", "info",
                                "Existing project detected. Beginning sandboxed modification session.")
            branch_name = self.project_manager.begin_modification_session()
            if not branch_name:
                self.event_bus.emit("log_message_received", "Application", "error", "Failed to create sandbox branch.")
                self.event_bus.emit("ai_response_ready", "I couldn't create a safe sandbox branch.")
                return

            self.event_bus.emit("ai_response_ready", f"Working on your request in safe sandbox branch: {branch_name}")
            existing_files_context = self.project_manager.get_project_files()
        else:
            existing_files_context = None

        task = asyncio.create_task(self.architect_service.generate_or_modify(prompt, existing_files_context))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def on_new_project(self):
        new_path_str = self.project_manager.new_project()
        self.event_bus.emit("project_loaded", new_path_str)
        self.event_bus.emit("ai_response_ready", "New empty project created. Ready for your instructions.")

    def on_load_project(self):
        directory = QFileDialog.getExistingDirectory(self.main_window, "Select Project Folder")
        if directory:
            loaded_path_str = self.project_manager.load_project(directory)
            if loaded_path_str:
                self.event_bus.emit("project_loaded", loaded_path_str)

    def on_project_loaded(self, path_str: str):
        display_name = self.project_manager.active_project_name
        self.main_window.sidebar.update_project_display(display_name)
        self.code_viewer.load_project(path_str)
        self.event_bus.emit("ai_response_ready", f"Project '{display_name}' is now active. Changes will be sandboxed.")

    def on_scan_directory_requested(self):
        self.rag_manager.open_scan_directory_dialog(self.main_window)

    def on_add_active_project_to_rag(self):
        self.rag_manager.ingest_active_project(self.project_manager, self.main_window)

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

    def clear_session(self):
        self.event_bus.emit("ai_response_ready", "New session started.")

    def show(self):
        self.main_window.show()