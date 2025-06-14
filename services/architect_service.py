# kintsugi_ava/services/architect_service.py
# V3: Refactored to delegate validation to the new ValidationService.

import asyncio
import json
from pathlib import Path

from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.project_manager import ProjectManager
from prompts.prompts import (
    MODIFICATION_PLANNER_PROMPT, HIERARCHICAL_PLANNER_PROMPT,
    CODER_PROMPT, CODE_MODIFIER_PROMPT
)
from services.rag_service import RAGService


class ArchitectService:
    """
    Handles the AI-driven planning and code generation/modification process.
    Its single responsibility is to interpret the user's request and
    produce the initial code, but it does not validate or execute it.
    """

    def __init__(self, event_bus: EventBus, llm_client: LLMClient, project_manager: ProjectManager,
                 rag_service: RAGService):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.project_manager = project_manager
        self.rag_service = rag_service

    async def _generate_hierarchical_plan(self, prompt: str) -> dict | None:
        """Generates a structured, multi-file plan for a new project."""
        self.update_status("architect", "working", "Designing project structure...")
        rag_context = self.rag_service.query(prompt)
        plan_prompt = HIERARCHICAL_PLANNER_PROMPT.format(prompt=prompt, rag_context=rag_context)

        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("architect", "No model configured.")
            return None

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
            return None

    async def _execute_concurrent_generation(self, plan: dict, user_prompt_summary: str) -> bool:
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

        self.update_status("coder", "working", f"Writing {len(code_files_to_generate)} files...")

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

        if self.project_manager.active_project_path:
            self.event_bus.emit("project_creation_finished", str(self.project_manager.active_project_path))

        return True

    async def generate_or_modify(self, prompt: str, existing_files: dict | None) -> bool:
        """
        The main entry point for the architect's workflow. Returns True on success.
        """
        self.log("info", f"Task received: '{prompt}'")
        user_prompt_summary = f'AI generation for: "{prompt[:50]}..."'
        success = False

        if not existing_files:
            plan = await self._generate_hierarchical_plan(prompt)
            if plan:
                success = await self._execute_concurrent_generation(plan, user_prompt_summary)
        else:
            success = await self._handle_modification(prompt, existing_files, user_prompt_summary)

        if success:
            self.update_status("coder", "success", "Code generation/modification complete.")

        return success

    async def _handle_modification(self, prompt: str, existing_files: dict, user_prompt_summary: str) -> bool:
        """Handles the logic for modifying an existing project."""
        self.update_status("architect", "working", "Creating modification plan...")
        plan_prompt = MODIFICATION_PLANNER_PROMPT.format(prompt=prompt,
                                                         existing_files_json=json.dumps(existing_files, indent=2))
        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("architect", "No model configured.")
            return False

        raw_plan_response = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt)])

        try:
            file_plan = self._parse_json_response(raw_plan_response).get("files", [])
            if not file_plan: raise ValueError("AI did not return a valid modification plan.")
            self.update_status("architect", "success", "Modification plan created.")
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("architect", f"Modification plan creation failed: {e}", raw_plan_response)
            return False

        self.event_bus.emit("prepare_for_generation", [f['filename'] for f in file_plan])
        await asyncio.sleep(0.1)

        for file_info in file_plan:
            filename = file_info['filename']
            purpose = file_info['purpose']
            original_code = existing_files.get(filename)

            step_succeeded = False
            if original_code is None:  # New file in existing project
                self.update_status("coder", "working", f"Writing new file: {filename}...")
                single_file_plan = {"files": [{"filename": filename, "purpose": purpose}], "dependencies": []}
                content_tuple = await self._generate_and_return_file(filename, purpose, single_file_plan)
                if content_tuple:
                    self.project_manager.save_and_commit_files({content_tuple[0]: content_tuple[1]},
                                                               f"feat: Create {filename}")
                    self.event_bus.emit("code_generation_complete", {content_tuple[0]: content_tuple[1]})
                    step_succeeded = True
            else:  # Modifying existing file
                step_succeeded = await self._generate_and_apply_patch(filename, purpose, original_code,
                                                                      user_prompt_summary)
            if not step_succeeded:
                self.handle_error("coder", f"Failed to process file: {filename}")
                return False  # Halt on first failure

        return True

    async def _generate_and_return_file(self, filename: str, purpose: str, file_plan: dict) -> tuple[str, str] | None:
        """Generates content for a single file and returns it."""
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
        self.update_status("coder", "working", f"Patching {filename}...")
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

    def _parse_json_response(self, response: str) -> dict:
        """Cleans and parses a JSON string from an AI response."""
        cleaned_response = self._clean_json_output(response)
        return json.loads(cleaned_response)

    def _clean_json_output(self, response: str) -> str:
        """Strips markdown and other clutter from a JSON AI response."""
        response = response.strip()
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end != 0:
            return response[json_start:json_end]
        raise ValueError("No valid JSON object found in AI's response.")

    def _clean_code_output(self, code: str, is_diff: bool = False) -> str:
        """Strips markdown code fences from a code block or diff."""
        code = code.strip()
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