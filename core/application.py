# kintsugi_ava/core/application.py
# V17: Fixes a typo in the RAG service injection.

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
from services.project_analyzer import ProjectAnalyzer
from services.rag_manager import RAGManager


class Application:
    """
    The main application object. It acts as the lead engineer, orchestrating
    all components and services to fulfill user requests for creation or
    modification of projects.
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.background_tasks = set()

        # --- Initialize all components and services ---
        self.project_manager = ProjectManager()
        self.llm_client = LLMClient()
        self.project_analyzer = ProjectAnalyzer()
        self.rag_manager = RAGManager(self.event_bus)
        # --- THE FIX IS HERE ---
        self.architect_service = ArchitectService(self.event_bus, self.llm_client, self.project_manager,
                                                  self.rag_manager.rag_service)
        # --- END OF FIX ---

        # --- Window Management ---
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow()
        self.workflow_monitor = WorkflowMonitorWindow()
        self.terminals_window = TerminalsWindow()
        self.model_config_dialog = ModelConfigurationDialog(self.llm_client)

        self._connect_events()

        # Start non-blocking initialization of services that need it
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

        # Logging & Monitoring Events
        self.event_bus.subscribe("log_message_received", self.terminals_window.add_log_message)
        self.event_bus.subscribe("node_status_changed", self.workflow_monitor.update_node_status)

    def on_user_request(self, prompt: str, history: list):
        """
        The main router. It checks if a project is loaded and decides
        whether to create a new one or modify the existing one.
        """
        self.workflow_monitor.scene.setup_layout()

        existing_files_context = None
        if self.project_manager.is_existing_project:
            print("[Application] Active project is an existing one. Analyzing files for context...")
            existing_files_context = self.project_analyzer.analyze(str(self.project_manager.active_project_path))

        # Create a background task for the AI workflow
        task = asyncio.create_task(self.architect_service.generate_or_modify(prompt, existing_files_context))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def on_new_project(self):
        """Handles the 'New Project' button click."""
        new_path_str = self.project_manager.new_project()
        self.event_bus.emit("project_loaded", new_path_str)
        self.event_bus.emit("ai_response_ready", f"New empty project created. Ready for your instructions.")

    def on_load_project(self):
        """Handles the 'Load Project' button click, opening a file dialog."""
        directory = QFileDialog.getExistingDirectory(self.main_window, "Select Project Folder")
        if directory:
            loaded_path_str = self.project_manager.load_project(directory)
            if loaded_path_str:
                self.event_bus.emit("project_loaded", loaded_path_str)

    def on_project_loaded(self, path_str: str):
        """Updates the UI after a project is created or loaded."""
        project_path = Path(path_str)
        display_name = self.project_manager.active_project_name
        self.main_window.sidebar.update_project_display(display_name)
        self.code_viewer.load_project(path_str)
        self.event_bus.emit("ai_response_ready", f"Project '{display_name}' is now active and ready for modifications.")

    def on_scan_directory_requested(self):
        """Handles the request to scan a directory for the RAG knowledge base."""
        self.rag_manager.open_scan_directory_dialog(self.main_window)

    async def cancel_all_tasks(self):
        """Gracefully cancels all running background tasks on shutdown."""
        if not self.background_tasks:
            return
        tasks_to_cancel = list(self.background_tasks)
        for task in tasks_to_cancel:
            task.cancel()
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    def show_window(self, window):
        """Helper to show a window and bring it to the front."""
        if not window.isVisible():
            window.show()
        else:
            window.activateWindow()

    def clear_session(self):
        """Resets the chat interface for a new conversation."""
        self.event_bus.emit("ai_response_ready", "New session started.")

    def show(self):
        """Shows the main application window."""
        self.main_window.show()