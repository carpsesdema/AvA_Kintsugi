# kintsugi_ava/services/architect_service.py
# V8: Implements the self-correction loop with the ReviewerService.

import asyncio
import json
from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.execution_engine import ExecutionEngine
from prompts.prompts import PLANNER_PROMPT, CODER_PROMPT
from services.reviewer_service import ReviewerService  # <-- Import it


class ArchitectService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.execution_engine = ExecutionEngine()
        # The Architect now owns the ReviewerService
        self.reviewer_service = ReviewerService(event_bus, llm_client)
        self.MAX_REFINEMENT_ATTEMPTS = 3

    async def create_project(self, prompt: str):
        self.log("info", f"Architect received new project request: '{prompt}'")
        # ...(omitting the planning step for brevity, it's unchanged)...
        # --- This part is the same as before ---
        self.update_status("architect", "working", "Designing plan...")
        plan_prompt = PLANNER_PROMPT.format(prompt=prompt)
        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.handle_error("architect", "No model configured.")
            return
        raw_plan_response = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt)])
        try:
            plan_data = self.parse_json_response(raw_plan_response)
            file_plan = plan_data.get("files", [])
            if not file_plan: raise ValueError("AI did not return a valid file plan.")
            self.update_status("architect", "success", f"Plan created: {len(file_plan)} file(s).")
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("architect", f"Plan creation failed: {e}", raw_plan_response)
            return

        # --- This part is the same as before ---
        self.update_status("coder", "working", f"Generating {len(file_plan)} file(s)...")
        generated_files = {}
        for file_info in file_plan:
            self.update_status("coder", "working", f"Writing {file_info['filename']}...")
            file_content = await self.generate_single_file(file_info, file_plan, provider, model)
            generated_files[file_info['filename']] = self._clean_code_output(file_content)
        self.update_status("coder", "success", "Code generation complete.")

        # --- THE NEW SELF-CORRECTION LOOP ---
        for attempt in range(self.MAX_REFINEMENT_ATTEMPTS):
            self.update_status("executor", "working", f"Validating... (Attempt {attempt + 1})")
            exec_result = self.execution_engine.save_and_run(generated_files)

            if exec_result.success:
                self.update_status("executor", "success", "Validation passed!")
                self.event_bus.emit("code_generation_complete", generated_files)
                self.event_bus.emit("ai_response_ready", f"Project successfully generated and tested!")
                return  # --- Exit on success ---

            # --- If it fails, enter the review-and-correct cycle ---
            self.update_status("executor", "error", "Validation failed.")
            self.log("error", f"Execution failed:\n{exec_result.error}")

            # Since our simple projects are single-file, we get the first file.
            # In a more complex system, we'd need to identify which file failed.
            main_filename = list(generated_files.keys())[0]
            broken_code = generated_files[main_filename]

            self.update_status("reviewer", "working", "Attempting to fix code...")
            fixed_code = await self.reviewer_service.review_and_correct_code(main_filename, broken_code,
                                                                             exec_result.error)

            generated_files[main_filename] = self._clean_code_output(fixed_code)
            self.update_status("reviewer", "success", "Fix implemented. Re-validating...")

        # If the loop finishes without success
        self.update_status("executor", "error", "Max refinement attempts reached.")
        self.log("error", "Could not fix the code after several attempts.")
        self.event_bus.emit("code_generation_complete", generated_files)
        self.event_bus.emit("ai_response_ready",
                            "I tried to fix the generated code but couldn't get it working. You can see the last attempt in the Code Viewer.")

    # ...(the rest of the ArchitectService methods are unchanged)...
    async def generate_single_file(self, file_info, file_plan, provider, model):
        self.log("ai_call", f"Asking AI Coder to write code for '{file_info['filename']}'...")
        code_prompt = CODER_PROMPT.format(file_plan=json.dumps(file_plan, indent=2), filename=file_info['filename'],
                                          purpose=file_info['purpose'])
        return "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, code_prompt)])

    def parse_json_response(self, response: str) -> dict:
        json_start = response.find('{');
        json_end = response.rfind('}') + 1
        if json_start == -1 or json_end == 0: raise ValueError("No JSON object found.")
        return json.loads(response[json_start:json_end])

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