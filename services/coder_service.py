# kintsugi_ava/services/coder_service.py
# V2: The first REAL AI-powered service.

import asyncio
from core.event_bus import EventBus
from core.llm_client import LLMClient

# --- The Coder's Prime Directive ---
# This is a simple, direct prompt for our Minimum Viable Magic.
# It tells the AI to create a single, complete Python file.
CODER_PROMPT_TEMPLATE = """
You are an expert Python developer. Your sole task is to generate a single, complete, and runnable Python script based on the user's request.

**USER REQUEST:** "{prompt}"

**CRITICAL INSTRUCTIONS:**
1.  Generate a SINGLE Python script. Do not generate multiple files or a project structure.
2.  The script must be complete and self-contained.
3.  Include all necessary imports.
4.  If it's a GUI application, ensure it creates the window and starts the event loop.
5.  Your response MUST be ONLY the raw Python code. Do not include any explanations, introductory text, or markdown code fences like ```python ... ```.
"""


class CoderService:
    """
    The CoderService uses the LLMClient to turn a prompt into code.
    This is the core of our AI generation workflow.
    """

    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def generate_code(self, prompt: str):
        """
        The main async method. It formats the prompt, calls the LLM,
        and emits the result.
        """
        print(f"[CoderService] Starting AI code generation for prompt: '{prompt}'")

        # --- AI Call ---
        final_prompt = CODER_PROMPT_TEMPLATE.format(prompt=prompt)

        # We'll use a fast, capable model for this. This can be configured later.
        # Let's default to a common Ollama model, but you can change it to "deepseek", "google", etc.
        # provider = "google"
        # model = "gemini-1.5-flash-latest"

        provider = "ollama"
        model = "llama3"

        full_code_response = ""
        # The `stream_chat` method is an async generator. We loop through it.
        async for chunk in self.llm_client.stream_chat(provider, model, final_prompt):
            full_code_response += chunk
            # We can emit progress to the UI here if we want, but for now, we'll wait.

        print(f"[CoderService] AI generation complete. Total length: {len(full_code_response)} chars.")

        # --- Emit Result ---
        # We need a filename. For a single file, we can derive it from the prompt.
        # This is a simple placeholder for now.
        filename = prompt.lower().replace(" ", "_").split("_")[0] + ".py"

        # The payload for our event is a dictionary of {filename: content}
        result = {filename: full_code_response}

        self.event_bus.emit("code_generation_complete", result)