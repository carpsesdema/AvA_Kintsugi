# kintsugi_ava/services/reviewer_service.py
# The service responsible for fixing broken code.

from core.event_bus import EventBus
from core.llm_client import LLMClient
from prompts.prompts import REFINEMENT_PROMPT # We will create this prompt next

class ReviewerService:
    """
    The ReviewerService uses an LLM to fix code that has failed execution.
    Its sole purpose is to take broken code and an error message, and
    return a corrected version of the code.
    """
    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def review_and_correct_code(self, filename: str, broken_code: str, error_message: str) -> str:
        """
        Takes broken code and an error, and attempts to fix it using an LLM.

        Args:
            filename: The name of the file being fixed.
            broken_code: The source code that failed.
            error_message: The error returned by the ExecutionEngine.

        Returns:
            The AI's attempt at the corrected code.
        """
        self.log("info", f"Reviewer received task to fix '{filename}'.")
        self.log("info", f"Error was: {error_message.strip().splitlines()[-1]}")

        # Format the specialized prompt for refinement
        prompt = REFINEMENT_PROMPT.format(
            filename=filename,
            code=broken_code,
            error=error_message
        )

        provider, model = self.llm_client.get_model_for_role("reviewer")
        if not provider or not model:
            self.log("error", "No model assigned for the 'reviewer' role.")
            # If no reviewer model, just return the broken code to avoid crashing
            return broken_code

        self.log("ai_call", f"Asking {provider}/{model} to fix the code...")

        fixed_code = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt)])

        self.log("success", f"Received potential fix for '{filename}'.")
        return fixed_code

    def log(self, message_type: str, content: str):
        """Helper to emit log events with a consistent source name."""
        self.event_bus.emit("log_message_received", "ReviewerService", message_type, content)