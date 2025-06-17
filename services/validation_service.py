# kintsugi_ava/services/validation_service.py
# V15: Implemented stateful, recursive fixing loop.

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
        self.max_fix_attempts = 2  # Set a limit to prevent infinite loops

    async def review_and_fix_file(self, initial_error_report: str, command: str) -> bool:
        """
        Manages a stateful, recursive fixing session.
        """
        current_error_report = initial_error_report

        for attempt in range(self.max_fix_attempts):
            self.log("info", f"Starting fix attempt {attempt + 1}/{self.max_fix_attempts}...")

            # 1. Get current project state and context
            project_source = self.project_manager.get_project_files()
            git_diff_before_fix = self.project_manager.get_git_diff()

            if not project_source:
                self.handle_error("executor", "Cannot initiate fix: No project files found.")
                return False

            crashing_file, line_number = self._parse_error_traceback(current_error_report)
            if not crashing_file:
                self.handle_error("executor",
                                  f"Could not identify the source file of the error on attempt {attempt + 1}.")
                return False

            if attempt == 0 and self.project_manager.active_project_path and line_number > 0:
                full_path = self.project_manager.active_project_path / crashing_file
                self.event_bus.emit("error_highlight_requested", full_path, line_number)

            self.update_status("reviewer", "working", f"Attempt {attempt + 1}: Analyzing error in {crashing_file}...")

            # 2. Ask the reviewer for a fix (either initial or recursive)
            if attempt == 0:
                changes_json_str = await self.reviewer_service.review_and_correct_code(
                    project_source=project_source,
                    error_report=current_error_report,
                    git_diff=git_diff_before_fix
                )
            else:  # Recursive attempt
                changes_json_str = await self.reviewer_service.attempt_recursive_fix(
                    project_source=project_source,
                    original_error_report=initial_error_report,
                    attempted_fix_diff=git_diff_before_fix,
                    new_error_report=current_error_report,
                )

            # 3. Process the AI's response
            if not changes_json_str:
                self.handle_error("reviewer", f"Did not generate a response for fix attempt {attempt + 1}.")
                continue  # Go to the next attempt if the AI returns nothing

            try:
                files_to_commit = self._robustly_parse_json_from_llm_response(changes_json_str)
            except (json.JSONDecodeError, ValueError) as e:
                self.handle_error("reviewer", f"Failed to parse AI's fix response on attempt {attempt + 1}: {e}")
                continue  # Go to the next attempt

            # 4. Apply the fix
            self.project_manager.write_and_stage_files(files_to_commit)
            self.event_bus.emit("code_generation_complete", files_to_commit)

            # 5. Validate the fix by re-running the command
            self.log("info", f"Validating fix attempt {attempt + 1} by re-running command: '{command}'")
            validation_result = await self.execution_engine.run_command(command)

            if validation_result.success:
                self.log("success", f"Validation successful! Fix confirmed on attempt {attempt + 1}.")
                fix_commit_message = f"fix: AI rewrite for error in {crashing_file} on attempt {attempt + 1}"
                self.project_manager.commit_staged_files(fix_commit_message)
                self.update_status("reviewer", "success", "Fix applied successfully.")
                return True  # Success! Exit the loop.
            else:
                self.log("warning", f"Fix attempt {attempt + 1} failed validation. A new error occurred.")
                current_error_report = validation_result.error  # This becomes the input for the next loop iteration

        # 6. If all attempts fail, log the final state.
        self.log("error", f"Failed to fix the error after {self.max_fix_attempts} attempts.")
        self.handle_error("reviewer", f"Could not fix the error. Last error:\n{current_error_report}")
        # Optionally, revert the changes here if desired.
        return False

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
                    path_to_check = path_obj if project_root in path_obj.parents else None
                else:
                    path_to_check = (project_root / path_obj).resolve()

                if path_to_check and path_to_check.is_file():
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