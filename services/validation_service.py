# kintsugi_ava/services/validation_service.py
# V9: Truly robust traceback parsing. Excludes .venv directory explicitly.

import re
import asyncio
from pathlib import Path

from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.project_manager import ProjectManager
from services.reviewer_service import ReviewerService
from utils.code_summarizer import CodeSummarizer


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

    async def _setup_environment(self) -> tuple[bool, str]:
        """Checks for and installs dependencies from requirements.txt if it exists."""
        project_dir = self.project_manager.active_project_path
        if not project_dir: return False, "Cannot set up environment: No active project."

        requirements_file = project_dir / "requirements.txt"
        if not requirements_file.exists():
            self.log("info", "No requirements.txt found, skipping dependency installation.")
            return True, "No requirements.txt found."

        python_executable = self.project_manager.venv_python_path
        if not python_executable: return False, "Cannot install dependencies: No virtual environment found."

        self.log("info", f"Found requirements.txt. Installing dependencies...")
        command = [str(python_executable), "-m", "pip", "install", "-r", str(requirements_file)]

        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=project_dir)
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            self.log("success", "Dependencies installed successfully.")
            return True, stdout.decode('utf-8', 'ignore')
        else:
            error_output = stderr.decode('utf-8', 'ignore')
            self.log("error", f"Failed to install dependencies:\n{error_output}")
            return False, error_output

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
                # Resolve the path to make it absolute and clean
                file_path = Path(file_path_str).resolve()

                # --- THE TRULY ROBUST FIX ---
                # Condition 1: Is the file inside the project directory?
                is_in_project = project_root in file_path.parents
                # Condition 2: Is the file *NOT* inside the project's venv directory?
                is_in_venv = venv_path in file_path.parents

                if is_in_project and not is_in_venv:
                    relative_path = file_path.relative_to(project_root)
                    posix_path_str = relative_path.as_posix()
                    self.log("info",
                             f"Pinpointed error in project source file: {posix_path_str} at line {line_num_str}")
                    return posix_path_str, int(line_num_str)
                # --- END OF FIX ---

            except (ValueError, FileNotFoundError):
                # This can happen if the path is weird or doesn't exist. Just skip it.
                continue

        self.log("warning", "Could not pinpoint error to a project source file. Defaulting to main.py.")
        return "main.py", 1

    async def run_validation_loop(self):
        """The self-correction loop that runs and fixes the code by replacing faulty files."""
        self.event_bus.emit("validation_started")

        self.update_status("executor", "working", "Preparing environment...")
        setup_success, setup_output = await self._setup_environment()
        if not setup_success:
            self.handle_error("executor",
                              f"Failed to install dependencies. Please check requirements.txt.\nDetails: {setup_output}")
            return

        for attempt in range(self.MAX_REFINEMENT_ATTEMPTS):
            self.update_status("executor", "working", f"Validating... (Attempt {attempt + 1})")
            exec_result = self.execution_engine.run_main_in_project()

            if exec_result.success:
                self.update_status("executor", "success", "Validation passed!")
                success_message = "Modifications complete and successfully tested!" if self.project_manager.is_existing_project else "Application generated and successfully tested!"
                self.event_bus.emit("workflow_completed")
                self.event_bus.emit("ai_response_ready", success_message)
                return

            self.update_status("executor", "error", "Validation failed.")
            all_project_files = self.project_manager.get_project_files()
            file_to_fix, line_number = self._parse_error_traceback(exec_result.error)

            if not file_to_fix or file_to_fix not in all_project_files:
                self.log("error",
                         f"DEBUG: File to fix '{file_to_fix}' not found in project files: {list(all_project_files.keys())}")
                self.handle_error("executor",
                                  f"Could not find file '{file_to_fix}' in the project file list to apply fix.")
                return

            self.event_bus.emit("validation_failed", [file_to_fix])

            self.update_status("reviewer", "working", f"Attempting to fix {file_to_fix}...")
            broken_code = all_project_files.get(file_to_fix, "")

            summarized_context = {}
            for fname, content in all_project_files.items():
                if fname.endswith('.py'):
                    summarizer = CodeSummarizer(content)
                    summarized_context[fname] = summarizer.summarize()
                else:
                    summarized_context[fname] = f"File exists: {fname}"

            corrected_content = await self.reviewer_service.review_and_correct_code(
                file_to_fix, broken_code, exec_result.error, line_number, summarized_context
            )

            if not corrected_content:
                self.handle_error("reviewer", f"Could not generate a fix for {file_to_fix}.")
                break

            fix_commit_message = f"fix: AI Reviewer rewrite for {file_to_fix} after error"
            self.project_manager.save_and_commit_files({file_to_fix: corrected_content}, fix_commit_message)
            self.event_bus.emit("code_generation_complete", {file_to_fix: corrected_content})
            self.update_status("reviewer", "success", "Fix implemented. Re-validating...")

        else:
            self.handle_error("executor", "Could not fix the code after several attempts.")

    def update_status(self, agent_id: str, status: str, text: str):
        self.event_bus.emit("node_status_changed", agent_id, status, text)
        if status != "working": self.log("info", f"{agent_id.title()} status: {status} - {text}")

    def log(self, message_type: str, content: str):
        self.event_bus.emit("log_message_received", "ValidationService", message_type, content)

    def handle_error(self, agent: str, error_msg: str):
        self.update_status(agent, "error", "Failed")
        self.log("error", f"{agent} failed: {error_msg}")
        self.event_bus.emit("ai_response_ready", f"Sorry, the {agent} failed. Error: {error_msg}")