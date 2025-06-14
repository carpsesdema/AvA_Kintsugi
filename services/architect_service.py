# kintsugi_ava/services/architect_service.py
# V11: Fixed major performance bug in generation loop.

import asyncio
import json
import re
from pathlib import Path

from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.project_manager import ProjectManager
from prompts.prompts import (
    MODIFICATION_PLANNER_PROMPT, HIERARCHICAL_PLANNER_PROMPT,
    CODER_PROMPT
)
from services.rag_service import RAGService
from utils.code_summarizer import CodeSummarizer


class ArchitectService:
    """
    Handles the AI-driven planning and code generation/modification process.
    Uses architect role for planning, coder role for actual code generation.
    """

    def __init__(self, event_bus: EventBus, llm_client: LLMClient, project_manager: ProjectManager,
                 rag_service: RAGService):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.project_manager = project_manager
        self.rag_service = rag_service

    async def generate_or_modify(self, prompt: str, existing_files: dict | None) -> bool:
        """Determines whether to start a new project or modify an existing one."""
        self.log("info", f"Task received: '{prompt}'")
        success = False
        if not existing_files:
            plan = await self._generate_hierarchical_plan(prompt)
            if plan:
                success = await self._execute_artisanal_generation(plan)
        else:
            # For modifications, we'll need a different flow.
            # For now, let's assume we can get a plan and regenerate files.
            self.log("info", "Modification of existing project is not fully implemented yet.")
            success = False  # Placeholder

        if success:
            self.update_status("coder", "success", "Code generation complete.")
        return success

    async def _generate_hierarchical_plan(self, prompt: str) -> dict | None:
        """Generates a structured, multi-file plan for a new project."""
        self.update_status("architect", "working", "Designing project structure...")
        rag_context = self.rag_service.query(prompt)
        plan_prompt = HIERARCHICAL_PLANNER_PROMPT.format(prompt=prompt, rag_context=rag_context)

        provider, model = self.llm_client.get_model_for_role("architect")
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
        Generates all files in-memory first, then saves and commits them all
        at once for maximum performance.
        """
        files_to_generate = plan.get("files", [])
        dependencies = plan.get("dependencies", [])

        all_filenames = [f['filename'] for f in files_to_generate]
        if dependencies and "requirements.txt" not in all_filenames:
            all_filenames.append("requirements.txt")

        project_path = str(self.project_manager.active_project_path)
        self.event_bus.emit("prepare_for_generation", all_filenames, project_path)
        await asyncio.sleep(0.1)  # Give UI time to prepare

        # --- NEW: In-memory dictionary to hold all generated code ---
        generated_files = {}
        summarized_context = {}  # We'll still build this for the prompt, but without file I/O

        # Handle requirements.txt first
        if dependencies:
            self.update_status("coder", "working", "Preparing requirements.txt...")
            req_content = "\n".join(dependencies) + "\n"
            generated_files["requirements.txt"] = req_content
            # This event updates the editor tab with the final content
            self.event_bus.emit("code_generation_complete", {"requirements.txt": req_content})
            summarized_context["requirements.txt"] = "File containing project dependencies."

        # Now generate the actual code files
        code_files_to_generate = [f for f in files_to_generate if f.get("filename") != "requirements.txt"]

        for file_info in code_files_to_generate:
            filename = file_info['filename']
            purpose = file_info['purpose']
            self.update_status("coder", "working", f"Writing {filename}...")

            # Generate the file content using our existing helper function
            file_content = await self._generate_one_file_with_context(plan, filename, purpose, summarized_context)

            if file_content is None:
                self.handle_error("coder", f"Failed to generate content for {filename}.")
                return False

            # Add the generated content to our dictionary
            generated_files[filename] = file_content
            self.log("info", f"Successfully generated content for {filename}.")

            # Update the UI with the completed file content
            self.event_bus.emit("code_generation_complete", {filename: file_content})

            # Update the context for the NEXT file generation, but without slow parsing.
            # We just signal that the file exists and the plan describes its purpose.
            summarized_context[filename] = f"File '{filename}' is being generated. Purpose: {purpose}"

        # --- THE BIG FINALE ---
        # Now that ALL files are generated in memory, save and commit them in one go.
        self.log("success", "Code generation complete. Saving all files to disk...")
        self.update_status("coder", "working", "Saving files...")

        self.project_manager.save_and_commit_files(generated_files, "feat: Initial project generation")

        self.log("success", "Project foundation committed successfully.")
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
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            return match.group(0)
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