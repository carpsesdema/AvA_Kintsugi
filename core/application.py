# kintsugi_ava/core/application.py
# V12: Implements launching and terminating the external RAG server.

import asyncio
from pathlib import Path
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
from services.reviewer_service import ReviewerService
from services.validation_service import ValidationService


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
        self.workflow_monitor = WorkflowMonitorWindow(self.event_bus)
        self.terminals = TerminalsWindow(self.event_bus)
        self.model_config_dialog = ModelConfigurationDialog(self.llm_client, self.main_window)

        # --- Services ---
        self.rag_manager = RAGManager(self.event_bus) # Manages the RAG server process
        self.architect_service = ArchitectService(
            self.event_bus, self.llm_client, self.project_manager, self.rag_manager.rag_service)
        self.reviewer_service = ReviewerService(self.event_bus, self.llm_client)
        self.validation_service = ValidationService(
            self.event_bus, self.execution_engine, self.project_manager, self.reviewer_service)
        self.terminal_service = TerminalService(
            self.event_bus, self.project_manager, self.execution_engine, self.code_viewer)

        # --- State ---
        self.ai_task = None
        self.terminal_task = None
        self._last_error_report = None

        self._connect_events()
        print("[Application] Core components initialized and events connected.")

    def _connect_events(self):
        """Subscribe handlers to events on the central event bus."""
        # Project & Session
        self.event_bus.subscribe("user_request_submitted", self._handle_user_request)
        self.event_bus.subscribe("new_project_requested", self._handle_new_project)
        self.event_bus.subscribe("load_project_requested", self._handle_load_project)
        self.event_bus.subscribe("new_session_requested", self._handle_new_session)

        # Tools & Config
        self.event_bus.subscribe("configure_models_requested", self.model_config_dialog.exec)
        self.event_bus.subscribe("launch_rag_server_requested", self._handle_launch_rag_server)

        # --- THE FIX: Removing subscriptions to methods that no longer exist ---
        # The following buttons are now placeholders and their events are removed to prevent crashes.
        # self.event_bus.subscribe("scan_directory_requested", self.rag_manager.open_scan_directory_dialog)
        # self.event_bus.subscribe("add_active_project_to_rag_requested", self.rag_manager.ingest_active_project)
        # --- END OF FIX ---

        # Execution & Fixing
        self.event_bus.subscribe("terminal_command_entered", self._handle_terminal_command)
        self.event_bus.subscribe("execution_failed", self._handle_execution_failed)
        self.event_bus.subscribe("review_and_fix_requested", self._handle_review_and_fix)
        self.event_bus.subscribe("error_highlight_requested", self.code_viewer.highlight_error_in_editor)

        # UI Updates & Window Visibility
        self.event_bus.subscribe("show_code_viewer_requested", self.code_viewer.show_window)
        self.event_bus.subscribe("show_workflow_monitor_requested", self.workflow_monitor.show)
        self.event_bus.subscribe("show_terminals_requested", self.terminals.show)
        self.event_bus.subscribe("ai_response_ready", self.main_window.chat_interface._add_ai_response)
        self.event_bus.subscribe("log_message_received", self.terminals.add_log_message)
        self.event_bus.subscribe("node_status_changed", self.workflow_monitor.scene.update_node_status)
        self.event_bus.subscribe("branch_updated", self.code_viewer.statusBar().on_branch_updated)

        # Code Generation
        self.event_bus.subscribe("prepare_for_generation", self.code_viewer.prepare_for_generation)
        self.event_bus.subscribe("stream_code_chunk", self.code_viewer.stream_code_chunk)
        self.event_bus.subscribe("code_generation_complete", self.code_viewer.display_code)

    def show(self):
        """Show the main application window."""
        self.main_window.show()

    def _handle_user_request(self, prompt, conversation_history):
        if self.ai_task and not self.ai_task.done():
            QMessageBox.warning(self.main_window, "AI Busy", "The AI is currently processing another request.")
            return
        self.ai_task = asyncio.create_task(self._run_full_workflow(prompt))
        self.ai_task.add_done_callback(self._on_ai_task_done)

    def _on_ai_task_done(self, task: asyncio.Task):
        try:
            task.result()
            self.event_bus.emit("ai_response_ready", "Code generation complete. Run the code or ask for modifications.")
        except asyncio.CancelledError:
            print("[Application] AI task was cancelled.")
        except Exception as e:
            print(f"[Application] CRITICAL ERROR IN AI TASK: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.main_window, "Workflow Error", f"The AI workflow failed unexpectedly.\n\nError: {e}")
        finally:
            self.code_viewer.hide_fix_button()

    async def _run_full_workflow(self, prompt: str):
        existing_files = self.project_manager.get_project_files() if self.project_manager.is_existing_project else None
        await self.architect_service.generate_or_modify(prompt, existing_files)

    def _handle_terminal_command(self, command: str):
        if self.terminal_task and not self.terminal_task.done():
            self.event_bus.emit("terminal_output_received", "A command is already running.\n")
            return
        self.code_viewer.clear_all_error_highlights()
        self._last_error_report = None
        self.code_viewer.hide_fix_button()
        self.terminal_task = asyncio.create_task(self.terminal_service.execute_command(command))

    def _handle_execution_failed(self, error_report: str):
        self._last_error_report = error_report
        self.code_viewer.show_fix_button()

    def _handle_review_and_fix(self):
        if not self._last_error_report:
            return
        self.code_viewer.terminal.show_fixing_in_progress()
        if self.ai_task and not self.ai_task.done():
            QMessageBox.warning(self.main_window, "AI Busy", "The AI is currently processing another request.")
            self.code_viewer.hide_fix_button()
            return
        self.ai_task = asyncio.create_task(self.validation_service.review_and_fix_file(self._last_error_report))
        self.ai_task.add_done_callback(self._on_ai_task_done)
        self._last_error_report = None

    def _handle_new_project(self):
        project_path = self.project_manager.new_project("New_Project")
        if not project_path:
            QMessageBox.critical(self.main_window, "Project Creation Failed", "Could not initialize Git. Please ensure Git is installed and in your PATH.")
            return
        self.main_window.sidebar.update_project_display(self.project_manager.active_project_name)
        self.code_viewer.prepare_for_new_project_session()
        if self.project_manager.repo and self.project_manager.repo.active_branch:
            self.event_bus.emit("branch_updated", self.project_manager.repo.active_branch.name)
        self.event_bus.emit("new_session_requested")

    def _handle_load_project(self):
        path = QFileDialog.getExistingDirectory(self.main_window, "Load Project", str(self.project_manager.workspace_root))
        if path:
            project_path = self.project_manager.load_project(path)
            if project_path:
                branch_name = self.project_manager.begin_modification_session()
                self.main_window.sidebar.update_project_display(self.project_manager.active_project_name)
                self.code_viewer.load_project(project_path)
                self.event_bus.emit("new_session_requested")
                if branch_name:
                    self.event_bus.emit("branch_updated", branch_name)
                elif self.project_manager.repo and self.project_manager.repo.active_branch:
                    self.event_bus.emit("branch_updated", self.project_manager.repo.active_branch.name)

    def _handle_launch_rag_server(self):
        self.rag_manager.launch_rag_server(self.main_window)

    def _handle_new_session(self):
        if self.ai_task and not self.ai_task.done():
            self.ai_task.cancel()
        if self.terminal_task and not self.terminal_task.done():
            self.terminal_task.cancel()
        for agent_id in ["architect", "coder", "executor", "reviewer"]:
            self.event_bus.emit("node_status_changed", agent_id, "idle", "Ready")
        self.code_viewer.clear_all_error_highlights()
        self.code_viewer.hide_fix_button()
        self._last_error_report = None
        print("[Application] New session state reset.")

    async def cancel_all_tasks(self):
        """
        Cleanly shuts down all background processes and tasks.
        This is called when the application is about to quit.
        """
        self.rag_manager.terminate_rag_server()

        tasks_to_cancel = [self.ai_task, self.terminal_task]
        for task in tasks_to_cancel:
            if task and not task.done():
                try:
                    task.cancel()
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"[Application] Error during task cancellation: {e}")