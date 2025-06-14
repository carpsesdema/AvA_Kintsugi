# kintsugi_ava/services/architect_service.py
# V9: Simplified with diff/patch system removed - only full file generation and replacement.

import asyncio
import json
from pathlib import Path

from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.project_manager import ProjectManager
from prompts.prompts import (
    MODIFICATION_PLANNER_PROMPT, HIERARCHICAL_PLANNER_PROMPT,
    CODER_PROMPT, REFINEMENT_PROMPT
)
from services.rag_service import RAGService
from utils.code_summarizer import CodeSummarizer


class ArchitectService:
    """
    Handles the AI-driven planning and code generation/modification process.
    Simplified to use only full file generation - no more complex patch system.
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

    async def _execute_artisanal_generation(self, plan: dict) -> bool:
        """
        Generates files one by one, providing a summarized context of completed
        files to maintain high performance.
        """
        files_to_generate = plan.get("files", [])
        dependencies = plan.get("dependencies", [])

        all_filenames = [f['filename'] for f in files_to_generate]
        if dependencies:
            all_filenames.append("requirements.txt")

        project_path = str(self.project_manager.active_project_path)
        self.event_bus.emit("prepare_for_generation", all_filenames, project_path)
        await asyncio.sleep(0.1)

        if dependencies:
            self.update_status("coder", "working", "Writing requirements.txt...")
            req_content = "\n".join(dependencies) + "\n"
            self.project_manager.save_and_commit_files({"requirements.txt": req_content}, "feat: Add dependencies")
            self.event_bus.emit("code_generation_complete", {"requirements.txt": req_content})

        code_files_to_generate = [f for f in files_to_generate if f.get("filename") != "requirements.txt"]

        for file_info in code_files_to_generate:
            filename = file_info['filename']
            purpose = file_info['purpose']
            self.update_status("coder", "working", f"Writing {filename}...")

            completed_files = self.project_manager.get_project_files()
            summarized_context = {}
            for fname, content in completed_files.items():
                if fname.endswith('.py'):
                    summarizer = CodeSummarizer(content)
                    summarized_context[fname] = summarizer.summarize()
                else:
                    summarized_context[fname] = f"File exists: {fname}"

            file_content = await self._generate_one_file_with_context(plan, filename, purpose, summarized_context)

            if file_content is None:
                self.handle_error("coder", f"Failed to generate content for {filename}.")
                return False

            self.project_manager.save_and_commit_files({filename: file_content}, f"feat: Create {filename}")
            self.event_bus.emit("code_generation_complete", {filename: file_content})
            self.log("info", f"Successfully generated and committed {filename}.")

        self.log("success", "Project foundation committed successfully.")
        return True

    async def generate_or_modify(self, prompt: str, existing_files: dict | None) -> bool:
        self.log("info", f"Task received: '{prompt}'")
        success = False
        if not existing_files:
            plan = await self._generate_hierarchical_plan(prompt)
            if plan: success = await self._execute_artisanal_generation(plan)
        else:
            user_prompt_summary = f'AI generation for: "{prompt[:50]}..."'
            success = await self._handle_modification(prompt, existing_files, user_prompt_summary)
        if success: self.update_status("coder", "success", "Code generation/modification complete.")
        return success

    async def _handle_modification(self, prompt: str, existing_files: dict, user_prompt_summary: str) -> bool:
        """Handles modifications using full file replacement instead of patches."""
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

        # Prepare for modifications - no project path since we're modifying existing
        self.event_bus.emit("prepare_for_generation", [f['filename'] for f in file_plan])
        await asyncio.sleep(0.1)

        for file_info in file_plan:
            filename, purpose = file_info['filename'], file_info['purpose']
            original_code = self.project_manager.get_project_files().get(filename)

            if original_code is None:
                # New file creation
                self.update_status("coder", "working", f"Writing new file: {filename}...")
                completed_files = self.project_manager.get_project_files()
                summarized_context = {fname: CodeSummarizer(content).summarize() for fname, content in
                                      completed_files.items() if fname.endswith('.py')}
                file_content = await self._generate_one_file_with_context(file_plan, filename, purpose,
                                                                          summarized_context)
                if file_content:
                    self.project_manager.save_and_commit_files({filename: file_content}, f"feat: Create {filename}")
                    self.event_bus.emit("code_generation_complete", {filename: file_content})
                else:
                    self.handle_error("coder", f"Failed to create new file: {filename}")
                    return False
            else:
                # File modification using full replacement
                if not await self._generate_and_replace_file(filename, purpose, original_code, user_prompt_summary):
                    self.handle_error("coder", f"Failed to modify file: {filename}")
                    return False

        return True

    async def _generate_and_replace_file(self, filename: str, purpose: str, original_code: str,
                                         commit_message: str) -> bool:
        """Generates a complete replacement for an existing file."""
        self.update_status("coder", "working", f"Rewriting {filename}...")

        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("coder", "No model configured.")
            return False

        # Use the refinement prompt which asks for complete file replacement
        replacement_prompt = REFINEMENT_PROMPT.format(
            filename=filename,
            line_number=1,  # Not relevant for full replacement
            code=original_code,
            error=f"User requested modification: {purpose}"
        )

        new_content = ""
        async for chunk in self.llm_client.stream_chat(provider, model, replacement_prompt):
            new_content += chunk
            self.event_bus.emit("stream_code_chunk", filename, chunk)

        cleaned_content = self._clean_code_output(new_content)
        if not cleaned_content:
            self.log("warning", f"AI returned empty content for {filename}.")
            return False

        # Save the complete new file
        self.project_manager.save_and_commit_files({filename: cleaned_content}, commit_message)

        # Update the UI
        self.event_bus.emit("code_generation_complete", {filename: cleaned_content})

        self.log("info", f"Successfully replaced {filename}")
        return True

    async def _generate_one_file_with_context(self, plan: dict, filename: str, purpose: str,
                                              summarized_context: dict) -> str | None:
        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("coder", "No model configured.")
            return None

        code_prompt = CODER_PROMPT.format(
            file_plan_json=json.dumps(plan, indent=2),
            code_summaries_json=json.dumps(summarized_context, indent=2),
            filename=filename,
            purpose=purpose
        )

        file_content = ""
        async for chunk in self.llm_client.stream_chat(provider, model, code_prompt):
            file_content += chunk
            self.event_bus.emit("stream_code_chunk", filename, chunk)
        return self._clean_code_output(file_content)

    def _parse_json_response(self, response: str) -> dict:
        cleaned_response = self._clean_json_output(response)
        return json.loads(cleaned_response)

    def _clean_json_output(self, response: str) -> str:
        response = response.strip()
        json_start, json_end = response.find('{'), response.rfind('}') + 1
        if json_start != -1 and json_end != 0: return response[json_start:json_end]
        raise ValueError("No valid JSON object found in AI's response.")

    def _clean_code_output(self, code: str) -> str:
        """Cleans code output by removing markdown formatting."""
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):].lstrip()
        elif code.startswith("```"):
            code = code[3:].lstrip()
        if code.endswith("```"):
            code = code[:-3].rstrip()
        return code.strip()

    def handle_error(self, agent: str, error_msg: str, response: str = ""):
        self.update_status(agent, "error", "Failed")
        self.log("error", f"{agent} failed: {error_msg}\nResponse: {response}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed. Error: {error_msg}")

    def update_status(self, agent_id: str, status: str, text: str):
        self.event_bus.emit("node_status_changed", agent_id, status, text)
        if status != "working": self.log("info", f"{agent_id.title()} status: {status} - {text}")

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ArchitectService", message_type, content)