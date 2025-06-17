# kintsugi_ava/core/managers/workflow_manager.py
# UPDATED: Implemented a state machine to handle bootstrap vs. modification workflows.

from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.event_bus import EventBus
from core.app_state import AppState  # <-- NEW: Import our state enum


class WorkflowManager:
    """
    Orchestrates AI workflows and project management operations using a state machine.
    Single responsibility: High-level workflow coordination and state management.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Manager references (set by Application)
        self.service_manager = None
        self.window_manager = None
        self.task_manager = None

        # --- NEW: State Machine Attributes ---
        self.state: AppState = AppState.BOOTSTRAP  # Start in bootstrap mode
        self._last_error_report = None

        print("[WorkflowManager] Initialized in BOOTSTRAP state")

    def set_managers(self, service_manager, window_manager, task_manager):
        """Set references to other managers and subscribe to state-changing events."""
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager

        # --- NEW: Subscribe to events that change our application state ---
        self.event_bus.subscribe("project_loaded", self._on_project_activated)
        self.event_bus.subscribe("new_project_created", self._on_project_activated)
        # The "New Session" button will be our primary way to reset the state
        self.event_bus.subscribe("new_session_requested", self.handle_new_session)

    # --- NEW: State Change Handlers ---
    def _on_project_activated(self, project_path: str, project_name: str):
        """
        Callback for when a project becomes active (loaded or created).
        This transitions the application into the 'MODIFY' state.
        """
        print(f"[WorkflowManager] Project '{project_name}' is active. Switching to MODIFY state.")
        self.state = AppState.MODIFY
        # Announce the state change to the rest of the app (specifically the UI)
        self.event_bus.emit("app_state_changed", self.state, project_name)

    def _on_project_cleared(self):
        """
        Callback to reset the application to its initial 'BOOTSTRAP' state.
        """
        print("[WorkflowManager] Project context cleared. Switching to BOOTSTRAP state.")
        self.state = AppState.BOOTSTRAP
        self.event_bus.emit("app_state_changed", self.state, None)  # No project name

    # --- NEW: Central User Request Router ---
    def handle_user_request(self, prompt: str, conversation_history: list):
        """
        This is the NEW central router for all user chat input.
        It checks for slash commands, then routes based on the current app state.
        """
        stripped_prompt = prompt.strip()
        if not stripped_prompt:
            return

        # 1. Check for slash commands
        if stripped_prompt.startswith('/'):
            self._handle_slash_command(stripped_prompt)
            return

        # 2. Route based on the current application state
        if self.state == AppState.BOOTSTRAP:
            print("[WorkflowManager] State is BOOTSTRAP. Starting new project workflow...")
            workflow_coroutine = self._run_bootstrap_workflow(prompt)
        elif self.state == AppState.MODIFY:
            print("[WorkflowManager] State is MODIFY. Starting modification workflow...")
            workflow_coroutine = self._run_modification_workflow(prompt)
        else:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error", f"Unknown state: {self.state}")
            return

        # 3. Execute the chosen workflow
        self.task_manager.start_ai_workflow_task(workflow_coroutine)

    # --- NEW: Slash Command Handler ---
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
            # This command explicitly triggers a bootstrap workflow.
            workflow_coroutine = self._run_bootstrap_workflow(args)
            self.task_manager.start_ai_workflow_task(workflow_coroutine)
        else:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error", f"Unknown command: {command_name}")

    # --- Renamed and Refactored Workflow Methods ---
    async def _run_bootstrap_workflow(self, prompt: str):
        """Runs the workflow to create a new project from a prompt."""
        if not self.service_manager:
            return

        # Ensure we are in a clean state to create a new project
        self._on_project_cleared()  # This resets the UI and state

        # We need a new, blank project created first for the architect to work in.
        project_manager = self.service_manager.get_project_manager()
        project_path = project_manager.new_project("New_AI_Project")
        if not project_path:
            QMessageBox.critical(None, "Project Creation Failed", "Could not create temporary project directory.")
            return

        # Announce the new project so the state machine is aware.
        self.event_bus.emit("new_project_created", project_path, project_manager.active_project_name)

        architect_service = self.service_manager.get_architect_service()
        await architect_service.generate_or_modify(prompt, existing_files=None)

    async def _run_modification_workflow(self, prompt: str):
        """Runs the workflow to modify an existing project."""
        if not self.service_manager:
            return

        project_manager = self.service_manager.get_project_manager()
        architect_service = self.service_manager.get_architect_service()

        if not project_manager.active_project_path:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error",
                                "Cannot modify: No project is loaded.")
            return

        existing_files = project_manager.get_project_files()
        await architect_service.generate_or_modify(prompt, existing_files)

    # --- UPDATED: Button Handlers to emit events ---
    def handle_new_project(self):
        """Handles the 'New Project' button click. Creates a blank project and sets the state."""
        if not self.service_manager or not self.window_manager:
            return

        project_manager = self.service_manager.get_project_manager()
        project_path = project_manager.new_project("New_Project")
        if not project_path:
            QMessageBox.critical(self.window_manager.get_main_window(), "Project Creation Failed",
                                 "Could not initialize project. Please ensure Git is installed.")
            return

        self.window_manager.update_project_display(project_manager.active_project_name)
        self.window_manager.prepare_code_viewer_for_new_project()

        # Announce the new project, which will trigger the state change to MODIFY
        self.event_bus.emit("new_project_created", project_path, project_manager.active_project_name)
        if project_manager.repo and project_manager.repo.active_branch:
            self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

    def handle_load_project(self):
        """Handles the 'Load Project' button click. Loads a project and sets the state."""
        if not self.service_manager or not self.window_manager:
            return

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

                # Announce the loaded project, which will trigger the state change to MODIFY
                self.event_bus.emit("project_loaded", project_path, project_manager.active_project_name)
                if project_manager.repo and project_manager.repo.active_branch:
                    self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

    # --- UPDATED: New Session Handler ---
    def handle_new_session(self):
        """Handles new session request - resets all state."""
        print("[WorkflowManager] Handling new session reset")
        if self.task_manager:
            self.task_manager.cancel_ai_task()
            self.task_manager.cancel_all_terminal_tasks()

        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        if code_viewer:
            code_viewer.clear_all_error_highlights()
            code_viewer.hide_fix_button()

        self._last_error_report = None

        # NEW: Reset the application state back to bootstrap.
        # Note: This does not clear the project itself, just the session and state.
        # User must click "New Project" to clear the loaded project.
        # Let's re-think that. A "New Session" should probably reset everything.
        # For now, let's keep the project loaded but ready for a fresh request.
        # If we want a full reset, we can add `self._on_project_cleared()` here.
        # Let's add it. "New Session" should feel like a fresh start.
        self._on_project_cleared()

        if self.window_manager:
            self.window_manager.update_project_display("(none)")
            self.window_manager.prepare_code_viewer_for_new_project()

        # Also need to clear the project in the ProjectManager itself.
        if self.service_manager and self.service_manager.get_project_manager():
            self.service_manager.get_project_manager().clear_active_project()

        print("[WorkflowManager] New session state reset complete")
        self.event_bus.emit("chat_cleared")

    def handle_execution_failed(self, error_report: str):
        self._last_error_report = error_report
        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        if code_viewer:
            code_viewer.show_fix_button()

    def handle_review_and_fix(self):
        if not self._last_error_report:
            return
        if not self.service_manager or not self.task_manager:
            return
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