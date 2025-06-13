# kintsugi_ava/services/architect_service.py
# V16: Injects RAGService for context-aware planning.

import asyncio
import json
from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.execution_engine import ExecutionEngine
from core.project_manager import ProjectManager
from prompts.prompts import PLANNER_PROMPT, MODIFICATION_PLANNER_PROMPT, CODER_PROMPT
from services.reviewer_service import ReviewerService
from services.rag_service import RAGService


class ArchitectService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient, project_manager: ProjectManager, rag_service: RAGService):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.project_manager = project_manager
        self.execution_engine = ExecutionEngine(self.project_manager)
        self.reviewer_service = ReviewerService(event_bus, llm_client)
        self.rag_service = rag_service # Use the injected service
        self.MAX_REFINEMENT_ATTEMPTS = 3

    async def generate_or_modify(self, prompt: str, existing_files: dict = None):
        """
        The main entry point for the service. It can either generate a new
        project or modify an existing one based on the provided context.
        """
        self.log("info", f"Task received: '{prompt}'")

        # --- STEP 1: Plan the project ---
        plan_prompt = ""
        if existing_files:
            self.log("info",
                     f"Existing project context detected ({len(existing_files)} files). Planning modifications.")
            self.update_status("architect", "working", "Planning modifications...")
            # Use the specialized modification prompt
            plan_prompt = MODIFICATION_PLANNER_PROMPT.format(prompt=prompt,
                                                             existing_files_json=json.dumps(existing_files, indent=2))
        else:
            self.log("info", "No existing project. Planning from scratch.")
            self.update_status("architect", "working", "Querying RAG & designing plan...")
            # Use the standard planner prompt with RAG context
            rag_context = self.rag_service.query(prompt)
            plan_prompt = PLANNER_PROMPT.format(prompt=prompt, rag_context=rag_context)

        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("architect", "No model configured.")
            return

        raw_plan_response = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt)])

        try:
            plan_data = self._parse_json_response(raw_plan_response)
            file_plan = plan_data.get("files", [])
            if not file_plan: raise ValueError("AI did not return a valid file plan.")
            self.update_status("architect", "success", f"Plan created: {len(file_plan)} file(s) to generate/modify.")
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("architect", f"Plan creation failed: {e}", raw_plan_response)
            return

        filenames_to_generate = [f['filename'] for f in file_plan]
        self.event_bus.emit("prepare_for_generation", filenames_to_generate)
        await asyncio.sleep(0.1)

        self.update_status("coder", "working", "Generating code...")
        generated_code = {}

        for file_info in file_plan:
            filename = file_info['filename']
            file_content = ""
            async for chunk in self._generate_single_file_stream(file_info, file_plan, provider, model):
                file_content += chunk
                self.event_bus.emit("stream_code_chunk", filename, chunk)
            generated_code[filename] = self._clean_code_output(file_content)

        self.project_manager.save_files_to_project(generated_code)
        self.update_status("coder", "success", "Code generation complete.")

        # Self-correction loop
        for attempt in range(self.MAX_REFINEMENT_ATTEMPTS):
            self.update_status("executor", "working", f"Validating... (Attempt {attempt + 1})")
            exec_result = self.execution_engine.run_main_in_project()

            if exec_result.success:
                self.update_status("executor", "success", "Validation passed!")
                self.event_bus.emit("code_generation_complete", generated_code)
                self.event_bus.emit("ai_response_ready", "Modifications complete and successfully tested!")
                return

            self.update_status("executor", "error", "Validation failed.")
            all_project_files = self.project_manager.get_project_files()
            if "main.py" not in all_project_files:
                self.handle_error("executor", "Could not find main.py to fix.")
                return

            self.update_status("reviewer", "working", "Attempting to fix code...")
            broken_code = all_project_files.get("main.py", "")

            fixed_code_str = await self.reviewer_service.review_and_correct_code("main.py", broken_code,
                                                                                 exec_result.error)

            fixed_file_map = {"main.py": self._clean_code_output(fixed_code_str)}
            self.project_manager.save_files_to_project(fixed_file_map)

            self.event_bus.emit("code_generation_complete", fixed_file_map)
            self.update_status("reviewer", "success", "Fix implemented. Re-validating...")

        self.handle_error("executor", "Could not fix the code after several attempts.")

    async def _generate_single_file_stream(self, file_info, file_plan, provider, model):
        self.log("ai_call", f"Asking AI Coder to write code for '{file_info['filename']}'...")
        code_prompt = CODER_PROMPT.format(
            file_plan=json.dumps(file_plan, indent=2),
            filename=file_info['filename'],
            purpose=file_info['purpose']
        )
        async for chunk in self.llm_client.stream_chat(provider, model, code_prompt):
            yield chunk

    def _parse_json_response(self, response: str) -> dict:
        cleaned_response = self._clean_json_output(response, is_json=True)
        return json.loads(cleaned_response)

    def _clean_json_output(self, response: str, is_json: bool = False) -> str:
        response = response.strip()
        if is_json:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                return response[json_start:json_end]
            raise ValueError("No valid JSON object found in the AI's response.")
        return response

    def _clean_code_output(self, code: str) -> str:
        code = self._clean_json_output(code, is_json=False)  # Reuse for basic stripping
        if code.startswith("```python"):
            code = code[9:].lstrip()
        elif code.startswith("'''python"):
            code = code[9:].lstrip()
        elif code.startswith("```"):
            code = code[3:].lstrip()
        elif code.startswith("'''"):
            code = code[3:].lstrip()
        if code.endswith("```"): code = code[:-3].rstrip()
        if code.endswith("'''"): code = code[:-3].rstrip()
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