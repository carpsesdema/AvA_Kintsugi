# kintsugi_ava/core/application.py
# The central orchestrator for the Kintsugi AvA application.
# This class instantiates all services and GUI components and connects them via the event bus.

import asyncio
from PySide6.QtWidgets import QFileDialog, QMessageBox

# GUI Imports
from gui.main_window import MainWindow
from gui.code_viewer import CodeViewerWindow
from gui.workflow_monitor_window import WorkflowMonitorWindow
from gui.model_config_dialog import ModelConfigurationDialog
from gui.terminals import TerminalsWindow

# Core Imports
from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.project_manager import ProjectManager
from core.execution_engine import ExecutionEngine

# Service Imports
from services.architect_service import ArchitectService
from services.rag_manager import RAGManager
from services.terminal_service import TerminalService


class Application:
    """The main application class, orchestrating all components."""

    def __init__(self):
        # --- Central Communication ---
        self.event_bus = EventBus()

        # --- Core Components ---
        self.llm_client = LLMClient()
        self.project_manager = ProjectManager()
        self.execution_engine = ExecutionEngine(self.project_manager)

        # --- GUI Windows ---
        self.main_window = MainWindow(self.event_bus)
        self.code_viewer = CodeViewerWindow(self.event_bus)
        self.workflow_monitor = WorkflowMonitorWindow()
        self.terminals = TerminalsWindow()
        self.model_config_dialog = ModelConfigurationDialog(self.llm_client, self.main_window)

        # --- Services ---
        # The RAGManager orchestrates scanning and ingestion, and owns the core RAGService
        self.rag_manager = RAGManager(self.event_bus)

        # The ArchitectService handles the main AI logic loop
        self.architect_service = ArchitectService(
            self.event_bus,
            self.llm_client,
            self.project_manager,
            self.rag_manager.rag_service  # Pass the actual RAG service instance
        )

        # The TerminalService handles commands from the integrated terminal
        self.terminal_service = TerminalService(
            self.event_bus,
            self.project_manager,
            self.execution_engine,
            self.code_viewer
        )

        # --- Task Tracking ---
        # Keep track of long-running background tasks
        self.ai_task = None
        self.terminal_task = None

        # --- Connect Events ---
        self._connect_events()
        print("[Application] Core components initialized and events connected.")

    def _connect_events(self):
        """Subscribe handlers to events on the central event bus."""

        # --- User Actions from GUI ---
        self.event_bus.subscribe("user_request_submitted", self._handle_user_request)
        self.event_bus.subscribe("new_project_requested", self._handle_new_project)
        self.event_bus.subscribe("load_project_requested", self._handle_load_project)
        self.event_bus.subscribe("configure_models_requested", self.model_config_dialog.exec)
        self.event_bus.subscribe("scan_directory_requested", self.rag_manager.open_scan_directory_dialog)
        self.event_bus.subscribe("add_active_project_to_rag_requested", self._handle_add_project_to_rag)
        self.event_bus.subscribe("terminal_command_entered", self._handle_terminal_command)
        self.event_bus.subscribe("new_session_requested", self._handle_new_session)

        # --- Window Visibility ---
        self.event_bus.subscribe("show_code_viewer_requested", self.code_viewer.show_window)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.workflow_monitor.show)
        self.event_bus.subscribe("show_terminals_requested", self.terminals.show)

        # --- AI & System Feedback to GUI ---
        self.event_bus.subscribe("ai_response_ready", self.main_window.chat_interface._add_ai_response)
        self.event_bus.subscribe("log_message_received", self.terminals.add_log_message)
        self.event_bus.subscribe("node_status_changed", self.workflow_monitor.update_node_status)
        self.event_bus.subscribe("branch_updated", self.code_viewer.statusBar().on_branch_updated)

        # --- Code Generation/Modification UI Updates ---
        self.event_bus.subscribe("prepare_for_generation", self.code_viewer.prepare_for_generation)
        self.event_bus.subscribe("stream_code_chunk", self.code_viewer.stream_code_chunk)
        self.event_bus.subscribe("code_generation_complete", self.code_viewer.display_code)
        self.event_bus.subscribe("code_patched", self.code_viewer.apply_diff_highlighting)

    def show(self):
        """Show the main application window and start background initializations."""
        self.main_window.show()
        self.rag_manager.start_async_initialization()

    def _handle_user_request(self, prompt, conversation_history):
        """Handle the main user prompt to generate or modify code."""
        if self.ai_task and not self.ai_task.done():
            QMessageBox.warning(self.main_window, "AI Busy", "The AI is currently processing another request.")
            return

        # Pass existing files only if we're modifying a loaded project
        existing_files = self.project_manager.get_project_files() if self.project_manager.is_existing_project else None

        self.ai_task = asyncio.create_task(
            self.architect_service.generate_or_modify(prompt, existing_files)
        )

    def _handle_terminal_command(self, command: str):
        """Execute a command from the integrated terminal."""
        if self.terminal_task and not self.terminal_task.done():
            self.event_bus.emit("terminal_output_received", "A command is already running.\n")
            return
        self.terminal_task = asyncio.create_task(self.terminal_service.execute_command(command))

    def _handle_new_project(self):
        """Create a new, empty project."""
        # For now, use a default name. Could add a dialog later.
        project_path = self.project_manager.new_project("New_Project")
        self.main_window.sidebar.update_project_display(self.project_manager.active_project_name)
        self.code_viewer.load_project(project_path)
        self.event_bus.emit("new_session_requested")  # Clears chat and resets state
        if self.project_manager.repo and self.project_manager.repo.active_branch:
            self.event_bus.emit("branch_updated", self.project_manager.repo.active_branch.name)

    def _handle_load_project(self):
        """Open a dialog to load an existing project."""
        path = QFileDialog.getExistingDirectory(self.main_window, "Load Project",
                                                str(self.project_manager.workspace_root))
        if path:
            project_path = self.project_manager.load_project(path)
            if project_path:
                branch_name = self.project_manager.begin_modification_session()
                self.main_window.sidebar.update_project_display(self.project_manager.active_project_name)
                self.code_viewer.load_project(project_path)
                self.event_bus.emit("new_session_requested")  # Clears chat and resets state
                if branch_name:
                    self.event_bus.emit("branch_updated", branch_name)
                elif self.project_manager.repo and self.project_manager.repo.active_branch:
                    self.event_bus.emit("branch_updated", self.project_manager.repo.active_branch.name)

    def _handle_add_project_to_rag(self):
        """Adds all files from the active project to the RAG knowledge base."""
        self.rag_manager.ingest_active_project(self.project_manager, self.main_window)

    def _handle_new_session(self):
        """Resets the state for a new conversation."""
        # Cancel any ongoing AI task to prevent it from continuing in the new session
        if self.ai_task and not self.ai_task.done():
            self.ai_task.cancel()

        # Reset the workflow monitor nodes to their idle state
        for agent_id in ["architect", "coder", "executor", "reviewer"]:
            self.event_bus.emit("node_status_changed", agent_id, "idle", "Ready")

        print("[Application] New session state reset.")

    async def cancel_all_tasks(self):
        """Safely cancel any running background tasks on shutdown."""
        tasks_to_cancel = [self.ai_task, self.terminal_task]
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    print(f"[Application] Task {task.get_name()} successfully cancelled.")