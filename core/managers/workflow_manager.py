# kintsugi_ava/core/managers/workflow_manager.py
# UPDATED: Added robust error handling for the context-gathering phase.

from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.event_bus import EventBus
from core.app_state import AppState


class WorkflowManager:
    """
    Orchestrates AI workflows and project management operations using a state machine.
    Single responsibility: High-level workflow coordination and state management.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.service_manager = None
        self.window_manager = None
        self.task_manager = None
        self.state: AppState = AppState.BOOTSTRAP
        self._last_error_report = None
        print("[WorkflowManager] Initialized in BOOTSTRAP state")

    def set_managers(self, service_manager, window_manager, task_manager):
        """Set references to other managers and subscribe to state-changing events."""
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager
        self.event_bus.subscribe("project_loaded", self._on_project_activated)
        self.event_bus.subscribe("new_project_created", self._on_project_activated)
        self.event_bus.subscribe("new_session_requested", self.handle_new_session)

    def _on_project_activated(self, project_path: str, project_name: str):
        """Callback for when a project becomes active, transitioning the app to 'MODIFY' state."""
        print(f"[WorkflowManager] Project '{project_name}' is active. Switching to MODIFY state.")
        self.state = AppState.MODIFY
        self.event_bus.emit("app_state_changed", self.state, project_name)

    def _on_project_cleared(self):
        """Callback to reset the application to its initial 'BOOTSTRAP' state."""
        print("[WorkflowManager] Project context cleared. Switching to BOOTSTRAP state.")
        self.state = AppState.BOOTSTRAP
        self.event_bus.emit("app_state_changed", self.state, None)

    def handle_user_request(self, prompt: str, conversation_history: list):
        """The central router for all user chat input."""
        stripped_prompt = prompt.strip()
        if not stripped_prompt:
            return

        if stripped_prompt.startswith('/'):
            self._handle_slash_command(stripped_prompt)
            return

        if self.state == AppState.BOOTSTRAP:
            print("[WorkflowManager] State is BOOTSTRAP. Starting new project workflow...")
            workflow_coroutine = self._run_bootstrap_workflow(prompt)
        elif self.state == AppState.MODIFY:
            print("[WorkflowManager] State is MODIFY. Starting modification workflow...")
            workflow_coroutine = self._run_modification_workflow(prompt)
        else:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error", f"Unknown state: {self.state}")
            return

        self.task_manager.start_ai_workflow_task(workflow_coroutine)

    def _handle_slash_command(self, command: str):
        """Parses and executes a slash command from the user."""
        parts = command.strip().split(' ', 1)
        command_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        print(f"[WorkflowManager] Handling slash command: {command_name}")

        if command_name == "/new":
            if not args:
                self.event_bus.emit("log_message_received", "WorkflowManager", "warning",
                                    "Usage: /new <description of new project>")
                return
            workflow_coroutine = self._run_bootstrap_workflow(args)
            self.task_manager.start_ai_workflow_task(workflow_coroutine)
        else:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error", f"Unknown command: {command_name}")

    async def _run_bootstrap_workflow(self, prompt: str):
        """Runs the workflow to create a new project from a prompt."""
        if not self.service_manager: return

        project_manager = self.service_manager.get_project_manager()
        # A new bootstrap request implies clearing any previous state.
        project_manager.clear_active_project()
        self._on_project_cleared()

        # A bootstrap requires a temporary project name to start.
        project_path = project_manager.new_project("New_AI_Project")
        if not project_path:
            QMessageBox.critical(None, "Project Creation Failed", "Could not create temporary project directory.")
            return

        self.window_manager.update_project_display(project_manager.active_project_name)
        self.window_manager.prepare_code_viewer_for_new_project()
        self.event_bus.emit("new_project_created", project_path, project_manager.active_project_name)

        architect_service = self.service_manager.get_architect_service()
        await architect_service.generate_or_modify(prompt, existing_files=None)

    async def _run_modification_workflow(self, prompt: str):
        """Runs the workflow to modify an existing project, with robust context gathering."""
        if not self.service_manager: return

        project_manager = self.service_manager.get_project_manager()
        architect_service = self.service_manager.get_architect_service()

        if not project_manager.active_project_path:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error",
                                "Cannot modify: No project is loaded.")
            return

        # --- NEW: Robust Context Gathering ---
        try:
            existing_files = project_manager.get_project_files()
            # In the future, context from other services (e.g., LivingDesignAgent) would be gathered here.
        except Exception as e:
            error_msg = f"Failed to gather project context before modification. Error: {e}"
            self.event_bus.emit("log_message_received", "WorkflowManager", "error", error_msg)
            self.event_bus.emit("ai_response_ready",
                                "Sorry, I couldn't properly analyze the project to make changes. Please check the logs.")
            return
        # --- END Robust Context Gathering ---

        await architect_service.generate_or_modify(prompt, existing_files)

    def handle_new_project(self):
        if not self.service_manager or not self.window_manager: return
        project_manager = self.service_manager.get_project_manager()
        project_path = project_manager.new_project("New_Project")
        if not project_path:
            QMessageBox.critical(self.window_manager.get_main_window(), "Project Creation Failed",
                                 "Could not initialize project. Please ensure Git is installed.")
            return
        self.window_manager.update_project_display(project_manager.active_project_name)
        self.window_manager.prepare_code_viewer_for_new_project()
        self.event_bus.emit("new_project_created", project_path, project_manager.active_project_name)
        if project_manager.repo and project_manager.repo.active_branch:
            self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

    def handle_load_project(self):
        if not self.service_manager or not self.window_manager: return
        project_manager = self.service_manager.get_project_manager()
        path = QFileDialog.getExistingDirectory(self.window_manager.get_main_window(), "Load Project",
                                                str(project_manager.workspace_root))
        if path:
            project_path = project_manager.load_project(path)
            if project_path:
                branch_name = project_manager.begin_modification_session()
                print(f"[WorkflowManager] Created modification branch: {branch_name}")
                self.window_manager.update_project_display(project_manager.active_project_name)
                self.window_manager.load_project_in_code_viewer(project_path)
                self.event_bus.emit("project_loaded", project_path, project_manager.active_project_name)
                if project_manager.repo and project_manager.repo.active_branch:
                    self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

    def handle_new_session(self):
        """Handles new session request - a full reset to initial state."""
        print("[WorkflowManager] Handling new session reset")
        if self.task_manager:
            self.task_manager.cancel_ai_task()
            self.task_manager.cancel_all_terminal_tasks()

        if self.service_manager and self.service_manager.get_project_manager():
            self.service_manager.get_project_manager().clear_active_project()

        self._last_error_report = None
        self._on_project_cleared()

        if self.window_manager:
            self.window_manager.update_project_display("(none)")
            self.window_manager.prepare_code_viewer_for_new_project()

        print("[WorkflowManager] New session state reset complete")
        self.event_bus.emit("chat_cleared")

    def handle_execution_failed(self, error_report: str):
        self._last_error_report = error_report
        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        if code_viewer:
            code_viewer.show_fix_button()

    def handle_review_and_fix(self):
        if not self._last_error_report: return
        if not self.service_manager or not self.task_manager: return
        code_viewer = self.window_manager.get_code_viewer()
        if code_viewer and hasattr(code_viewer, 'terminal'):
            code_viewer.terminal.show_fixing_in_progress()
        validation_service = self.service_manager.get_validation_service()
        if validation_service:
            fix_coroutine = validation_service.review_and_fix_file(self._last_error_report)
            if self.task_manager.start_ai_workflow_task(fix_coroutine):
                self._last_error_report = None

    def get_workflow_status(self) -> dict:
        """Get current workflow status for debugging."""
        return {
            "current_state": self.state.name,
            "has_error_report": self._last_error_report is not None,
        }