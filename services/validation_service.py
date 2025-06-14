# kintsugi_ava/services/validation_service.py
# V4: Implements full-file replacement instead of patching for reliability.

import re
import asyncio
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
        """Parses a traceback string to find the file and line number within the project."""
        if not self.project_manager.active_project_path: return "main.py", 1
        traceback_lines = re.findall(r'File "([^"]+)", line (\d+)', error_str)
        for file_path_str, line_num_str in reversed(traceback_lines):
            file_path = Path(file_path_str)
            try:
                if self.project_manager.active_project_path in file_path.resolve().parents:
                    relative_path_str = str(file_path.relative_to(self.project_manager.active_project_path))
                    self.log("info", f"Pinpointed error in project file: {relative_path_str} at line {line_num_str}")
                    return relative_path_str, int(line_num_str)
            except (ValueError, FileNotFoundError):
                continue
        self.log("warning", "Could not pinpoint error to a specific project file. Defaulting to main.py.")
        return "main.py", 1

    async def run_validation_loop(self):
        """The self-correction loop that runs and fixes the code by replacing faulty files."""
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

            # --- LOGIC CHANGE: Get full corrected code instead of a patch ---
            corrected_content = await self.reviewer_service.review_and_correct_code(
                file_to_fix, broken_code, exec_result.error, line_number
            )

            if not corrected_content:
                self.handle_error("reviewer", f"Could not generate a fix for {file_to_fix}.")
                break

            # Save the entire corrected file, which is more robust than patching.
            fix_commit_message = f"fix: AI Reviewer rewrite for {file_to_fix} after error"
            self.project_manager.save_and_commit_files({file_to_fix: corrected_content}, fix_commit_message)

            # Update the UI by treating it as a new code generation for that file
            self.event_bus.emit("code_generation_complete", {file_to_fix: corrected_content})
            self.update_status("reviewer", "success", "Fix implemented. Re-validating...")
            # --- END LOGIC CHANGE ---

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