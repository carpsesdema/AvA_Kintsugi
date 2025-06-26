# src/ava/services/validation_service.py
import re
import json
from pathlib import Path
from src.ava.core.event_bus import EventBus
from src.ava.core.project_manager import ProjectManager
from src.ava.services.reviewer_service import ReviewerService
from src.ava.prompts.prompts import REFINEMENT_PROMPT
from src.ava.utils.code_summarizer import CodeSummarizer


class ValidationService:
    def __init__(self, event_bus: EventBus,
                 project_manager: ProjectManager, reviewer_service: ReviewerService):
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.reviewer_service = reviewer_service

    def _find_relevant_files_for_fix(self, error_report: str, all_project_files: dict, crashing_file: str,
                                     top_n: int = 4) -> list[str]:
        """Finds the most relevant files based on an error report."""
        prompt_keywords = set(re.findall(r'\b\w+\b', error_report.lower()))
        if not prompt_keywords:
            return list(all_project_files.keys())[:top_n]

        scored_files = []
        for filename, content in all_project_files.items():
            score = 0
            if any(keyword in filename.lower() for keyword in prompt_keywords):
                score += 10
            content_lower = content.lower()
            for keyword in prompt_keywords:
                score += content_lower.count(keyword)
            scored_files.append((score, filename))

        scored_files.sort(key=lambda x: x[0], reverse=True)
        relevant_set = {filename for score, filename in scored_files[:top_n]}
        if crashing_file:
            relevant_set.add(crashing_file)
        if 'main.py' in all_project_files:
            relevant_set.add('main.py')
        return list(relevant_set)

    async def review_and_fix_file(self, error_report: str) -> bool:
        """Performs a one-shot intelligent fix using focused context."""
        self.log("info", "Starting one-shot surgical fix...")
        all_project_files = self.project_manager.get_project_files()
        if not all_project_files:
            self.handle_error("executor", "Cannot initiate fix: No project files found.")
            return False

        git_diff = self.project_manager.get_git_diff()
        crashing_file, line_number = self._parse_error_traceback(error_report)

        if crashing_file and self.project_manager.active_project_path and line_number > 0:
            self.event_bus.emit("error_highlight_requested", self.project_manager.active_project_path / crashing_file,
                                line_number)

        self.update_status("reviewer", "working", f"Analyzing error in {crashing_file or 'unknown file'}...")

        relevant_filenames = self._find_relevant_files_for_fix(error_report, all_project_files, crashing_file)
        self.log("info", f"Sending focused context with {len(relevant_filenames)} files to reviewer.")

        full_code_context_list = []
        summaries_context_list = []
        for filename, content in sorted(all_project_files.items()):
            if filename in relevant_filenames:
                full_code_context_list.append(f"--- File: {filename} ---\n```python\n{content}\n```")
            else:
                summary = CodeSummarizer(content).summarize() if filename.endswith('.py') else f"// Non-Python file ({Path(filename).suffix})"
                summaries_context_list.append(f"### File: `{filename}`\n```\n{summary}\n```")

        full_code_context_str = "\n\n".join(full_code_context_list)
        summaries_context_str = "\n\n".join(summaries_context_list)

        changes_json_str = await self.reviewer_service.review_and_correct_code(
            full_code_context=full_code_context_str,
            file_summaries_string=summaries_context_str,
            error_report=error_report,
            git_diff=git_diff
        )

        if not changes_json_str:
            self.handle_error("reviewer", "Did not generate a response for the error fix.")
            return False

        try:
            files_to_commit = self._robustly_parse_json_from_llm_response(changes_json_str)
            if not isinstance(files_to_commit, dict) or not files_to_commit:
                raise ValueError("AI response was not a valid, non-empty dictionary of file changes.")

            # --- CRITICAL SAFETY CHECK ---
            for filename, content in files_to_commit.items():
                if not content or content.isspace():
                    self.handle_error("reviewer", f"AI proposed an empty fix for '{filename}', which would wipe the file. Aborting fix to prevent data loss.")
                    return False
            # --- END SAFETY CHECK ---

        except (json.JSONDecodeError, ValueError) as e:
            self.handle_error("reviewer", f"Failed to parse AI's fix response: {e}")
            return False

        filenames_changed = ", ".join(files_to_commit.keys())
        fix_commit_message = f"fix: AI rewrite for error in {crashing_file or 'project'}\n\nChanged files: {filenames_changed}"
        self.project_manager.save_and_commit_files(files_to_commit, fix_commit_message)

        self.event_bus.emit("code_generation_complete", files_to_commit)
        self.update_status("reviewer", "success", f"Fix applied to {len(files_to_commit)} file(s).")
        self.log("success", "Successfully applied fix. Please try running the code again.")
        return True

    def _robustly_parse_json_from_llm_response(self, response_text: str) -> dict:
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
            if not file_path_from_trace or not line_num_str: continue
            try:
                path_obj = Path(file_path_from_trace)
                path_to_check = (project_root / path_obj).resolve() if not path_obj.is_absolute() else path_obj.resolve()
                if path_to_check.is_file() and project_root in path_to_check.parents:
                    if ".venv" in path_to_check.parts or "site-packages" in path_to_check.parts: continue
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