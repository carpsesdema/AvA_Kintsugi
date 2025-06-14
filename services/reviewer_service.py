# kintsugi_ava/services/reviewer_service.py
# V6: Enhanced workflow monitor integration with review phase events

from core.event_bus import EventBus
from core.llm_client import LLMClient
from prompts.prompts import REFINEMENT_PROMPT
import json


class ReviewerService:
    """
    The ReviewerService uses an LLM to generate a full, corrected version of a file
    that failed to execute.
    """

    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def review_and_correct_code(self, filename: str, broken_code: str, error_message: str,
                                      line_number: int, summarized_context: dict) -> str | None:
        """
        Takes broken code and an error, and gets a fully rewritten, corrected version of the file from an LLM.

        Returns:
            A string containing the full, corrected source code, or None.
        """
        # Emit review started event for enhanced workflow monitor
        self.event_bus.emit("review_started")

        self.log("info", f"Reviewer received task to fix '{filename}' near line {line_number}.")
        self.log("info", f"Error was: {error_message.strip().splitlines()[-1]}")

        # Remove the file being fixed from the context to avoid confusion
        context_for_prompt = summarized_context.copy()
        if filename in context_for_prompt:
            del context_for_prompt[filename]

        prompt = REFINEMENT_PROMPT.format(
            filename=filename,
            line_number=line_number,
            code=broken_code,
            error=error_message,
            code_summaries_json=json.dumps(context_for_prompt, indent=2)
        )

        provider, model = self.llm_client.get_model_for_role("reviewer")
        if not provider or not model:
            self.log("error", "No model assigned for the 'reviewer' role.")
            return None

        self.log("ai_call", f"Asking {provider}/{model} to generate a context-aware correction for {filename}...")

        # The LLM is now expected to return the full file content.
        corrected_code = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt)])

        if corrected_code and corrected_code.strip():
            cleaned_code = self._clean_code_output(corrected_code)
            if cleaned_code:
                self.log("success", f"Review completed for '{filename}'.")
                return cleaned_code

        self.log("warning", f"Reviewer did not produce a valid correction for '{filename}'.")
        return None

    def _clean_code_output(self, code: str) -> str:
        """Strips markdown code fences from a code block."""
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):].lstrip()
        elif code.startswith("```"):
            code = code[3:].lstrip()

        if code.endswith("```"):
            code = code[:-3].rstrip()

        return code.strip()

    def log(self, message_type: str, content: str):
        """Helper to emit log events with a consistent source name."""
        self.event_bus.emit("log_message_received", "ReviewerService", message_type, content)