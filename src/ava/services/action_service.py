# src/ava/services/action_service.py
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QFileDialog, QMessageBox
import asyncio
from pathlib import Path

from src.ava.core.event_bus import EventBus
from src.ava.core.app_state import AppState
from src.ava.core.interaction_mode import InteractionMode

if TYPE_CHECKING:
    from src.ava.core.managers.service_manager import ServiceManager
    from src.ava.core.managers.window_manager import WindowManager
    from src.ava.core.managers.task_manager import TaskManager


class ActionService:
    """
    Handles direct user actions from the UI that are not AI prompts.
    This includes project management and session control.
    """

    def __init__(self, event_bus: EventBus, service_manager: "ServiceManager", window_manager: "WindowManager",
                 task_manager: "TaskManager"):
        self.event_bus = event_bus
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager

        # This needs to be deferred until managers are set in EventCoordinator
        if self.window_manager and self.window_manager.get_main_window() and self.service_manager and self.service_manager.get_project_manager():
            self.window_manager.get_main_window().chat_interface.set_project_manager(
                self.service_manager.get_project_manager()
            )
        print("[ActionService] Initialized")

    def handle_build_prompt_from_chat(self, prompt_text: str):
        """Switches to Build mode and populates the chat input with the given text."""
        self.log("info", "Switching to Build mode from chat context.")
        if self.window_manager:
            main_window = self.window_manager.get_main_window()
            if main_window and hasattr(main_window, 'chat_interface'):
                chat_interface = main_window.chat_interface

                # Directly set the mode to BUILD. The UI will update via the event bus.
                self.event_bus.emit("interaction_mode_change_requested", InteractionMode.BUILD)

                # Set the prompt text in the input box
                chat_input = chat_interface.input_widget
                chat_input.set_text_and_focus(prompt_text)

    def handle_new_project(self):
        """Handles the 'New Project' button click, now with context isolation."""
        project_manager = self.service_manager.get_project_manager()
        rag_manager = self.service_manager.get_rag_manager()
        app_state_service = self.service_manager.get_app_state_service()
        lsp_client = self.service_manager.get_lsp_client_service()  # <-- GET LSP CLIENT
        if not all([project_manager, rag_manager, app_state_service]): return

        project_path_str = project_manager.new_project("New_AI_Project")
        if not project_path_str:
            QMessageBox.critical(self.window_manager.get_main_window(), "Project Creation Failed",
                                 "Could not initialize project. Please check your file system permissions.")
            return

        project_path = Path(project_path_str)
        asyncio.create_task(rag_manager.switch_project_context(project_path))
        app_state_service.set_app_state(AppState.MODIFY, project_manager.active_project_name)

        # --- NEW: Initialize LSP session now that we have a project ---
        if lsp_client:
            asyncio.create_task(lsp_client.initialize_session())
        # --- END NEW ---

        # Explicitly tell the chat interface to reset and load the session for the new project.
        if self.window_manager:
            chat_interface = self.window_manager.get_main_window().chat_interface
            if chat_interface:
                chat_interface.set_project_manager(project_manager)
                chat_interface.load_project_session()


    def handle_load_project(self):
        """Handles the 'Load Project' button click, now with context isolation."""
        project_manager = self.service_manager.get_project_manager()
        rag_manager = self.service_manager.get_rag_manager()
        app_state_service = self.service_manager.get_app_state_service()
        lsp_client = self.service_manager.get_lsp_client_service()  # <-- GET LSP CLIENT
        if not all([project_manager, rag_manager, app_state_service]): return

        path = QFileDialog.getExistingDirectory(self.window_manager.get_main_window(), "Load Project",
                                                str(project_manager.workspace_root))
        if path:
            project_path_str = project_manager.load_project(path)
            if project_path_str:
                project_path = Path(project_path_str)
                asyncio.create_task(rag_manager.switch_project_context(project_path))

                self.log("info", "Project loaded.")
                app_state_service.set_app_state(AppState.MODIFY, project_manager.active_project_name)

                # --- NEW: Initialize LSP session now that we have a project ---
                if lsp_client:
                    asyncio.create_task(lsp_client.initialize_session())
                # --- END NEW ---

                # Explicitly tell the chat interface to reset and load the session for the loaded project.
                if self.window_manager:
                    chat_interface = self.window_manager.get_main_window().chat_interface
                    if chat_interface:
                        chat_interface.set_project_manager(project_manager)
                        chat_interface.load_project_session()


    def handle_new_session(self):
        """Handles the 'New Session' button click."""
        self.log("info", "Handling new session reset")
        if self.task_manager:
            asyncio.create_task(self.task_manager.cancel_all_tasks())

        project_manager = self.service_manager.get_project_manager()
        if project_manager:
            project_manager.clear_active_project()

        app_state_service = self.service_manager.get_app_state_service()
        if app_state_service:
            app_state_service.set_app_state(AppState.BOOTSTRAP)

        if self.window_manager and self.window_manager.get_main_window():
            self.window_manager.get_main_window().chat_interface.clear_chat("New session started.")

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ActionService", level, message)