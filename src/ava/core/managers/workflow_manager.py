# src/ava/core/managers/workflow_manager.py
import asyncio
import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox
from typing import Optional, Dict

from src.ava.core.event_bus import EventBus
from src.ava.core.app_state import AppState
from src.ava.core.interaction_mode import InteractionMode
from src.ava.core.managers.service_manager import ServiceManager
from src.ava.core.managers.window_manager import WindowManager
from src.ava.core.managers.task_manager import TaskManager
from src.ava.prompts import (
    CREATIVE_ASSISTANT_PROMPT, AURA_REFINEMENT_PROMPT
)


class WorkflowManager:
    """
    Orchestrates AI workflows based on the authoritative application state.
    It reads state from AppStateService but does not set it.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.service_manager: ServiceManager = None
        self.window_manager: WindowManager = None
        self.task_manager: TaskManager = None
        self._last_error_report = None
        self._last_generated_code: Optional[Dict[str, str]] = None
        self._is_plugin_override_active = False # Retained for potential future Python plugins
        print("[WorkflowManager] Initialized")

    def set_managers(self, service_manager: ServiceManager, window_manager: WindowManager, task_manager: TaskManager):
        """Set references to other managers and subscribe to relevant events."""
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager
        self.event_bus.subscribe("review_and_fix_from_plugin_requested", self.handle_review_and_fix_request)
        self.event_bus.subscribe("execution_failed", self.handle_execution_failed)
        self.event_bus.subscribe("review_and_fix_requested", self.handle_review_and_fix_button)
        self.event_bus.subscribe("session_cleared", self._on_session_cleared)
        self.event_bus.subscribe("code_generation_complete", self._on_code_generation_complete)
        self.event_bus.subscribe("plugin_build_override_activated", self._activate_plugin_override)

    def _activate_plugin_override(self):
        """Called by a plugin to signal it's taking over the build process."""
        self._is_plugin_override_active = True

    def _on_code_generation_complete(self, generated_files: Dict[str, str]):
        """Catches the generated code after a build to be used by Aura."""
        self.log("info", f"WorkflowManager captured {len(generated_files)} generated files for Aura's context.")
        self._last_generated_code = generated_files
        self._is_plugin_override_active = False  # Reset override after a build completes

    async def _run_aura_workflow(self, user_idea: str, conversation_history: list, image_bytes: Optional[bytes],
                                 image_media_type: Optional[str]):
        """Runs the Aura persona workflow."""
        self.log("info", f"Aura is processing: '{user_idea[:50]}...'")

        history_for_prompt = conversation_history[:-1] if conversation_history else []
        formatted_history = "\n".join(
            [f"{msg.get('sender', msg.get('role', 'unknown')).title()}: {msg.get('text', '') or msg.get('content', '')}"
             for msg in history_for_prompt]
        )

        if self._last_generated_code:
            self.log("info", "Aura is in REFINEMENT mode with existing code context.")
            code_context_json = json.dumps(self._last_generated_code, indent=2)
            aura_prompt = AURA_REFINEMENT_PROMPT.format(
                conversation_history=formatted_history,
                user_idea=user_idea,
                code_context=code_context_json
            )
        else:
            self.log("info", "Aura is in CREATION mode.")
            aura_prompt = CREATIVE_ASSISTANT_PROMPT.format(
                conversation_history=formatted_history,
                user_idea=user_idea
            )

        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("chat")

        if not provider or not model:
            self.event_bus.emit("streaming_chunk", "Sorry, no 'chat' model is configured for Aura.")
            return

        self.event_bus.emit("streaming_start", "Aura")
        try:
            stream = llm_client.stream_chat(
                provider, model, aura_prompt, "chat",
                image_bytes, image_media_type,
                history=conversation_history
            )
            async for chunk in stream:
                self.event_bus.emit("streaming_chunk", chunk)
        except Exception as e:
            self.event_bus.emit("streaming_chunk", f"\n\nAura encountered an error: {e}")
            self.log("error", f"Error during Aura streaming: {e}")
        finally:
            self.event_bus.emit("streaming_end")

    def handle_user_request(self, prompt: str, conversation_history: list,
                            image_bytes: Optional[bytes] = None, image_media_type: Optional[str] = None,
                            code_context: Optional[Dict[str, str]] = None):
        """The central router for all user chat input."""
        stripped_prompt = prompt.strip()
        if not stripped_prompt and not image_bytes and not code_context:
            return

        app_state_service = self.service_manager.get_app_state_service()
        if not app_state_service:
            self.log("error", "AppStateService not available.")
            return

        interaction_mode = app_state_service.get_interaction_mode()
        app_state = app_state_service.get_app_state()

        workflow_coroutine = None
        if interaction_mode == InteractionMode.PLAN:
            workflow_coroutine = self._run_aura_workflow(prompt, conversation_history, image_bytes, image_media_type)
        elif interaction_mode == InteractionMode.BUILD:
            # Logic for custom non-Python prompts has been removed.
            # The architect service is now called directly without custom prompts.
            architect_service = self.service_manager.get_architect_service()
            if app_state == AppState.BOOTSTRAP:
                self._last_generated_code = None
                workflow_coroutine = architect_service.generate_or_modify(prompt, existing_files=None)
            elif app_state == AppState.MODIFY:
                existing_files = self.service_manager.get_project_manager().get_project_files()
                workflow_coroutine = architect_service.generate_or_modify(prompt, existing_files)
        else:
            self.log("error", f"Unknown interaction mode: {interaction_mode}")
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

    def _on_session_cleared(self):
        self._last_error_report = None
        self._last_generated_code = None
        self._is_plugin_override_active = False

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
        if not highlighted_text.strip():
            self.log("warning", "Fix requested for empty highlighted text.")
            return

        error_context_for_fix: str
        if self._last_error_report:
            error_context_for_fix = (
                f"User highlighted the following from the terminal output:\n--- HIGHLIGHTED TEXT ---\n{highlighted_text}\n--- END HIGHLIGHTED TEXT ---\n\n"
                f"This may be related to the last full error report from a failed command execution:\n--- LAST FULL ERROR ---\n{self._last_error_report}\n--- END LAST FULL ERROR ---"
            )
            self.log("info", "Fixing highlighted text with context from last full error report.")
        else:
            error_context_for_fix = (
                f"User highlighted the following error/text from the terminal output. This is the primary context for the fix:\n"
                f"--- HIGHLIGHTED TEXT ---\n{highlighted_text}\n--- END HIGHLIGHTED TEXT ---"
            )
            self.log("info", "Fixing highlighted text (no previous full error report stored).")

        self._initiate_fix_workflow(error_context_for_fix)

    def _initiate_fix_workflow(self, error_report: str):
        if not (self.service_manager and self.task_manager):
            self.log("error", "Cannot initiate fix: Core services not available.")
            return

        if self.window_manager and self.window_manager.get_code_viewer():
            self.window_manager.get_code_viewer().terminal.show_fixing_in_progress()

        validation_service = self.service_manager.get_validation_service()
        if validation_service:
            fix_coroutine = validation_service.review_and_fix_file(error_report)
            self.task_manager.start_ai_workflow_task(fix_coroutine)
        else:
            self.log("error", "ValidationService not available to initiate fix.")
            if self.window_manager and self.window_manager.get_code_viewer():
                self.window_manager.get_code_viewer().terminal.hide_fix_button()

    def log(self, level, message):
        self.event_bus.emit("log_message_received", "WorkflowManager", level, message)