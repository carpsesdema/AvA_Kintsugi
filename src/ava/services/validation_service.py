# src/ava/services/validation_service.py
# V19: Correctly accepts ProjectIndexerService for robust context gathering.

import re
import json
from pathlib import Path
from ava.core.event_bus import EventBus
from ava.core.project_manager import ProjectManager
from ava.services.reviewer_service import ReviewerService
from ava.services.project_indexer_service import ProjectIndexerService
from ava.prompts.prompts import FOCUSED_FIXER_PROMPT


class ValidationService:
    def __init__(self, event_bus: EventBus,
                 project_manager: ProjectManager,
                 reviewer_service: ReviewerService,
                 project_indexer: ProjectIndexerService): # <-- Correctly accepts the indexer
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.reviewer_service = reviewer_service
        self.project_indexer = project_indexer # <-- Stores the indexer


    async def review_and_fix_file(self, error_report: str) -> bool:
        """
        Performs a focused, intelligent fix by sending only the necessary context to the LLM.
        """
        self.log("info", "Starting focused fix workflow...")

        # 1. Identify the crashing file from the error report
        crashing_file_path, line_number = self._parse_error_traceback(error_report)
        if not crashing_file_path:
            self.handle_error("executor", "Could not identify the source file of the error from the traceback.")
            return False

        # 2. Gather focused context instead of the whole project
        crashing_file_content = self.project_manager.read_file(crashing_file_path)
        if crashing_file_content is None:
            self.handle_error("executor", f"Could not read the content of the crashing file: {crashing_file_path}")
            return False

        # Get project index if the service is available
        project_index = {}
        if self.project_indexer and self.project_manager.active_project_path:
             project_index = self.project_indexer.build_index(self.project_manager.active_project_path)


        git_diff = self.project_manager.get_git_diff()

        if self.project_manager.active_project_path and line_number > 0:
            full_path = self.project_manager.active_project_path / crashing_file_path
            self.event_bus.emit("error_highlight_requested", full_path, line_number)

        self.update_status("reviewer", "working", f"Analyzing error in {crashing_file_path}...")

        # 3. Use the FOCUSED_FIXER_PROMPT
        prompt = FOCUSED_FIXER_PROMPT.format(
            error_report=error_report,
            crashing_filename=crashing_file_path,
            crashing_file_content=crashing_file_content,
            project_index_json=json.dumps(project_index, indent=2),
            git_diff=git_diff
        )

        changes_json_str = await self.reviewer_service._get_fix_from_llm(prompt) # Using the internal helper

        if not changes_json_str:
            self.handle_error("reviewer", "Did not generate a response for the error fix.")
            return False

        # 4. Process and apply the fix
        try:
            files_to_commit = self._robustly_parse_json_from_llm_response(changes_json_str)
            if not isinstance(files_to_commit, dict) or not files_to_commit:
                raise ValueError("AI response was not a valid, non-empty dictionary of file changes.")
        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("reviewer", f"Failed to parse AI's fix response: {e}")
            return False

        filenames_changed = ", ".join(files_to_commit.keys())
        fix_commit_message = f"fix: AI rewrite for error in {crashing_file_path}\n\nChanged files: {filenames_changed}"
        self.project_manager.save_and_commit_files(files_to_commit, fix_commit_message)

        # 5. Notify the system that the fix is applied and finish.
        self.event_bus.emit("code_generation_complete", files_to_commit)
        self.update_status("reviewer", "success", f"Fix applied to {len(files_to_commit)} file(s).")
        self.log("success", "Successfully applied fix. Please try running the code again.")
        return True

    def _robustly_parse_json_from_llm_response(self, response_text: str) -> dict:
        """
        A highly robust function to find and parse a JSON object from an LLM's text response.
        """
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                self.log("warning", f"Found a markdown JSON block, but it failed to parse: {e}. Trying other methods.")

        first_brace = response_text.find('{')
        last_brace = response_text.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            potential_json_str = response_text[first_brace:last_brace + 1]
            try:
                return json.loads(potential_json_str)
            except json.JSONDecodeError:
                self.log("warning", "Found content between braces, but it was not valid JSON.")

        self.log("error", f"Could not extract valid JSON from LLM response. Raw head: '{response_text[:300]}...'")
        raise ValueError("Could not find a valid JSON object in the LLM response.")

    def _parse_error_traceback(self, error_str: str) -> tuple[str | None, int]:
        """
        Parses a traceback string to find the last file mentioned that is part
        of the user's project, not a system or venv library.
        """
        project_root = self.project_manager.active_project_path
        if not project_root:
            self.log("error", "Cannot parse traceback without an active project root.")
            return None, -1

        traceback_pattern = re.compile(r'File "((?:[a-zA-Z]:)?[^"]+)", line (\d+)')
        matches = traceback_pattern.findall(error_str)

        if not matches:
            fallback_pattern = re.compile(r'((?:[a-zA-Z]:)?[^:]+\.py):(\d+):')
            matches = [(m[0], m[1]) for m in fallback_pattern.findall(error_str)]

        if not matches:
            self.log("warning", "Could not find any file paths in the error report using known patterns.")
            return None, -1

        for file_path_from_trace, line_num_str in reversed(matches):
            if not file_path_from_trace or not line_num_str:
                continue
            try:
                path_obj = Path(file_path_from_trace)
                if path_obj.is_absolute():
                    # Check if the file is within the project directory
                    if project_root in path_obj.parents:
                        path_to_check = path_obj
                    else:  # If not, it's a system file or from another location.
                        continue
                else:  # if relative, resolve it against the project root
                    path_to_check = (project_root / path_obj).resolve()

                if path_to_check.is_file():
                    # Final check to exclude venv files
                    if ".venv" in path_to_check.parts or "site-packages" in path_to_check.parts:
                        continue

                    relative_path = path_to_check.relative_to(project_root)
                    posix_path_str = relative_path.as_posix()
                    self.log("info", f"Pinpointed error origin: {posix_path_str} at line {line_num_str}")
                    return posix_path_str, int(line_num_str)
            except (ValueError, OSError) as e:
                self.log("warning", f"Could not process path '{file_path_from_trace}': {e}")
                continue

        self.log("warning", "Could not pinpoint error to a specific project source file.")
        return None, -1

    def update_status(self, agent_id: str, status: str, text: str):
        self.event_bus.emit("node_status_changed", agent_id, status, text)
        if status != "working": self.log("info", f"{agent_id.title()} status: {status} - {text}")

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ValidationService", message_type, content)

    def handle_error(self, agent: str, error_msg: str):
        self.update_status(agent, "error", "Failed")
        self.log("error", f"{agent} failed: {error_msg}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed. Error: {error_msg}")