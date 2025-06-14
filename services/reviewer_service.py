# kintsugi_ava/services/reviewer_service.py
# V3: Upgraded to use the new diff-based refinement prompt.

from core.event_bus import EventBus
from core.llm_client import LLMClient
from prompts.prompts import REFINEMENT_PROMPT


class ReviewerService:
    """
    The ReviewerService uses an LLM to generate a diff patch to fix code,
    based on a precise error location.
    """

    def __init__(self, event_bus: EventBus, llm_client: LLMClient):
        self.event_bus = event_bus
        self.llm_client = llm_client

    async def review_and_correct_code(self, filename: str, broken_code: str, error_message: str, line_number: int) -> str | None:
        """
        Takes broken code, an error, and a line number, gets a fix patch from an LLM.

        Returns:
            A diff patch string if a fix was generated, otherwise None.
        """
        self.log("info", f"Reviewer received task to fix '{filename}' near line {line_number}.")
        self.log("info", f"Error was: {error_message.strip().splitlines()[-1]}")

        prompt = REFINEMENT_PROMPT.format(
            filename=filename,
            line_number=line_number,
            code=broken_code,
            error=error_message
        )

        provider, model = self.llm_client.get_model_for_role("reviewer")
        if not provider or not model:
            self.log("error", "No model assigned for the 'reviewer' role.")
            return None

        self.log("ai_call", f"Asking {provider}/{model} to generate a fix patch...")

        # The LLM is now expected to return a diff patch directly.
        patch_content = "".join([chunk async for chunk in self.llm_client.stream_chat(provider, model, prompt)])

        if patch_content and patch_content.strip():
            # The cleaning function from ArchitectService is now part of the service itself.
            cleaned_patch = self._clean_diff_output(patch_content)
            if cleaned_patch:
                self.log("success", f"Received potential fix patch for '{filename}'.")
                return cleaned_patch
            else:
                self.log("warning", f"Reviewer returned an empty or invalid patch for '{filename}'.")
                return None
        else:
            self.log("warning", f"Reviewer did not produce a patch for '{filename}'.")
            return None

    def _clean_diff_output(self, diff: str) -> str:
        """Strips markdown code fences from a diff block."""
        diff = diff.strip()
        start_markers = ["```diff", "```"]
        for marker in start_markers:
            if diff.startswith(marker):
                diff = diff[len(marker):].lstrip()
                # Handle cases like ```diff\n...
                if diff.lower().startswith('diff'):
                   diff = diff[4:].lstrip()

        if diff.endswith("```"):
            diff = diff[:-3].rstrip()

        # A valid diff should start with '@@'
        if not diff.strip().startswith("@@"):
            self.log("warning", "AI response for diff did not start with @@, discarding.")
            return ""

        return diff.strip()


    def log(self, message_type: str, content: str):
        """Helper to emit log events with a consistent source name."""
        self.event_bus.emit("log_message_received", "ReviewerService", message_type, content)