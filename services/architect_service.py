# kintsugi_ava/services/architect_service.py
# V11: Adds robust JSON cleaning to prevent silent failures during planning.

import asyncio
import json
from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.execution_engine import ExecutionEngine
from prompts.prompts import PLANNER_PROMPT, CODER_PROMPT
from services.reviewer_service import ReviewerService


class ArchitectService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.execution_engine = ExecutionEngine()
        self.reviewer_service = ReviewerService(event_bus, llm_client)
        self.MAX_REFINEMENT_ATTEMPTS = 3

    async def create_project(self, prompt: str):
        self.log("info", f"Architect received new project request: '{prompt}'")
        self.update_status("architect", "working", "Designing plan...")

        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("architect", "No model configured.")
            return

        plan_prompt = PLANNER_PROMPT.format(prompt=prompt)
        raw_plan_response = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt)])

        try:
            # --- THIS IS THE FIX ---
            # Clean the response before parsing to handle markdown fences.
            cleaned_plan_str = self._clean_json_output(raw_plan_response)
            plan_data = json.loads(cleaned_plan_str)
            # --- END OF FIX ---

            file_plan = plan_data.get("files", [])
            if not file_plan: raise ValueError("AI did not return a valid file plan.")
            self.update_status("architect", "success", f"Plan created: {len(file_plan)} file(s).")
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("architect", f"Plan creation failed: {e}", raw_plan_response)
            return

        filenames = [f['filename'] for f in file_plan]
        self.event_bus.emit("prepare_for_generation", filenames)
        await asyncio.sleep(0.1)

        self.update_status("coder", "working", "Generating code...")
        generated_files = {}

        for file_info in file_plan:
            filename = file_info['filename']
            self.update_status("coder", "working", f"Writing {filename}...")

            file_content = ""
            async for chunk in self.generate_single_file_stream(file_info, file_plan, provider, model):
                file_content += chunk
                self.event_bus.emit("stream_code_chunk", filename, chunk)

            generated_files[filename] = self._clean_code_output(file_content)
            self.log("success", f"Finished generating {filename}.")

        self.update_status("coder", "success", "Initial code generation complete.")

        current_code = generated_files.copy()
        for attempt in range(self.MAX_REFINEMENT_ATTEMPTS):
            self.update_status("executor", "working", f"Validating... (Attempt {attempt + 1})")
            exec_result = self.execution_engine.save_and_run(current_code)

            if exec_result.success:
                self.update_status("executor", "success", "Validation passed!")
                self.event_bus.emit("code_generation_complete", current_code)
                self.event_bus.emit("ai_response_ready", "Project successfully generated and tested!")
                return

            self.update_status("executor", "error", "Validation failed.")
            main_filename = "main.py"
            broken_code = current_code.get(main_filename, "")
            if not broken_code:
                self.handle_error("executor", "Could not find main.py to fix.")
                return

            self.update_status("reviewer", "working", "Attempting to fix code...")
            fixed_code_str = await self.reviewer_service.review_and_correct_code(main_filename, broken_code,
                                                                                 exec_result.error)
            current_code[main_filename] = self._clean_code_output(fixed_code_str)
            self.event_bus.emit("code_generation_complete", current_code)
            self.update_status("reviewer", "success", "Fix implemented. Re-validating...")

        self.handle_error("executor", "Could not fix the code after several attempts.")

    async def generate_single_file_stream(self, file_info, file_plan, provider, model):
        self.log("ai_call", f"Asking AI Coder to write code for '{file_info['filename']}'...")
        code_prompt = CODER_PROMPT.format(
            file_plan=json.dumps(file_plan, indent=2),
            filename=file_info['filename'],
            purpose=file_info['purpose']
        )
        async for chunk in self.llm_client.stream_chat(provider, model, code_prompt):
            yield chunk

    def _clean_json_output(self, response: str) -> str:
        """Finds and extracts a JSON object from a string that might have markdown."""
        # Find the first '{' and the last '}'
        json_start = response.find('{')
        json_end = response.rfind('}') + 1

        if json_start != -1 and json_end != 0:
            return response[json_start:json_end]

        # If no object is found, raise an error to be caught upstream
        raise ValueError("No valid JSON object found in the AI's response.")

    def handle_error(self, agent: str, error_msg: str, response: str = ""):
        self.update_status(agent, "error", "Failed")
        self.log("error", f"{agent} failed: {error_msg}\nResponse: {response}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed. Error: {error_msg}")

    def update_status(self, agent_id: str, status: str, text: str):
        self.event_bus.emit("node_status_changed", agent_id, status, text)
        if status != "working": self.log("info", f"{agent_id.title()} status: {status} - {text}")

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ArchitectService", message_type, content)

    def _clean_code_output(self, code: str) -> str:
        if code.strip().startswith("```python"): code = code.strip()[9:]
        if code.strip().startswith("```"): code = code.strip()[3:]
        if code.strip().endswith("```"): code = code.strip()[:-3]
        return code.strip()