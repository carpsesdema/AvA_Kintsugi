# kintsugi_ava/services/validation_service.py
# A dedicated service for the self-correction loop.

import re
from pathlib import Path

from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.project_manager import ProjectManager
from services.reviewer_service import ReviewerService


class ValidationService:
    """
    Handles the validation and refinement loop for the generated code.
    Its single responsibility is to test the code, and if it fails,
    orchestrate the diagnosis and repair process.
    """
    MAX_REFINEMENT_ATTEMPTS = 3

    def __init__(self, event_bus: EventBus, execution_engine: ExecutionEngine,
                 project_manager: ProjectManager, reviewer_service: ReviewerService):
        self.event_bus = event_bus
        self.execution_engine = execution_engine
        self.project_manager = project_manager
        self.reviewer_service = reviewer_service

    def _parse_error_traceback(self, error_str: str) -> tuple[str, int]:
        """Parses a traceback string to find the file and line number within the project."""
        if not self.project_manager.active_project_path:
            return "main.py", 1

        traceback_lines = re.findall(r'File "([^"]+)", line (\d+)', error_str)

        for file_path_str, line_num_str in reversed(traceback_lines):
            file_path = Path(file_path_str)
            try:
                # Use resolve() to get the absolute path for a reliable comparison
                if self.project_manager.active_project_path in file_path.resolve().parents:
                    relative_path_str = str(file_path.relative_to(self.project_manager.active_project_path))
                    self.log("info", f"Pinpointed error in project file: {relative_path_str} at line {line_num_str}")
                    return relative_path_str, int(line_num_str)
            except (ValueError, FileNotFoundError):
                continue

        self.log("warning", "Could not pinpoint error to a specific project file. Defaulting to main.py.")
        return "main.py", 1

    async def run_validation_loop(self):
        """The self-correction loop that runs and fixes the code using patches."""
        for attempt in range(self.MAX_REFINEMENT_ATTEMPTS):
            self.update_status("executor", "working", f"Validating... (Attempt {attempt + 1})")
            exec_result = self.execution_engine.run_main_in_project()

            if exec_result.success:
                self.update_status("executor", "success", "Validation passed!")
                success_message = "Modifications complete and successfully tested!" if self.project_manager.is_existing_project else "Application generated and successfully tested!"
                self.event_bus.emit("ai_response_ready", success_message)
                return

            self.update_status("executor", "error", "Validation failed.")

            all_project_files = self.project_manager.get_project_files()
            file_to_fix, line_number = self._parse_error_traceback(exec_result.error)

            if not file_to_fix or file_to_fix not in all_project_files:
                self.handle_error("executor", f"Could not find file '{file_to_fix}' to apply fix.")
                return

            self.update_status("reviewer", "working", f"Attempting to fix {file_to_fix}...")
            broken_code = all_project_files.get(file_to_fix, "")

            fix_patch = await self.reviewer_service.review_and_correct_code(
                file_to_fix, broken_code, exec_result.error, line_number
            )

            if not fix_patch:
                self.handle_error("reviewer", f"Could not generate a fix for {file_to_fix}.")
                break

            fix_commit_message = f"fix: AI Reviewer fix for {file_to_fix} after error"
            patch_success = self.project_manager.patch_file(file_to_fix, fix_patch, fix_commit_message)

            if patch_success:
                updated_files = self.project_manager.get_project_files()
                self.event_bus.emit("code_patched", file_to_fix, updated_files.get(file_to_fix, ""), fix_patch)
                self.update_status("reviewer", "success", "Fix implemented. Re-validating...")
            else:
                self.handle_error("reviewer", f"Generated fix for {file_to_fix} was invalid and could not be applied.")
                break

        else:  # This else belongs to the for loop, and runs if the loop completes without `break`.
            self.handle_error("executor", "Could not fix the code after several attempts.")

    def update_status(self, agent_id: str, status: str, text: str):
        """Updates the visual status of a node in the workflow monitor."""
        self.event_bus.emit("node_status_changed", agent_id, status, text)
        if status != "working":
            self.log("info", f"{agent_id.title()} status: {status} - {text}")

    def log(self, message_type: str, content: str):
        """Emits a log message to the event bus."""
        self.event_bus.emit("log_message_received", "ValidationService", message_type, content)

    def handle_error(self, agent: str, error_msg: str):
        """Centralized error reporting for this service."""
        self.update_status(agent, "error", "Failed")
        self.log("error", f"{agent} failed: {error_msg}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed. Error: {error_msg}")