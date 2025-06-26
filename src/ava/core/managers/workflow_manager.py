# src/ava/core/managers/workflow_manager.py
import asyncio
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox
from typing import Optional, Dict

from src.ava.core.event_bus import EventBus
from src.ava.core.app_state import AppState
from src.ava.core.interaction_mode import InteractionMode
from src.ava.core.managers.service_manager import ServiceManager
from src.ava.core.managers.window_manager import WindowManager
from src.ava.core.managers.task_manager import TaskManager


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

    def handle_user_request(self, prompt: str, conversation_history: list,
                            image_bytes: Optional[bytes] = None, image_media_type: Optional[str] = None,
                            code_context: Optional[Dict[str, str]] = None):
        """The central router for all user chat input, now with multimodal and code context support."""
        stripped_prompt = prompt.strip()
        if not stripped_prompt and not image_bytes and not code_context:
            return

        app_state_service = self.service_manager.get_app_state_service()
        if not app_state_service:
            self.log("error", "AppStateService not available.")
            return

        interaction_mode = app_state_service.get_interaction_mode()
        app_state = app_state_service.get_app_state()

        if stripped_prompt.startswith('/'):
            self._handle_slash_command(stripped_prompt, app_state_service)
            return

        workflow_coroutine = None
        if interaction_mode == InteractionMode.CHAT:
            print("[WorkflowManager] Mode is CHAT. Starting general chat workflow...")
            workflow_coroutine = self._run_chat_workflow(prompt, conversation_history, image_bytes, image_media_type,
                                                         code_context)
        elif interaction_mode == InteractionMode.BUILD:
            if app_state == AppState.BOOTSTRAP:
                print("[WorkflowManager] Mode is BUILD, State is BOOTSTRAP. Starting new project workflow...")
                workflow_coroutine = self._run_bootstrap_workflow(prompt, image_bytes)
            elif app_state == AppState.MODIFY:
                print("[WorkflowManager] Mode is BUILD, State is MODIFY. Starting modification workflow...")
                workflow_coroutine = self._run_modification_workflow(prompt, image_bytes)
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

    async def _run_chat_workflow(self, prompt: str, conversation_history: list,
                                 image_bytes: Optional[bytes], image_media_type: Optional[str],
                                 code_context: Optional[Dict[str, str]]):
        """Runs a simple, streaming chat interaction with the LLM, now with history, RAG, and image support."""
        if not self.service_manager: return
        llm_client = self.service_manager.get_llm_client()
        provider, model = llm_client.get_model_for_role("chat")

        if not provider or not model:
            self.event_bus.emit("streaming_chunk", "Sorry, no 'chat' model is configured.")
            return

        final_prompt_parts = []
        if code_context:
            filename, content = list(code_context.items())[0]
            final_prompt_parts.append(
                f"Please analyze the following code from the file `{filename}`.\n--- CODE ---\n```python\n{content}\n```\n--- END CODE ---")

        rag_manager = self.service_manager.get_rag_manager()
        if rag_manager and rag_manager.rag_service:  # Ensure rag_service is available
            rag_query = prompt or "Summarize the attached code based on project documents or general knowledge."

            # Query project-specific RAG
            project_rag_context = await rag_manager.rag_service.query(rag_query, target_collection="project")
            if project_rag_context and "no relevant documents found" not in project_rag_context.lower() and "not running or is unreachable" not in project_rag_context.lower():
                final_prompt_parts.append(
                    f"USE THE FOLLOWING PROJECT-SPECIFIC CONTEXT TO INFORM YOUR ANSWER:\n--- PROJECT CONTEXT ---\n{project_rag_context}\n--- END PROJECT CONTEXT ---")

            # Query global RAG
            global_rag_context = await rag_manager.rag_service.query(rag_query, target_collection="global")
            if global_rag_context and "no relevant documents found" not in global_rag_context.lower() and "not running or is unreachable" not in global_rag_context.lower():
                final_prompt_parts.append(
                    f"USE THE FOLLOWING GENERAL PYTHON EXAMPLES & BEST PRACTICES (GLOBAL CONTEXT) TO INFORM YOUR ANSWER:\n--- GLOBAL CONTEXT ---\n{global_rag_context}\n--- END GLOBAL CONTEXT ---")

        else:
            self.log("warning", "RAGManager or RAGService not available for chat workflow.")

        final_prompt_parts.append(f"User's Question: {prompt if prompt else 'Please review the attached code.'}")
        final_prompt = "\n\n".join(final_prompt_parts)

        chat_prompt_for_llm = final_prompt
        if not prompt and image_bytes and not code_context:  # If only an image is provided
            chat_prompt_for_llm = "Describe this image in detail."
        elif not prompt and not image_bytes and code_context:  # If only code context is provided
            chat_prompt_for_llm = final_prompt  # The prompt already includes the code

        self.event_bus.emit("streaming_start", "Kintsugi AvA")
        try:
            stream = llm_client.stream_chat(
                provider, model, chat_prompt_for_llm, "chat",
                image_bytes, image_media_type, history=conversation_history
            )
            async for chunk in stream:
                self.event_bus.emit("streaming_chunk", chunk)
        except Exception as e:
            self.event_bus.emit("streaming_chunk", f"\n\nAn error occurred: {e}")
            self.log("error", f"Error during chat streaming: {e}")  # Log the error
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

        app_state_service = self.service_manager.get_app_state_service()
        app_state_service.set_app_state(AppState.BOOTSTRAP)

        project_path = project_manager.new_project("New_AI_Project")
        if not project_path:
            QMessageBox.critical(None, "Project Creation Failed", "Could not create temporary project directory.")
            return

        # Switch RAG context to this new project (it will be empty initially)
        rag_manager = self.service_manager.get_rag_manager()
        if rag_manager:
            await rag_manager.switch_project_context(Path(project_path))

        architect_service = self.service_manager.get_architect_service()
        # generate_or_modify in ArchitectService will now handle querying both RAGs
        generation_success = await architect_service.generate_or_modify(final_prompt, existing_files=None)

        if generation_success:
            self.log("info", "Bootstrap generation successful. Transitioning to MODIFY state.")
            app_state_service.set_app_state(AppState.MODIFY, project_manager.active_project_name)
        else:
            self.log("error", "Bootstrap generation failed. Remaining in BOOTSTRAP state.")

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
        # generate_or_modify in ArchitectService will now handle querying both RAGs
        await architect_service.generate_or_modify(final_prompt, existing_files)

    def _handle_slash_command(self, command: str, app_state_service):
        parts = command.strip().split(' ', 1)
        command_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        if command_name == "/new":
            if not args:
                self.log("warning", "Usage: /new <description of new project>")
                return
            app_state_service.set_interaction_mode(InteractionMode.BUILD)
            self.task_manager.start_ai_workflow_task(self._run_bootstrap_workflow(args))
        elif command_name == "/build":
            app_state_service.set_interaction_mode(InteractionMode.BUILD)
        elif command_name == "/chat":
            app_state_service.set_interaction_mode(InteractionMode.CHAT)
        else:
            self.log("error", f"Unknown command: {command_name}")

    def _on_session_cleared(self):
        """Resets the state of this manager when a new session is started."""
        self._last_error_report = None

    def handle_execution_failed(self, error_report: str):
        self._last_error_report = error_report
        if self.window_manager and self.window_manager.get_code_viewer():
            self.window_manager.get_code_viewer().show_fix_button()

    def handle_review_and_fix_button(self):
        """Handles the "Review & Fix" button click from the UI."""
        if self._last_error_report:
            self._initiate_fix_workflow(self._last_error_report)
        else:
            self.log("warning", "Fix button clicked but no error report was available.")

    def handle_review_and_fix_request(self, error_report: str):
        """Handles a fix request from a plugin or other internal service."""
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