# kintsugi_ava/services/architect_service.py
# V24: Unifies the refinement loop to use patches from the ReviewerService.

import asyncio
import json
from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.execution_engine import ExecutionEngine
from core.project_manager import ProjectManager
from prompts.prompts import (
    PLANNER_PROMPT, MODIFICATION_PLANNER_PROMPT, CODER_PROMPT, CODE_MODIFIER_PROMPT
)
from services.reviewer_service import ReviewerService
from services.rag_service import RAGService


class ArchitectService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient, project_manager: ProjectManager,
                 rag_service: RAGService):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.project_manager = project_manager
        self.execution_engine = ExecutionEngine(self.project_manager)
        self.reviewer_service = ReviewerService(event_bus, llm_client)
        self.rag_service = rag_service
        self.MAX_REFINEMENT_ATTEMPTS = 3

    async def generate_or_modify(self, prompt: str, existing_files: dict = None):
        self.log("info", f"Task received: '{prompt}'")
        user_prompt_summary = f'AI generation for: "{prompt[:50]}..."'

        # --- STEP 1: Plan ---
        self.update_status("architect", "working", "Creating a plan...")
        plan_prompt = ""
        if existing_files:
            plan_prompt = MODIFICATION_PLANNER_PROMPT.format(prompt=prompt,
                                                             existing_files_json=json.dumps(existing_files, indent=2))
        else:
            rag_context = self.rag_service.query(prompt)
            plan_prompt = PLANNER_PROMPT.format(prompt=prompt, rag_context=rag_context)

        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("architect", "No model configured.")
            return

        raw_plan_response = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt)])

        try:
            file_plan = self._parse_json_response(raw_plan_response).get("files", [])
            if not file_plan: raise ValueError("AI did not return a valid file plan.")
            self.update_status("architect", "success", f"Plan created: {len(file_plan)} file(s).")
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("architect", f"Plan creation failed: {e}", raw_plan_response)
            return

        # --- STEP 2: Execute Plan (Create, Modify, or Patch) ---
        files_for_viewer = [f['filename'] for f in file_plan]
        self.event_bus.emit("prepare_for_generation", files_for_viewer)
        await asyncio.sleep(0.1)

        all_steps_succeeded = True
        for file_info in file_plan:
            filename = file_info['filename']
            purpose = file_info['purpose']

            step_success = False
            if existing_files and filename in existing_files:
                self.update_status("coder", "working", f"Modifying {filename}...")
                step_success = await self._generate_and_apply_patch(filename, purpose, existing_files[filename],
                                                                    user_prompt_summary)
            else:
                self.update_status("coder", "working", f"Creating {filename}...")
                step_success = await self._generate_new_file(filename, purpose, file_plan, user_prompt_summary)

            if not step_success:
                all_steps_succeeded = False
                self.handle_error("coder", f"Failed to process file: {filename}")
                break

        if not all_steps_succeeded:
            return

        self.update_status("coder", "success", "Code generation/modification complete.")

        # --- STEP 3: Validate and Refine ---
        await self._validate_and_refine_loop()

    async def _generate_new_file(self, filename: str, purpose: str, file_plan: list, commit_message: str) -> bool:
        """Generates a new file from scratch and saves it. Returns success status."""
        provider, model = self.llm_client.get_model_for_role("coder")
        code_prompt = CODER_PROMPT.format(file_plan=json.dumps(file_plan), filename=filename, purpose=purpose)

        file_content = ""
        async for chunk in self.llm_client.stream_chat(provider, model, code_prompt):
            file_content += chunk
            self.event_bus.emit("stream_code_chunk", filename, chunk)

        cleaned_code = self._clean_code_output(file_content)
        self.project_manager.save_and_commit_files({filename: cleaned_code}, commit_message)
        self.event_bus.emit("code_generation_complete", {filename: cleaned_code})
        return True

    async def _generate_and_apply_patch(self, filename: str, purpose: str, original_code: str,
                                        commit_message: str) -> bool:
        """Generates a diff patch, applies it, and emits data. Returns success status."""
        provider, model = self.llm_client.get_model_for_role("coder")
        patch_prompt = CODE_MODIFIER_PROMPT.format(purpose=purpose, filename=filename, original_code=original_code)

        patch_content = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, patch_prompt)])
        cleaned_patch = self._clean_code_output(patch_content, is_diff=True)

        if not cleaned_patch:
            self.log("warning", f"AI did not return a patch for {filename}. Skipping modification.")
            return True

        success = self.project_manager.patch_file(filename, cleaned_patch, commit_message)

        if success:
            updated_files = self.project_manager.get_project_files()
            if filename in updated_files:
                self.event_bus.emit("code_patched", filename, updated_files[filename], cleaned_patch)
            else:
                self.log("warning", f"Patch applied to {filename}, but could not re-read the file.")
            return True
        else:
            self.log("error", f"A patch generated for {filename} was invalid and could not be applied.")
            return False

    async def _validate_and_refine_loop(self):
        """The self-correction loop that runs and fixes the code using patches."""
        for attempt in range(self.MAX_REFINEMENT_ATTEMPTS):
            self.update_status("executor", "working", f"Validating... (Attempt {attempt + 1})")
            exec_result = self.execution_engine.run_main_in_project()

            if exec_result.success:
                self.update_status("executor", "success", "Validation passed!")
                success_message = "Modifications complete and successfully tested!" if self.project_manager.is_existing_project else "Application generated and successfully tested!"
                self.event_bus.emit("ai_response_ready", success_message)
                return

            # --- THE FIX ---
            # The refinement loop is now fully patch-based.
            self.update_status("executor", "error", "Validation failed.")
            all_project_files = self.project_manager.get_project_files()
            main_py_path = "main.py"
            if main_py_path not in all_project_files:
                self.handle_error("executor", "Could not find main.py to fix.")
                return

            self.update_status("reviewer", "working", "Attempting to fix code...")
            broken_code = all_project_files.get(main_py_path, "")

            # The reviewer now returns a patch, not the full code.
            fix_patch = await self.reviewer_service.review_and_correct_code(main_py_path, broken_code,
                                                                            exec_result.error)

            if not fix_patch:
                self.handle_error("reviewer", f"Could not generate a fix for {main_py_path}.")
                return

            # Apply the reviewer's patch using the ProjectManager.
            fix_commit_message = f"AI Reviewer fix after error: {exec_result.error.strip().splitlines()[-1]}"
            patch_success = self.project_manager.patch_file(main_py_path, fix_patch, fix_commit_message)

            if patch_success:
                # Emit the patched event so the UI can highlight the reviewer's changes.
                updated_files = self.project_manager.get_project_files()
                self.event_bus.emit("code_patched", main_py_path, updated_files.get(main_py_path, ""), fix_patch)
                self.update_status("reviewer", "success", "Fix implemented. Re-validating...")
            else:
                self.handle_error("reviewer", f"Generated fix for {main_py_path} was invalid and could not be applied.")
                return
            # --- END OF FIX ---

        self.handle_error("executor", "Could not fix the code after several attempts.")

    def _parse_json_response(self, response: str) -> dict:
        """Cleans and parses a JSON string from an AI response."""
        cleaned_response = self._clean_json_output(response, is_json=True)
        return json.loads(cleaned_response)

    def _clean_json_output(self, response: str, is_json: bool = False) -> str:
        """Strips markdown and other clutter from an AI response."""
        response = response.strip()
        if is_json:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                return response[json_start:json_end]
            raise ValueError("No valid JSON object found in AI's response.")
        return response

    def _clean_code_output(self, code: str, is_diff: bool = False) -> str:
        """Strips markdown code fences from a code block or diff."""
        code = self._clean_json_output(code, is_json=False)
        start_marker = "```diff" if is_diff else "```python"

        if code.startswith(start_marker):
            code = code[len(start_marker):].lstrip()
        elif code.startswith("```"):
            code = code[3:].lstrip()
            if is_diff and code.lstrip().startswith('diff'):
                code = code.lstrip()[4:].lstrip()

        if code.endswith("```"):
            code = code[:-3].rstrip()

        return code.strip()

    def handle_error(self, agent: str, error_msg: str, response: str = ""):
        """Centralized error reporting."""
        self.update_status(agent, "error", "Failed")
        self.log("error", f"{agent} failed: {error_msg}\nResponse: {response}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed. Error: {error_msg}")

    def update_status(self, agent_id: str, status: str, text: str):
        """Updates the visual status of a node in the workflow monitor."""
        self.event_bus.emit("node_status_changed", agent_id, status, text)
        if status != "working":
            self.log("info", f"{agent_id.title()} status: {status} - {text}")

    def log(self, message_type: str, content: str):
        """Emits a log message to the event bus."""
        self.event_bus.emit("log_message_received", "ArchitectService", message_type, content)