# kintsugi_ava/services/validation_service.py
# V13: Calls the unified review_and_correct_code method.

import re
import json
from pathlib import Path
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.project_manager import ProjectManager
from services.reviewer_service import ReviewerService


class ValidationService:
    def __init__(self, event_bus: EventBus, execution_engine: ExecutionEngine,
                 project_manager: ProjectManager, reviewer_service: ReviewerService):
        self.event_bus = event_bus
        self.execution_engine = execution_engine
        self.project_manager = project_manager
        self.reviewer_service = reviewer_service

    async def review_and_fix_file(self, error_report: str) -> bool:
        all_project_files = self.project_manager.get_project_files()
        if not all_project_files:
            self.handle_error("executor", "Cannot initiate fix: No project files found.")
            return False

        crashing_file, line_number = self._parse_error_traceback(error_report)
        if not crashing_file:
            self.handle_error("executor", "Could not identify the source file of the error.")
            return False

        if self.project_manager.active_project_path:
            full_path = self.project_manager.active_project_path / crashing_file
            self.event_bus.emit("error_highlight_requested", full_path, line_number)

        self.update_status("reviewer", "working", f"Analyzing error in {crashing_file}...")

        # --- FIX: Call the single, powerful review method ---
        changes_json = await self.reviewer_service.review_and_correct_code(
            project_source=all_project_files,
            error_filename=crashing_file,
            error_report=error_report
        )
        # --- END FIX ---

        if not changes_json:
            self.handle_error("reviewer", "Could not generate a valid fix for the error.")
            return False

        try:
            cleaned_response = self._clean_json_output(changes_json)
            files_to_commit = json.loads(cleaned_response)
            if not isinstance(files_to_commit, dict) or not files_to_commit:
                raise ValueError("AI response was not a valid dictionary of file changes.")
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("reviewer", f"Failed to parse AI's fix response: {e}")
            return False

        filenames_changed = ", ".join(files_to_commit.keys())
        fix_commit_message = f"fix: AI rewrite for error in {crashing_file}\n\nChanged files: {filenames_changed}"
        self.project_manager.save_and_commit_files(files_to_commit, fix_commit_message)

        self.event_bus.emit("code_generation_complete", files_to_commit)
        self.update_status("reviewer", "success", f"Fix applied to {len(files_to_commit)} file(s).")
        self.log("success", "Successfully applied fix. Please try running the code again.")
        return True

    def _parse_error_traceback(self, error_str: str) -> tuple[str | None, int]:
        project_root = self.project_manager.active_project_path
        if not project_root: return None, -1
        traceback_lines = re.findall(r'File "(.+?)", line (\d+)', error_str)
        for file_path_str, line_num_str in reversed(traceback_lines):
            try:
                file_path = Path(file_path_str).resolve()
                if project_root in file_path.parents or project_root == file_path.parent:
                    if ".venv" in file_path.parts or "site-packages" in file_path.parts: continue
                    relative_path = file_path.relative_to(project_root)
                    posix_path_str = relative_path.as_posix()
                    self.log("info", f"Pinpointed error in project source: {posix_path_str} at line {line_num_str}")
                    return posix_path_str, int(line_num_str)
            except (ValueError, FileNotFoundError):
                continue
        self.log("warning", "Could not pinpoint error to a specific project source file.")
        return None, -1

    def _clean_json_output(self, response: str) -> str:
        response = response.strip()
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match: return match.group(0)
        if response.startswith('{') and response.endswith('}'): return response
        raise ValueError("No valid JSON object found in AI's response.")

    def update_status(self, agent_id: str, status: str, text: str):
        self.event_bus.emit("node_status_changed", agent_id, status, text)
        if status != "working": self.log("info", f"{agent_id.title()} status: {status} - {text}")

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ValidationService", message_type, content)

    def handle_error(self, agent: str, error_msg: str):
        self.update_status(agent, "error", "Failed")
        self.log("error", f"{agent} failed: {error_msg}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed. Error: {error_msg}")