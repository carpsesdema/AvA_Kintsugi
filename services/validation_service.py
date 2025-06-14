# kintsugi_ava/services/validation_service.py
# V11: Emits an event to request error highlighting in the UI.

import re
from pathlib import Path

from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.project_manager import ProjectManager
from services.reviewer_service import ReviewerService
from utils.code_summarizer import CodeSummarizer


class ValidationService:
    """
    Handles the AI-driven code correction process when manually triggered by the user.
    """

    def __init__(self, event_bus: EventBus, execution_engine: ExecutionEngine,
                 project_manager: ProjectManager, reviewer_service: ReviewerService):
        self.event_bus = event_bus
        self.execution_engine = execution_engine
        self.project_manager = project_manager
        self.reviewer_service = reviewer_service

    async def review_and_fix_file(self, error_report: str) -> bool:
        """
        Performs a single, user-triggered review and fix cycle on a file that caused an error.

        Args:
            error_report: The full error string captured from the failed execution.

        Returns:
            True if a fix was successfully generated and saved, False otherwise.
        """
        self.update_status("executor", "error", "Execution failed. Awaiting fix...")
        all_project_files = self.project_manager.get_project_files()
        file_to_fix, line_number = self._parse_error_traceback(error_report)

        # --- NEW: BROADCAST ERROR LOCATION FOR UI HIGHLIGHTING ---
        if file_to_fix and line_number > 0 and self.project_manager.active_project_path:
            full_path = self.project_manager.active_project_path / file_to_fix
            self.event_bus.emit("error_highlight_requested", full_path, line_number)
        # --- END NEW ---

        if not file_to_fix or file_to_fix not in all_project_files:
            self.handle_error("executor", f"Could not find file '{file_to_fix}' in the project file list to apply fix.")
            return False

        self.update_status("reviewer", "working", f"Attempting to fix {file_to_fix}...")
        broken_code = all_project_files.get(file_to_fix, "")

        # Create the summarized context for the reviewer
        summarized_context = {}
        for fname, content in all_project_files.items():
            if fname.endswith('.py'):
                summarizer = CodeSummarizer(content)
                summarized_context[fname] = summarizer.summarize()
            else:
                summarized_context[fname] = f"File exists: {fname}"

        # Get the full corrected code from the reviewer service
        corrected_content = await self.reviewer_service.review_and_correct_code(
            file_to_fix, broken_code, error_report, line_number, summarized_context
        )

        if not corrected_content:
            self.handle_error("reviewer", f"Could not generate a fix for {file_to_fix}.")
            return False

        # Save the entire corrected file
        fix_commit_message = f"fix: AI Reviewer rewrite for {file_to_fix} after error"
        self.project_manager.save_and_commit_files({file_to_fix: corrected_content}, fix_commit_message)

        # Update the UI by treating it as a new code generation for that file
        self.event_bus.emit("code_generation_complete", {file_to_fix: corrected_content})
        self.update_status("reviewer", "success", f"Fix for {file_to_fix} has been applied.")
        self.log("success", f"Successfully applied fix to {file_to_fix}. Please try running the code again.")
        return True

    def _parse_error_traceback(self, error_str: str) -> tuple[str, int]:
        """
        Parses a traceback string to find the file and line number *within the project*,
        ignoring errors from external libraries (like those in .venv).
        """
        project_root = self.project_manager.active_project_path
        if not project_root:
            return "main.py", 1

        venv_path = project_root / ".venv"
        traceback_lines = re.findall(r'File "([^"]+)", line (\d+)', error_str)

        for file_path_str, line_num_str in reversed(traceback_lines):
            try:
                file_path = Path(file_path_str).resolve()
                is_in_project = project_root in file_path.parents or project_root == file_path.parent
                is_in_venv = venv_path in file_path.parents

                if is_in_project and not is_in_venv:
                    relative_path = file_path.relative_to(project_root)
                    posix_path_str = relative_path.as_posix()
                    self.log("info", f"Pinpointed error in project source file: {posix_path_str} at line {line_num_str}")
                    return posix_path_str, int(line_num_str)
            except (ValueError, FileNotFoundError):
                continue

        self.log("warning", "Could not pinpoint error to a project source file. Defaulting to main.py.")
        return "main.py", 1

    def update_status(self, agent_id: str, status: str, text: str):
        self.event_bus.emit("node_status_changed", agent_id, status, text)
        if status != "working": self.log("info", f"{agent_id.title()} status: {status} - {text}")

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ValidationService", message_type, content)

    def handle_error(self, agent: str, error_msg: str):
        self.update_status(agent, "error", "Failed")
        self.log("error", f"{agent} failed: {error_msg}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed. Error: {error_msg}")