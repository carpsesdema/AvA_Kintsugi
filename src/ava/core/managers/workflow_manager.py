# kintsugi_ava/core/managers/workflow_manager.py
# UPDATED: Now handles image data in user requests.

from PySide6.QtWidgets import QFileDialog, QMessageBox
from typing import Optional

from src.ava.core.event_bus import EventBus
from src.ava.core.app_state import AppState
from src.ava.core.interaction_mode import InteractionMode


class WorkflowManager:
    """
    Orchestrates AI workflows based on both application state and user interaction mode.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.service_manager = None
        self.window_manager = None
        self.task_manager = None

        # State management
        self.app_state: AppState = AppState.BOOTSTRAP
        self.interaction_mode: InteractionMode = InteractionMode.BUILD

        self._last_error_report = None
        print("[WorkflowManager] Initialized in BOOTSTRAP state, BUILD mode")

    def set_managers(self, service_manager, window_manager, task_manager):
        """Set references to other managers and subscribe to state-changing events."""
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager
        self.event_bus.subscribe("project_loaded", self._on_project_activated)
        self.event_bus.subscribe("new_project_created", self._on_project_activated)
        self.event_bus.subscribe("new_session_requested", self.handle_new_session)
        self.event_bus.subscribe("interaction_mode_changed", self.handle_mode_change)
        self.event_bus.subscribe("review_and_fix_from_plugin_requested", self.handle_review_and_fix_request)
        self.event_bus.subscribe("execution_failed", self.handle_execution_failed)
        self.event_bus.subscribe("review_and_fix_requested", self.handle_review_and_fix_button)

    def handle_mode_change(self, new_mode: InteractionMode):
        self.interaction_mode = new_mode
        mode_name = "CHAT" if new_mode == InteractionMode.CHAT else "BUILD"
        print(f"[WorkflowManager] Interaction mode switched to {mode_name}")
        self.event_bus.emit("log_message_received", "WorkflowManager", "info", f"Switched to {mode_name} mode.")

    def _on_project_activated(self, project_path: str, project_name: str):
        print(f"[WorkflowManager] Project '{project_name}' is active. Switching to MODIFY state.")
        self.app_state = AppState.MODIFY
        self.event_bus.emit("app_state_changed", self.app_state, project_name)

    def _on_project_cleared(self):
        print("[WorkflowManager] Project context cleared. Switching to BOOTSTRAP state.")
        self.app_state = AppState.BOOTSTRAP
        self.event_bus.emit("app_state_changed", self.app_state, None)

    def handle_user_request(self, prompt: str, conversation_history: list,
                            image_bytes: Optional[bytes] = None, image_media_type: Optional[str] = None):
        """The central router for all user chat input, now with multimodal support."""
        stripped_prompt = prompt.strip()
        if not stripped_prompt and not image_bytes:
            return

        if stripped_prompt.startswith('/'):
            self._handle_slash_command(stripped_prompt)
            return

        # Prepare the right workflow coroutine based on mode and state
        if self.interaction_mode == InteractionMode.CHAT:
            print("[WorkflowManager] Mode is CHAT. Starting general chat workflow...")
            workflow_coroutine = self._run_chat_workflow(prompt, conversation_history, image_bytes, image_media_type)
        elif self.interaction_mode == InteractionMode.BUILD:
            if self.app_state == AppState.BOOTSTRAP:
                print("[WorkflowManager] Mode is BUILD, State is BOOTSTRAP. Starting new project workflow...")
                workflow_coroutine = self._run_bootstrap_workflow(prompt, image_bytes)
            elif self.app_state == AppState.MODIFY:
                print("[WorkflowManager] Mode is BUILD, State is MODIFY. Starting modification workflow...")
                workflow_coroutine = self._run_modification_workflow(prompt, image_bytes)
        else:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error", f"Unknown interaction mode: {self.interaction_mode}")
            return

        self.task_manager.start_ai_workflow_task(workflow_coroutine)

    async def _run_chat_workflow(self, prompt: str, conversation_history: list,
                                 image_bytes: Optional[bytes] = None, image_media_type: Optional[str] = None):
        """Runs a simple, streaming chat interaction with the LLM, now with image support."""
        if not self.service_manager: return
        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("chat")

        if not provider or not model:
            self.event_bus.emit("streaming_message_chunk", "Sorry, no 'chat' model is configured.")
            return

        # Use a simpler prompt for chat mode
        chat_prompt = prompt or "Describe this image."

        self.event_bus.emit("streaming_message_start", "Kintsugi AvA")
        try:
            stream = llm_client.stream_chat(provider, model, chat_prompt, "chat", image_bytes, image_media_type)
            async for chunk in stream:
                self.event_bus.emit("streaming_message_chunk", chunk)
        except Exception as e:
            self.event_bus.emit("streaming_message_chunk", f"\n\nAn error occurred: {e}")
        finally:
            self.event_bus.emit("streaming_message_end")

    def _handle_slash_command(self, command: str):
        """Parses and executes a slash command from the user."""
        parts = command.strip().split(' ', 1)
        command_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command_name == "/new":
            if not args:
                self.event_bus.emit("log_message_received", "WorkflowManager", "warning", "Usage: /new <description of new project>")
                return
            self.handle_mode_change(InteractionMode.BUILD)
            workflow_coroutine = self._run_bootstrap_workflow(args)
            self.task_manager.start_ai_workflow_task(workflow_coroutine)
        elif command_name == "/build":
            self.handle_mode_change(InteractionMode.BUILD)
            self.event_bus.emit("force_ui_update_request", {"component": "mode_toggle", "mode": "build"})
        elif command_name == "/chat":
            self.handle_mode_change(InteractionMode.CHAT)
            self.event_bus.emit("force_ui_update_request", {"component": "mode_toggle", "mode": "chat"})
        else:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error", f"Unknown command: {command_name}")


    async def _run_bootstrap_workflow(self, prompt: str, image_bytes: Optional[bytes] = None):
        """Runs the workflow to create a new project from a prompt (image support can be added here later)."""
        # TODO: Add logic to describe the image and add it to the prompt if present
        if not self.service_manager: return

        project_manager = self.service_manager.get_project_manager()
        project_manager.clear_active_project()
        self._on_project_cleared()

        project_path = project_manager.new_project("New_AI_Project")
        if not project_path:
            QMessageBox.critical(None, "Project Creation Failed", "Could not create temporary project directory.")
            return

        self.window_manager.update_project_display(project_manager.active_project_name)
        self.window_manager.prepare_code_viewer_for_new_project()
        self.event_bus.emit("new_project_created", project_path, project_manager.active_project_name)

        architect_service = self.service_manager.get_architect_service()
        await architect_service.generate_or_modify(prompt, existing_files=None)

    async def _run_modification_workflow(self, prompt: str, image_bytes: Optional[bytes] = None):
        """Runs the workflow to modify an existing project (image support can be added here later)."""
        # TODO: Add logic to describe the image and add it to the prompt if present
        if not self.service_manager: return

        project_manager = self.service_manager.get_project_manager()
        architect_service = self.service_manager.get_architect_service()

        if not project_manager.active_project_path:
            self.event_bus.emit("log_message_received", "WorkflowManager", "error", "Cannot modify: No project is loaded.")
            return

        existing_files = project_manager.get_project_files()
        await architect_service.generate_or_modify(prompt, existing_files)

    # ... (rest of the file remains the same)
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
            main_window = self.window_manager.get_main_window()
            if main_window and hasattr(main_window, 'chat_interface'):
                if hasattr(main_window.chat_interface, 'mode_toggle'):
                    main_window.chat_interface.mode_toggle.setMode(InteractionMode.BUILD)

        print("[WorkflowManager] New session state reset complete")
        self.event_bus.emit("chat_cleared")

    def handle_execution_failed(self, error_report: str):
        self._last_error_report = error_report
        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        if code_viewer: code_viewer.show_fix_button()

    def handle_review_and_fix_button(self):
        if self._last_error_report: self._initiate_fix_workflow(self._last_error_report)
        else: self.log("warning", "Fix button clicked but no error report was available.")

    def handle_review_and_fix_request(self, error_report: str):
        if error_report: self._initiate_fix_workflow(error_report)
        else: self.log("warning", "Received an empty error report to fix.")

    def handle_highlighted_error_fix_request(self, highlighted_text: str):
        if self._last_error_report:
            augmented_error_report = (
                f"User highlighted: {highlighted_text}\n\nFull error:\n{self._last_error_report}"
            )
            self._initiate_fix_workflow(augmented_error_report)
        else:
            self.log("warning", "A fix was requested for highlighted text, but no previous error is stored.")

    def _initiate_fix_workflow(self, error_report: str):
        """The core logic to start the AI fix workflow."""
        if not self.service_manager or not self.task_manager: return
        code_viewer = self.window_manager.get_code_viewer()
        if code_viewer and hasattr(code_viewer, 'terminal'): code_viewer.terminal.show_fixing_in_progress()
        validation_service = self.service_manager.get_validation_service()
        if validation_service:
            fix_coroutine = validation_service.review_and_fix_file(error_report)
            self.task_manager.start_ai_workflow_task(fix_coroutine)

    def log(self, level, message): self.event_bus.emit("log_message_received", "WorkflowManager", level, message)