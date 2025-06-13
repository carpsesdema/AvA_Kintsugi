# kintsugi_ava/services/reviewer_service.py
# V2: Now generates diffs to unify the code modification process.

import difflib
from core.event_bus import EventBus
from core.llm_client import LLMClient
from prompts.prompts import REFINEMENT_PROMPT


class ReviewerService:
    """
    The ReviewerService uses an LLM to fix code, then generates a diff
    of the changes to ensure all modifications are handled consistently.
    """

    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    def _generate_diff(self, original_code: str, fixed_code: str, filename: str) -> str:
        """Compares two versions of code and returns a unified diff string."""
        diff = difflib.unified_diff(
            original_code.splitlines(keepends=True),
            fixed_code.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
        # We only want the content of the diff, not the '---' and '+++' headers.
        diff_content = "".join(list(diff)[2:])
        return diff_content

    async def review_and_correct_code(self, filename: str, broken_code: str, error_message: str) -> str | None:
        """
        Takes broken code and an error, gets a fix from an LLM, and returns a diff patch.

        Returns:
            A diff patch string if a fix was generated, otherwise None.
        """
        self.log("info", f"Reviewer received task to fix '{filename}'.")
        self.log("info", f"Error was: {error_message.strip().splitlines()[-1]}")

        prompt = REFINEMENT_PROMPT.format(
            filename=filename,
            code=broken_code,
            error=error_message
        )

        provider, model = self.llm_client.get_model_for_role("reviewer")
        if not provider or not model:
            self.log("error", "No model assigned for the 'reviewer' role.")
            return None

        self.log("ai_call", f"Asking {provider}/{model} to fix the code...")

        fixed_code = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt)])

        if fixed_code and fixed_code.strip() != broken_code.strip():
            self.log("success", f"Received potential fix for '{filename}'. Generating diff.")
            # Generate a patch from the change the reviewer made.
            patch = self._generate_diff(broken_code, fixed_code, filename)
            return patch
        else:
            self.log("warning", f"Reviewer did not produce a change for '{filename}'.")
            return None

    def log(self, message_type: str, content: str):
        """Helper to emit log events with a consistent source name."""
        self.event_bus.emit("log_message_received", "ReviewerService", message_type, content)