# kintsugi_ava/services/reviewer_service.py
# V10: Updated to pass role parameter for temperature settings.

from core.event_bus import EventBus
from core.llm_client import LLMClient
from prompts.prompts import REFINEMENT_PROMPT
import json


class ReviewerService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def review_and_correct_code(
            self, project_source: dict, error_filename: str, error_report: str
    ) -> str | None:
        """
        Uses an LLM with full project context to generate a multi-file fix.
        This is the primary method for all bug fixing.
        """
        self.log("info", f"Reviewer analyzing architectural error from '{error_filename}'.")

        prompt = REFINEMENT_PROMPT.format(
            project_source_json=json.dumps(project_source, indent=2),
            error_filename=error_filename,
            error_report=error_report
        )

        # Use the 'reviewer' role, which you can now confidently set to a fast model.
        provider, model = self.llm_client.get_model_for_role("reviewer")
        if not provider or not model:
            self.log("error", "No model assigned for the 'reviewer' role.")
            return None

        self.log("ai_call", f"Asking {provider}/{model} to generate an architectural correction...")

        # Pass the "reviewer" role for proper temperature setting
        json_response_str = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "reviewer")])

        if json_response_str and json_response_str.strip():
            self.log("success", "Reviewer provided a potential fix.")
            return json_response_str

        self.log("warning", "Reviewer did not produce a valid response for the fix.")
        return None

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ReviewerService", message_type, content)