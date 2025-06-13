# kintsugi_ava/services/architect_service.py
# V6: Now imports its prompts from a central library for better maintainability.

import asyncio
import json
from core.event_bus import EventBus
from core.llm_client import LLMClient
from core.execution_engine import ExecutionEngine
from prompts.prompts import PLANNER_PROMPT, CODER_PROMPT  # <-- The key change!


class ArchitectService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.execution_engine = ExecutionEngine()

    async def create_project(self, prompt: str):
        self.log("info", f"Architect received new project request: '{prompt}'")

        # --- STEP 1: Plan the project ---
        self.log("ai_call", "Asking AI Architect to design the project plan...")
        plan_prompt = PLANNER_PROMPT.format(prompt=prompt)  # Use imported prompt
        provider, model = self.llm_client.get_model_for_role("coder")
        if not provider or not model:
            self.log("error", "No model assigned for planning/coding.")
            self.event_bus.emit("ai_response_ready", "Sorry, no model is configured.")
            return

        raw_plan_response = "".join(
            [chunk async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt)])
        try:
            json_start = raw_plan_response.find('{');
            json_end = raw_plan_response.rfind('}') + 1
            if json_start == -1 or json_end == 0: raise ValueError("No JSON object found.")
            clean_json_str = raw_plan_response[json_start:json_end]
            plan_data = json.loads(clean_json_str)
            file_plan = plan_data.get("files", [])
            if not file_plan: raise ValueError("AI did not return a valid file plan.")
            self.log("success", f"Project plan received. Files: {[f['filename'] for f in file_plan]}")
        except (json.JSONDecodeError, ValueError) as e:
            self.log("error", f"Failed to get a valid project plan: {e}\nResponse was: {raw_plan_response}")
            self.event_bus.emit("ai_response_ready", f"Sorry, I couldn't create a plan. Error: {e}")
            return

        # --- STEP 2: Generate code for each file ---
        generated_files = {}
        plan_str = json.dumps(file_plan, indent=2)
        for file_to_generate in file_plan:
            filename = file_to_generate["filename"]
            purpose = file_to_generate["purpose"]
            self.log("ai_call", f"Asking AI Coder to write code for '{filename}'...")
            code_prompt = CODER_PROMPT.format(file_plan=plan_str, filename=filename,
                                              purpose=purpose)  # Use imported prompt
            file_content = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, code_prompt)])
            generated_files[filename] = self._clean_code_output(file_content)
            self.log("success", f"Successfully generated code for '{filename}'.")
            await asyncio.sleep(0.1)

        # --- STEP 3: Validate the generated project ---
        self.log("info", "Generation complete. Handing off to Execution Engine for validation...")
        execution_result = self.execution_engine.save_and_run(generated_files)

        # --- STEP 4: Finalize and emit results ---
        self.event_bus.emit("code_generation_complete", generated_files)

        if execution_result.success:
            self.log("success", "Execution Engine reports success! Project is runnable.")
            final_message = f"I've finished and successfully tested the project. You can view the {len(generated_files)} files in the Code Viewer."
        else:
            self.log("error", f"Execution Engine reported an error:\n{execution_result.error}")
            final_message = (f"I've finished generating the files, but there was an error when I tried to run it. "
                             f"You can view the code and the error in the logs.\n\n**Error:**\n```\n{execution_result.error}\n```")

        self.event_bus.emit("ai_response_ready", final_message)

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ArchitectService", message_type, content)

    def _clean_code_output(self, code: str) -> str:
        if code.strip().startswith("```python"): code = code.strip()[9:]
        if code.strip().startswith("```"): code = code.strip()[3:]
        if code.strip().endswith("```"): code = code.strip()[:-3]
        return code.strip()