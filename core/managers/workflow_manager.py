# kintsugi_ava/core/managers/workflow_manager.py
# UPDATED: Removed agent status events previously used by the workflow monitor.

from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox

from core.event_bus import EventBus


class WorkflowManager:
    """
    Orchestrates AI workflows and project management operations.
    Single responsibility: High-level workflow coordination and state management.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Manager references (set by Application)
        self.service_manager = None
        self.window_manager = None
        self.task_manager = None

        # Workflow state
        self._last_error_report = None

        print("[WorkflowManager] Initialized")

    def set_managers(self, service_manager, window_manager, task_manager):
        """
        Set references to other managers.

        Args:
            service_manager: ServiceManager instance
            window_manager: WindowManager instance
            task_manager: TaskManager instance
        """
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager

    def handle_user_request(self, prompt: str, conversation_history: list):
        """
        Handle user request for AI code generation.

        Args:
            prompt: User's request text
            conversation_history: Chat conversation history
        """
        if not self.service_manager or not self.task_manager:
            print("[WorkflowManager] Cannot handle user request: managers not set")
            return

        workflow_coroutine = self._run_full_workflow(prompt)
        self.task_manager.start_ai_workflow_task(workflow_coroutine)

    async def _run_full_workflow(self, prompt: str):
        """
        Execute the complete AI workflow.

        Args:
            prompt: User's request prompt
        """
        if not self.service_manager:
            return

        project_manager = self.service_manager.get_project_manager()
        architect_service = self.service_manager.get_architect_service()

        if not project_manager or not architect_service:
            print("[WorkflowManager] Cannot run workflow: required services not available")
            return

        # FIX: Properly check for existing project and get files
        existing_files = None
        if project_manager.is_existing_project and project_manager.active_project_path:
            print(f"[WorkflowManager] Loading existing project files from: {project_manager.active_project_path}")
            existing_files = project_manager.get_project_files()
            if existing_files:
                print(f"[WorkflowManager] Found {len(existing_files)} existing files for modification")
            else:
                print("[WorkflowManager] No tracked files found in existing project")
        else:
            print("[WorkflowManager] Creating new project - no existing files")

        await architect_service.generate_or_modify(prompt, existing_files)

    def handle_new_project(self):
        """Handle new project creation request."""
        if not self.service_manager or not self.window_manager:
            print("[WorkflowManager] Cannot handle new project: managers not set")
            return

        project_manager = self.service_manager.get_project_manager()
        main_window = self.window_manager.get_main_window()

        if not project_manager:
            print("[WorkflowManager] Cannot create project: ProjectManager not available")
            return

        project_path = project_manager.new_project("New_Project")
        if not project_path:
            QMessageBox.critical(main_window, "Project Creation Failed",
                                 "Could not initialize Git. Please ensure Git is installed and in your PATH.")
            return

        # Update UI
        self.window_manager.update_project_display(project_manager.active_project_name)
        self.window_manager.prepare_code_viewer_for_new_project()

        # Update branch display
        if project_manager.repo and project_manager.repo.active_branch:
            self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

        # Reset session
        self.event_bus.emit("new_session_requested")

    def handle_load_project(self):
        """Handle load existing project request."""
        if not self.service_manager or not self.window_manager:
            print("[WorkflowManager] Cannot handle load project: managers not set")
            return

        project_manager = self.service_manager.get_project_manager()
        main_window = self.window_manager.get_main_window()

        if not project_manager:
            print("[WorkflowManager] Cannot load project: ProjectManager not available")
            return

        path = QFileDialog.getExistingDirectory(
            main_window,
            "Load Project",
            str(project_manager.workspace_root)
        )

        if path:
            project_path = project_manager.load_project(path)
            if project_path:
                # Create a new branch for modifications
                branch_name = project_manager.begin_modification_session()
                print(f"[WorkflowManager] Created modification branch: {branch_name}")

                # Update UI
                self.window_manager.update_project_display(project_manager.active_project_name)
                self.window_manager.load_project_in_code_viewer(project_path)

                # Reset session
                self.event_bus.emit("new_session_requested")

                # Update branch display
                if branch_name and not branch_name.startswith("Error"):
                    self.event_bus.emit("branch_updated", branch_name)
                elif project_manager.repo and project_manager.repo.active_branch:
                    self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

                # Log the loaded files
                existing_files = project_manager.get_project_files()
                if existing_files:
                    print(f"[WorkflowManager] Project loaded with {len(existing_files)} files")

    def handle_execution_failed(self, error_report: str):
        """
        Handle execution failure - prepare for review and fix.

        Args:
            error_report: Error report from failed execution
        """
        self._last_error_report = error_report

        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        if code_viewer:
            code_viewer.show_fix_button()

    def handle_review_and_fix(self):
        """Handle review and fix request from user."""
        if not self._last_error_report:
            print("[WorkflowManager] No error report available for review and fix")
            return

        if not self.service_manager or not self.task_manager:
            print("[WorkflowManager] Cannot handle review and fix: managers not set")
            return

        # Update UI to show work in progress
        code_viewer = self.window_manager.get_code_viewer()
        if code_viewer and hasattr(code_viewer, 'terminal'):
            code_viewer.terminal.show_fixing_in_progress()

        # Start the review and fix workflow
        validation_service = self.service_manager.get_validation_service()
        if validation_service:
            fix_coroutine = validation_service.review_and_fix_file(self._last_error_report)
            if self.task_manager.start_ai_workflow_task(fix_coroutine):
                self._last_error_report = None  # Clear after starting task

    def handle_new_session(self):
        """Handle new session request - reset all state."""
        print("[WorkflowManager] Handling new session reset")

        # Cancel any running tasks
        if self.task_manager:
            self.task_manager.cancel_ai_task()
            self.task_manager.cancel_terminal_task()

        # Clear error state
        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        if code_viewer:
            code_viewer.clear_all_error_highlights()
            code_viewer.hide_fix_button()

        # Reset workflow state
        self._last_error_report = None

        print("[WorkflowManager] New session state reset complete")

    def get_workflow_status(self) -> dict:
        """Get current workflow status for debugging."""
        return {
            "has_error_report": self._last_error_report is not None,
            "error_report_preview": self._last_error_report[:100] + "..." if self._last_error_report else None,
            "managers_available": {
                "service_manager": self.service_manager is not None,
                "window_manager": self.window_manager is not None,
                "task_manager": self.task_manager is not None
            }
        }