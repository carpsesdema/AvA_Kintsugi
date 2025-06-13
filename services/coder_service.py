# kintsugi_ava/services/coder_service.py
# V3: Now uses the model assigned in the LLMClient.

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
    """
    The CoderService uses the LLMClient to turn a prompt into code,
    using the model assigned to the 'coder' role.
    """

    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def generate_code(self, prompt: str):
        print(f"[CoderService] Starting AI code generation for prompt: '{prompt}'")
        final_prompt = CODER_PROMPT_TEMPLATE.format(prompt=prompt)

        # --- THIS IS THE KEY CHANGE ---
        # Get the assigned model from the client instead of hard-coding it.
        provider, model = self.llm_client.get_model_for_role("coder")

        if not provider or not model:
            error_message = "No model assigned for the 'coder' role. Please configure models."
            print(f"[CoderService] {error_message}")
            self.event_bus.emit("ai_response_ready", error_message)
            return

        full_code_response = ""
        async for chunk in self.llm_client.stream_chat(provider, model, final_prompt):
            full_code_response += chunk

        print(f"[CoderService] AI generation complete using {provider}/{model}.")

        filename = prompt.lower().replace(" ", "_").split("_")[0] + ".py"
        result = {filename: full_code_response}

        self.event_bus.emit("code_generation_complete", result)