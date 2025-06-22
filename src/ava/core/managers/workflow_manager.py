# src/ava/core/managers/workflow_manager.py
from PySide6.QtWidgets import QFileDialog, QMessageBox
from typing import Optional

from src.ava.core.event_bus import EventBus
from src.ava.core.app_state import AppState
from src.ava.core.interaction_mode import InteractionMode
from src.ava.core.managers.service_manager import ServiceManager
from src.ava.core.managers.window_manager import WindowManager
from src.ava.core.managers.task_manager import TaskManager


class WorkflowManager:
    """
    Orchestrates AI workflows based on both application state and user interaction mode.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.service_manager: ServiceManager = None
        self.window_manager: WindowManager = None
        self.task_manager: TaskManager = None
        self.app_state: AppState = AppState.BOOTSTRAP
        self.interaction_mode: InteractionMode = InteractionMode.BUILD
        self._last_error_report = None
        print("[WorkflowManager] Initialized in BOOTSTRAP state, BUILD mode")

    def set_managers(self, service_manager: ServiceManager, window_manager: WindowManager, task_manager: TaskManager):
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

    def handle_user_request(self, prompt: str, conversation_history: list,
                            image_bytes: Optional[bytes] = None, image_media_type: Optional[str] = None):
        """The central router for all user chat input, now with multimodal support."""
        stripped_prompt = prompt.strip()
        if not stripped_prompt and not image_bytes:
            return

        if stripped_prompt.startswith('/'):
            self._handle_slash_command(stripped_prompt)
            return

        workflow_coroutine = None
        if self.interaction_mode == InteractionMode.CHAT:
            print("[WorkflowManager] Mode is CHAT. Starting general chat workflow...")
            workflow_coroutine = self._run_chat_workflow(prompt, image_bytes, image_media_type)
        elif self.interaction_mode == InteractionMode.BUILD:
            if self.app_state == AppState.BOOTSTRAP:
                print("[WorkflowManager] Mode is BUILD, State is BOOTSTRAP. Starting new project workflow...")
                workflow_coroutine = self._run_bootstrap_workflow(prompt, image_bytes)
            elif self.app_state == AppState.MODIFY:
                print("[WorkflowManager] Mode is BUILD, State is MODIFY. Starting modification workflow...")
                workflow_coroutine = self._run_modification_workflow(prompt, image_bytes)
        else:
            self.log("error", f"Unknown interaction mode: {self.interaction_mode}")
            return

        if workflow_coroutine:
            self.task_manager.start_ai_workflow_task(workflow_coroutine)

    async def _get_description_from_image(self, image_bytes: bytes, media_type: str) -> str:
        """Asks a chat model to describe an image and returns the description."""
        self.log("info", "Image provided without text. Asking AI to describe the image for context...")
        if not self.service_manager: return ""

        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("chat")

        if not provider or not model:
            self.log("error", "No 'chat' model configured for image description.")
            return ""

        description_prompt = "Describe the user interface, error message, or diagram shown in this image in detail. This description will be used as the prompt to generate or modify a software project."

        description = ""
        try:
            stream = llm_client.stream_chat(provider, model, description_prompt, "chat", image_bytes, media_type)
            async for chunk in stream:
                description += chunk
            self.log("success", f"AI generated description from image: {description[:100]}...")
            return description
        except Exception as e:
            self.log("error", f"Failed to get description from image: {e}")
            return ""

    async def _run_chat_workflow(self, prompt: str, image_bytes: Optional[bytes], image_media_type: Optional[str]):
        """Runs a simple, streaming chat interaction with the LLM, now with image support."""
        if not self.service_manager: return
        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("chat")

        if not provider or not model:
            self.event_bus.emit("streaming_chunk", "Sorry, no 'chat' model is configured.")
            return

        # If there's an image but no text, create a default prompt.
        chat_prompt = prompt if prompt else "Describe this image in detail."

        self.event_bus.emit("streaming_start", "Kintsugi AvA")
        try:
            stream = llm_client.stream_chat(provider, model, chat_prompt, "chat", image_bytes, image_media_type)
            async for chunk in stream:
                self.event_bus.emit("streaming_chunk", chunk)
        except Exception as e:
            self.event_bus.emit("streaming_chunk", f"\n\nAn error occurred: {e}")
        finally:
            self.event_bus.emit("streaming_end")

    async def _run_bootstrap_workflow(self, prompt: str, image_bytes: Optional[bytes] = None):
        """Runs the workflow to create a new project from a prompt or an image description."""
        if not self.service_manager: return

        final_prompt = prompt
        if not prompt and image_bytes:
            description = await self._get_description_from_image(image_bytes, "image/png")
            if not description:
                self.log("error", "Could not generate a description from the image. Aborting.")
                return
            final_prompt = description

        if not final_prompt:
            self.log("error", "Cannot start new project with an empty prompt.")
            return

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
        await architect_service.generate_or_modify(final_prompt, existing_files=None)

    async def _run_modification_workflow(self, prompt: str, image_bytes: Optional[bytes] = None):
        """Runs the workflow to modify an existing project from a prompt or image description."""
        if not self.service_manager: return

        final_prompt = prompt
        if not prompt and image_bytes:
            description = await self._get_description_from_image(image_bytes, "image/png")
            if not description:
                self.log("error", "Could not generate a description from the image. Aborting.")
                return
            final_prompt = description

        if not final_prompt:
            self.log("error", "Cannot modify project with an empty prompt.")
            return

        project_manager = self.service_manager.get_project_manager()
        if not project_manager.active_project_path:
            self.log("error", "Cannot modify: No project is loaded.")
            return

        existing_files = project_manager.get_project_files()
        architect_service = self.service_manager.get_architect_service()
        await architect_service.generate_or_modify(final_prompt, existing_files)

    def handle_mode_change(self, new_mode: InteractionMode):
        self.interaction_mode = new_mode
        self.log("info", f"Switched to {new_mode.name} mode.")

    def _on_project_activated(self, project_path: str, project_name: str):
        self.log("info", f"Project '{project_name}' is active. Switching to MODIFY state.")
        self.app_state = AppState.MODIFY
        self.event_bus.emit("app_state_changed", self.app_state, project_name)

    def _on_project_cleared(self):
        self.log("info", "Project context cleared. Switching to BOOTSTRAP state.")
        self.app_state = AppState.BOOTSTRAP
        self.event_bus.emit("app_state_changed", self.app_state, None)

    def _handle_slash_command(self, command: str):
        parts = command.strip().split(' ', 1)
        command_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        if command_name == "/new":
            if not args:
                self.log("warning", "Usage: /new <description of new project>")
                return
            self.handle_mode_change(InteractionMode.BUILD)
            self.task_manager.start_ai_workflow_task(self._run_bootstrap_workflow(args))
        elif command_name == "/build":
            self.handle_mode_change(InteractionMode.BUILD)
        elif command_name == "/chat":
            self.handle_mode_change(InteractionMode.CHAT)
        else:
            self.log("error", f"Unknown command: {command_name}")

    def handle_new_project(self):
        if not (self.service_manager and self.window_manager): return
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
        if not (self.service_manager and self.window_manager): return
        project_manager = self.service_manager.get_project_manager()
        path = QFileDialog.getExistingDirectory(self.window_manager.get_main_window(), "Load Project",
                                                str(project_manager.workspace_root))
        if path:
            project_path = project_manager.load_project(path)
            if project_path:
                branch_name = project_manager.begin_modification_session()
                self.log("info", f"Created modification branch: {branch_name}")
                self.window_manager.update_project_display(project_manager.active_project_name)
                self.window_manager.load_project_in_code_viewer(project_path)
                self.event_bus.emit("project_loaded", project_path, project_manager.active_project_name)
                if project_manager.repo and project_manager.repo.active_branch:
                    self.event_bus.emit("branch_updated", project_manager.repo.active_branch.name)

    def handle_new_session(self):
        self.log("info", "Handling new session reset")
        if self.task_manager: self.task_manager.cancel_all_tasks()
        if self.service_manager: self.service_manager.get_project_manager().clear_active_project()
        self._last_error_report = None
        self._on_project_cleared()
        if self.window_manager:
            self.window_manager.update_project_display("(none)")
            self.window_manager.prepare_code_viewer_for_new_project()
        self.event_bus.emit("chat_cleared")

    def handle_execution_failed(self, error_report: str):
        self._last_error_report = error_report
        if self.window_manager and self.window_manager.get_code_viewer():
            self.window_manager.get_code_viewer().show_fix_button()

    def handle_review_and_fix_button(self):
        if self._last_error_report:
            self._initiate_fix_workflow(self._last_error_report)
        else:
            self.log("warning", "Fix button clicked but no error report was available.")

    def handle_review_and_fix_request(self, error_report: str):
        if error_report:
            self._initiate_fix_workflow(error_report)
        else:
            self.log("warning", "Received an empty error report to fix.")

    def handle_highlighted_error_fix_request(self, highlighted_text: str):
        if self._last_error_report:
            self._initiate_fix_workflow(
                f"User highlighted: {highlighted_text}\n\nFull error:\n{self._last_error_report}")
        else:
            self.log("warning", "A fix was requested for highlighted text, but no previous error is stored.")

    def _initiate_fix_workflow(self, error_report: str):
        if not (self.service_manager and self.task_manager): return
        if self.window_manager and self.window_manager.get_code_viewer():
            self.window_manager.get_code_viewer().terminal.show_fixing_in_progress()
        validation_service = self.service_manager.get_validation_service()
        if validation_service:
            self.task_manager.start_ai_workflow_task(validation_service.review_and_fix_file(error_report))

    def log(self, level, message):
        self.event_bus.emit("log_message_received", "WorkflowManager", level, message)