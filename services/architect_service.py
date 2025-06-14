# kintsugi_ava/services/architect_service.py
import asyncio
import json
import re
import traceback
from pathlib import Path

from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.execution_engine import ExecutionEngine
from core.project_manager import ProjectManager
from prompts.prompts import (
    MODIFICATION_PLANNER_PROMPT, HIERARCHICAL_PLANNER_PROMPT,
    CODER_PROMPT, CODE_MODIFIER_PROMPT, REFINEMENT_PROMPT
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

    async def _generate_hierarchical_plan(self, prompt: str) -> dict:
        """Generates a structured, multi-file plan for a new project."""
        self.update_status("architect", "working", "Designing project structure...")
        rag_context = self.rag_service.query(prompt)
        plan_prompt = HIERARCHICAL_PLANNER_PROMPT.format(prompt=prompt, rag_context=rag_context)

        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("architect", "No model configured.")
            return {}

        raw_plan_response = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt)])

        try:
            plan = self._parse_json_response(raw_plan_response)
            if not plan.get("files"):
                raise ValueError("AI did not return a valid file plan.")
            self.update_status("architect", "success", f"Plan created: {len(plan['files'])} file(s).")
            return plan
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("architect", f"Hierarchical plan creation failed: {e}", raw_plan_response)
            return {}

    async def _execute_concurrent_generation(self, plan: dict, user_prompt_summary: str):
        """Generates all files in a plan concurrently and commits them in one go."""
        files_to_generate = plan.get("files", [])
        dependencies = plan.get("dependencies", [])
        generated_code_map = {}

        if dependencies:
            req_content = "\n".join(dependencies) + "\n"
            generated_code_map["requirements.txt"] = req_content

        code_files_to_generate = [f for f in files_to_generate if f.get("filename") != "requirements.txt"]
        self.event_bus.emit("prepare_for_generation", [f['filename'] for f in code_files_to_generate])
        await asyncio.sleep(0.1)

        generation_tasks = [
            self._generate_and_return_file(
                file_info['filename'],
                file_info['purpose'],
                plan
            ) for file_info in code_files_to_generate
        ]

        results = await asyncio.gather(*generation_tasks, return_exceptions=True)

        all_successful = True
        for res in results:
            if isinstance(res, Exception):
                self.handle_error("coder", f"A sub-task failed during concurrent generation: {res}")
                all_successful = False
            elif res:
                filename, content = res
                generated_code_map[filename] = content

        if not all_successful:
            return False

        self.event_bus.emit("code_generation_complete", generated_code_map)

        self.log("info", "All files generated. Committing project foundation...")
        self.project_manager.save_and_commit_files(generated_code_map, user_prompt_summary)
        self.log("success", "Project foundation committed successfully.")

        return True

    async def generate_or_modify(self, prompt: str, existing_files: dict = None):
        """The main entry point for the architect's workflow."""
        self.log("info", f"Task received: '{prompt}'")
        user_prompt_summary = f'AI generation for: "{prompt[:50]}..."'

        if not existing_files:
            plan = await self._generate_hierarchical_plan(prompt)
            if not plan: return

            generation_succeeded = await self._execute_concurrent_generation(plan, user_prompt_summary)
            if not generation_succeeded: return

        else:  # Modification of existing project
            self.update_status("architect", "working", "Creating modification plan...")
            plan_prompt = MODIFICATION_PLANNER_PROMPT.format(prompt=prompt,
                                                             existing_files_json=json.dumps(existing_files, indent=2))
            provider, model = self.llm_client.get_model_for_role("coder")
            if not provider or not model:
                self.handle_error("architect", "No model configured.")
                return

            raw_plan_response = "".join(
                [chunk async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt)])

            try:
                file_plan = self._parse_json_response(raw_plan_response).get("files", [])
                if not file_plan: raise ValueError("AI did not return a valid modification plan.")
                self.update_status("architect", "success", "Modification plan created.")
            except (json.JSONDecodeError, ValueError) as e:
                self.handle_error("architect", f"Modification plan creation failed: {e}", raw_plan_response)
                return

            self.event_bus.emit("prepare_for_generation", [f['filename'] for f in file_plan])
            await asyncio.sleep(0.1)

            all_steps_succeeded = True
            for file_info in file_plan:
                filename = file_info['filename']
                purpose = file_info['purpose']
                original_code = existing_files.get(filename)
                if original_code is None:
                    single_file_plan = {"files": [{"filename": filename, "purpose": purpose}], "dependencies": []}
                    content_tuple = await self._generate_and_return_file(filename, purpose, single_file_plan)
                    if content_tuple:
                        self.project_manager.save_and_commit_files({content_tuple[0]: content_tuple[1]},
                                                                   f"feat: Create {filename}")
                        self.event_bus.emit("code_generation_complete", {content_tuple[0]: content_tuple[1]})
                    else:
                        all_steps_succeeded = False
                else:
                    success = await self._generate_and_apply_patch(filename, purpose, original_code,
                                                                   user_prompt_summary)
                    if not success: all_steps_succeeded = False

                if not all_steps_succeeded:
                    self.handle_error("coder", f"Failed to process file: {filename}")
                    break

            if not all_steps_succeeded: return

        self.update_status("coder", "success", "Code generation/modification complete.")
        await self._validate_and_refine_loop()

    async def _generate_and_return_file(self, filename: str, purpose: str, file_plan: dict) -> tuple[str, str] | None:
        """Generates content for a single file and returns it, but does not save or commit."""
        self.update_status("coder", "working", f"Writing {filename}...")
        provider, model = self.llm_client.get_model_for_role("coder")
        code_prompt = CODER_PROMPT.format(file_plan_json=json.dumps(file_plan, indent=2), filename=filename,
                                          purpose=purpose)

        file_content = ""
        async for chunk in self.llm_client.stream_chat(provider, model, code_prompt):
            file_content += chunk
            self.event_bus.emit("stream_code_chunk", filename, chunk)

        cleaned_code = self._clean_code_output(file_content)
        self.log("info", f"Successfully generated content for {filename}")
        return (filename, cleaned_code)

    async def _generate_and_apply_patch(self, filename: str, purpose: str, original_code: str,
                                        commit_message: str) -> bool:
        """Generates and applies a patch for a single file."""
        provider, model = self.llm_client.get_model_for_role("coder")
        patch_prompt = CODE_MODIFIER_PROMPT.format(purpose=purpose, filename=filename, original_code=original_code)

        patch_content = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, patch_prompt)])
        cleaned_patch = self._clean_code_output(patch_content, is_diff=True)

        if not cleaned_patch:
            self.log("warning", f"AI returned an empty patch for {filename}. No changes made.")
            return True

        success = self.project_manager.patch_file(filename, cleaned_patch, commit_message)
        if success:
            updated_files = self.project_manager.get_project_files()
            if filename in updated_files:
                self.event_bus.emit("code_patched", filename, updated_files[filename], cleaned_patch)
            return True
        else:
            self.log("error", f"A patch generated for {filename} was invalid.")
            return False

    def _parse_error_traceback(self, error_str: str) -> tuple[str | None, int | None]:
        """Parses a traceback string to find the file and line number within the project."""
        if not self.project_manager.active_project_path:
            return None, None

        # Regex to find 'File "path/to/file.py", line 123'
        # It now captures the file path and line number
        traceback_lines = re.findall(r'File "([^"]+)", line (\d+)', error_str)

        # Iterate backwards through the traceback to find the most recent call in our project
        for file_path_str, line_num_str in reversed(traceback_lines):
            file_path = Path(file_path_str)
            try:
                # Check if the file from the traceback is within our active project directory
                if self.project_manager.active_project_path in file_path.resolve().parents:
                    relative_path_str = str(file_path.relative_to(self.project_manager.active_project_path))
                    self.log("info", f"Pinpointed error in project file: {relative_path_str} at line {line_num_str}")
                    return relative_path_str, int(line_num_str)
            except (ValueError, FileNotFoundError):
                # This can happen if the path is not relative to the project, which is fine.
                continue

        self.log("warning", "Could not pinpoint error to a specific project file. Will default to main.py.")
        return None, None

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

            self.update_status("executor", "error", "Validation failed.")

            # --- THE FIX: SMART ERROR PARSING ---
            all_project_files = self.project_manager.get_project_files()
            file_to_fix, line_number = self._parse_error_traceback(exec_result.error)

            # Fallback to main.py if parsing fails or error is outside project files
            if not file_to_fix or not line_number:
                file_to_fix = "main.py"
                line_number = 1

            if file_to_fix not in all_project_files:
                self.handle_error("executor", f"Could not find file '{file_to_fix}' to apply fix.")
                return

            self.update_status("reviewer", "working", f"Attempting to fix {file_to_fix}...")
            broken_code = all_project_files.get(file_to_fix, "")

            fix_patch = await self.reviewer_service.review_and_correct_code(
                file_to_fix, broken_code, exec_result.error, line_number
            )
            # --- END FIX ---

            if not fix_patch:
                self.handle_error("reviewer", f"Could not generate a fix for {file_to_fix}.")
                # If it fails, break the loop for this file and let the outer error handler take over.
                break

            fix_commit_message = f"fix: AI Reviewer fix for {file_to_fix} after error"
            patch_success = self.project_manager.patch_file(file_to_fix, fix_patch, fix_commit_message)

            if patch_success:
                updated_files = self.project_manager.get_project_files()
                self.event_bus.emit("code_patched", file_to_fix, updated_files.get(file_to_fix, ""), fix_patch)
                self.update_status("reviewer", "success", "Fix implemented. Re-validating...")
            else:
                self.handle_error("reviewer", f"Generated fix for {file_to_fix} was invalid and could not be applied.")
                # Break the loop if the patch is bad.
                break

        # If the loop finishes without success, then we declare failure.
        else:
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