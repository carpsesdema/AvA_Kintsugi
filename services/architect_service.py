# kintsugi_ava/services/architect_service.py
# The new, smarter service that can plan and generate multi-file projects.

import asyncio
import json
from core.event_bus import EventBus
from core.llm_client import LLMClient

# --- PROMPT 1: The Planner ---
# This prompt asks the AI to think like an architect and design the file structure.
PLANNER_PROMPT_TEMPLATE = """
You are an expert software architect. Based on the user's request, determine a complete and logical file structure for the project.

**USER REQUEST:** "{prompt}"

**INSTRUCTIONS:**
1.  Think step-by-step to determine the necessary files.
2.  For each file, write a concise, one-sentence purpose.
3.  Your response MUST be ONLY a valid JSON object with a single key "files", which is a list of objects, each containing "filename" and "purpose".

**EXAMPLE RESPONSE:**
{
  "files": [
    {
      "filename": "main.py",
      "purpose": "The main entry point for the application, handling window creation and the game loop."
    },
    {
      "filename": "player.py",
      "purpose": "Defines the Player class, responsible for movement and controls."
    },
    {
      "filename": "world.py",
      "purpose": "Handles the generation and management of the game world."
    }
  ]
}
"""

# --- PROMPT 2: The Coder ---
# This prompt is focused on writing the code for a single file, given the full project plan.
CODER_PROMPT_TEMPLATE = """
You are an expert Python developer. Your task is to write the code for a single file based on the provided plan.

**PROJECT PLAN:**
{file_plan}

**FILE TO GENERATE:** `{filename}`
**PURPOSE OF THIS FILE:** {purpose}

**CRITICAL INSTRUCTIONS:**
1.  Generate the complete, runnable Python code for ONLY the specified file (`{filename}`).
2.  Adhere strictly to the file's purpose.
3.  Ensure the code is clean, efficient, and well-documented.
4.  Your response MUST be ONLY the raw Python code. Do not include any explanations or markdown.
"""


class ArchitectService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def create_project(self, prompt: str):
        self.log("info", f"Architect received new project request: '{prompt}'")

        # --- STEP 1: Plan the project structure ---
        self.log("ai_call", "Asking AI Architect to design the project plan...")
        plan_prompt = PLANNER_PROMPT_TEMPLATE.format(prompt=prompt)
        provider, model = self.llm_client.get_model_for_role("coder")  # We can reuse the "coder" role for now

        raw_plan_response = ""
        async for chunk in self.llm_client.stream_chat(provider, model, plan_prompt):
            raw_plan_response += chunk

        try:
            plan_data = json.loads(raw_plan_response)
            file_plan = plan_data.get("files", [])
            if not file_plan: raise ValueError("AI did not return a valid file plan.")
            self.log("success", f"Project plan received. Files to generate: {[f['filename'] for f in file_plan]}")
        except (json.JSONDecodeError, ValueError) as e:
            self.log("error", f"Failed to get a valid project plan from the AI: {e}")
            self.event_bus.emit("ai_response_ready", f"Sorry, I couldn't create a plan for that request. Error: {e}")
            return

        # --- STEP 2: Generate code for each file in the plan ---
        generated_files = {}
        plan_str = json.dumps(file_plan, indent=2)

        for file_to_generate in file_plan:
            filename = file_to_generate["filename"]
            purpose = file_to_generate["purpose"]

            self.log("ai_call", f"Asking AI Coder to write the code for '{filename}'...")
            code_prompt = CODER_PROMPT_TEMPLATE.format(
                file_plan=plan_str,
                filename=filename,
                purpose=purpose
            )

            file_content = ""
            async for chunk in self.llm_client.stream_chat(provider, model, code_prompt):
                file_content += chunk

            generated_files[filename] = file_content
            self.log("success", f"Successfully generated code for '{filename}'.")
            await asyncio.sleep(0.1)  # Small delay to allow UI to update

        # --- STEP 3: Finalize and emit results ---
        self.log("success", "All files have been generated successfully!")
        self.event_bus.emit("code_generation_complete", generated_files)
        success_message = f"I've finished generating a new project with {len(generated_files)} files. You can view them in the Code Viewer."
        self.event_bus.emit("ai_response_ready", success_message)

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ArchitectService", message_type, content)