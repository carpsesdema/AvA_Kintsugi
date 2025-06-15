# kintsugi_ava/services/reviewer_service.py
# V8: Added architecturally-aware correction method for multi-file fixes.

from core.event_bus import EventBus
from core.llm_client import LLMClient
from prompts.prompts import REFINEMENT_PROMPT
import json


class ReviewerService:
    """
    The ReviewerService uses an LLM to generate corrections for code that failed to execute.
    It can now handle both single-file rewrites and complex, multi-file architectural fixes.
    """

    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    # --- FIX: New method to handle the multi-file prompt logic ---
    async def review_and_correct_code_architecturally(
        self, project_source: dict, error_filename: str, error_report: str
    ) -> str | None:
        """
        Uses an LLM with full project context to generate a multi-file fix.

        Returns:
            A string containing a JSON object of {"filename": "new_code"}, or None on failure.
        """
        self.log("info", f"Reviewer received task to architecturally fix error from '{error_filename}'.")
        self.log("info", f"Error was: {error_report.strip().splitlines()[-1]}")

        prompt = REFINEMENT_PROMPT.format(
            project_source_json=json.dumps(project_source, indent=2),
            error_filename=error_filename,
            error_report=error_report
        )

        provider, model = self.llm_client.get_model_for_role("reviewer")
        if not provider or not model:
            self.log("error", "No model assigned for the 'reviewer' role.")
            return None

        self.log("ai_call", f"Asking {provider}/{model} to generate an architectural correction...")

        # The LLM is now expected to return a JSON object as a string.
        json_response_str = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt)])

        if json_response_str and json_response_str.strip():
            self.log("success", f"Reviewer provided a potential multi-file fix.")
            return json_response_str

        self.log("warning", f"Reviewer did not produce a valid response for the architectural fix.")
        return None
    # --- END FIX ---

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