# src/ava/services/action_service.py
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.ava.core.event_bus import EventBus
from src.ava.core.app_state import AppState

if TYPE_CHECKING:
    from src.ava.core.managers.service_manager import ServiceManager
    from src.ava.core.managers.window_manager import WindowManager
    from src.ava.core.managers.task_manager import TaskManager


class ActionService:
    """
    Handles direct user actions from the UI that are not AI prompts.
    This includes project management and session control.
    """

    def __init__(self, event_bus: EventBus, service_manager: "ServiceManager", window_manager: "WindowManager", task_manager: "TaskManager"):
        self.event_bus = event_bus
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager
        print("[ActionService] Initialized")

    def handle_new_project(self):
        """Handles the 'New Project' button click."""
        project_manager = self.service_manager.get_project_manager()
        app_state_service = self.service_manager.get_app_state_service()
        if not project_manager or not app_state_service:
            return

        project_path = project_manager.new_project("New_Project")
        if not project_path:
            QMessageBox.critical(self.window_manager.get_main_window(), "Project Creation Failed",
                                 "Could not initialize project. Please ensure Git is installed.")
            return

        app_state_service.set_app_state(AppState.MODIFY, project_manager.active_project_name)

        if project_manager.repo and project_manager.repo.active_branch:
            self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

    def handle_load_project(self):
        """Handles the 'Load Project' button click."""
        project_manager = self.service_manager.get_project_manager()
        app_state_service = self.service_manager.get_app_state_service()
        if not project_manager or not app_state_service:
            return

        path = QFileDialog.getExistingDirectory(self.window_manager.get_main_window(), "Load Project",
                                                str(project_manager.workspace_root))
        if path:
            project_path = project_manager.load_project(path)
            if project_path:
                branch_name = project_manager.begin_modification_session()
                self.log("info", f"Created modification branch: {branch_name}")
                app_state_service.set_app_state(AppState.MODIFY, project_manager.active_project_name)

                if project_manager.repo and project_manager.repo.active_branch:
                    self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

    def handle_new_session(self):
        """Handles the 'New Session' button click."""
        self.log("info", "Handling new session reset")
        if self.task_manager:
            self.task_manager.cancel_all_tasks()

        project_manager = self.service_manager.get_project_manager()
        if project_manager:
            project_manager.clear_active_project()

        app_state_service = self.service_manager.get_app_state_service()
        if app_state_service:
            app_state_service.set_app_state(AppState.BOOTSTRAP)

        self.event_bus.emit("chat_cleared")

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ActionService", level, message)