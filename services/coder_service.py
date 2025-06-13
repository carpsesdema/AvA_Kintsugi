# kintsugi_ava/services/coder_service.py
# V5: Now reports back to the user interface upon completion.

import asyncio
from core.event_bus import EventBus
from core.llm_client import LLMClient

CODER_PROMPT_TEMPLATE = """
You are an expert Python developer. Your sole task is to generate a single, complete, and runnable Python script based on the user's request.
**USER REQUEST:** "{prompt}"
**CRITICAL INSTRUCTIONS:**
1.  Generate a SINGLE Python script.
2.  The script must be complete and self-contained.
3.  Your response MUST be ONLY the raw Python code. Do not include any explanations or markdown.
"""


class CoderService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def generate_code(self, prompt: str):
        self.log("info", f"Received task. Prompt: '{prompt}'")
        final_prompt = CODER_PROMPT_TEMPLATE.format(prompt=prompt)

        provider, model = self.llm_client.get_model_for_role("coder")

        if not provider or not model:
            error_message = "No model assigned for 'coder' role. Please configure models."
            self.log("error", error_message)
            self.event_bus.emit("ai_response_ready", error_message)
            return

        self.log("ai_call", f"Sending request to {provider}/{model}...")

        full_code_response = ""
        try:
            async for chunk in self.llm_client.stream_chat(provider, model, final_prompt):
                full_code_response += chunk

            if "Error:" in full_code_response[:100]:
                raise Exception(full_code_response)

            self.log("success", f"Successfully received response from {provider}/{model}.")
        except Exception as e:
            error_msg = f"Sorry, the AI call failed. Please check the logs.\nError: {e}"
            self.log("error", f"AI call failed: {e}")
            self.event_bus.emit("ai_response_ready", error_msg)
            return

        filename = self._derive_filename(prompt)
        result = {filename: full_code_response}

        self.log("success", f"Code generation complete. Emitting results for '{filename}'.")

        # --- THIS IS THE NEW FEEDBACK LOOP ---
        # 1. First, tell the Code Viewer to display the code.
        self.event_bus.emit("code_generation_complete", result)
        # 2. Then, tell the Chat Interface to post a success message.
        success_message = f"I've finished generating `{filename}`. You can view it now in the Code Viewer."
        self.event_bus.emit("ai_response_ready", success_message)
        # --- END OF FEEDBACK LOOP ---

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "CoderService", message_type, content)

    def _derive_filename(self, prompt: str) -> str:
        words = prompt.lower().split()
        safe_words = [word for word in words if word.isalnum() and word not in ["a", "an", "the", "make", "create"]]
        filename_base = "_".join(safe_words[:3]) or "generated_file"
        return f"{filename_base}.py"