# src/ava/services/reviewer_service.py
from src.ava.core.event_bus import EventBus
from src.ava.core.llm_client import LLMClient
from src.ava.prompts import REFINEMENT_PROMPT
import json


class ReviewerService:
    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def review_and_correct_code(
            self, error_report: str, git_diff: str, full_code_context: str
    ) -> str | None:
        """
        Uses an LLM with FOCUSED project context and git diff for the first fix attempt.
        """
        self.log("info", "Reviewer analyzing error with focused context.")
        prompt = REFINEMENT_PROMPT.format(
            full_code_context=full_code_context,
            error_report=error_report,
            git_diff=git_diff
        )
        return await self._get_fix_from_llm(prompt)

    async def _get_fix_from_llm(self, prompt: str) -> str | None:
        """Helper method to run the LLM call and handle logging."""
        provider, model = self.llm_client.get_model_for_role("reviewer")
        if not provider or not model:
            self.log("error", "No model assigned for the 'reviewer' role.")
            return None

        self.log("ai_call", f"Asking {provider}/{model} for a correction...")

        json_response_str = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt, "reviewer")])

        if json_response_str and json_response_str.strip():
            self.log("success", "Reviewer provided a potential fix.")
            return json_response_str

        self.log("warning", "Reviewer did not produce a valid response for the fix.")
        return None

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ReviewerService", message_type, content)