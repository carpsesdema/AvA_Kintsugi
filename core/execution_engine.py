# kintsugi_ava/core/execution_engine.py
# V3: Now uses the ProjectManager to handle file operations.

import subprocess
import sys
import time
from pathlib import Path
from .project_manager import ProjectManager  # <-- Import it


class ExecutionResult:
    # ... (class remains the same) ...
    def __init__(self, success: bool, output: str, error: str):
        self.success = success
        self.output = output
        self.error = error


class ExecutionEngine:
    """
    Safely executes generated Python code from a managed project directory.
    """

    def __init__(self, project_manager: ProjectManager):
        # It no longer creates its own workspace, it uses the shared one.
        self.project_manager = project_manager

    def run_main_in_project(self) -> ExecutionResult:
        """
        Attempts to run the main file within the currently active project.
        """
        project_dir = self.project_manager.current_project_path
        if not project_dir:
            return ExecutionResult(False, "", "Execution failed: No project is active.")

        main_file_path = project_dir / "main.py"
        if not main_file_path.exists():
            return ExecutionResult(False, "", "Execution failed: No 'main.py' file found.")

        with open(main_file_path, "r", encoding="utf-8") as f:
            main_content = f.read()

        print(f"[ExecutionEngine] Running project in: {project_dir}")
        is_gui_app = "mainloop()" in main_content or "app.exec()" in main_content or "app.run()" in main_content

        try:
            process = subprocess.Popen(
                [sys.executable, str(main_file_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', cwd=project_dir  # <-- Run from the project dir
            )

            if is_gui_app:
                time.sleep(3)
                poll_result = process.poll()
                if poll_result is not None and poll_result != 0:
                    stdout, stderr = process.communicate()
                    return ExecutionResult(False, stdout, stderr or stdout)
                process.terminate()
                return ExecutionResult(True, "GUI app launched successfully.", "")

            else:
                stdout, stderr = process.communicate(timeout=15)
                if process.returncode == 0:
                    return ExecutionResult(True, stdout, stderr)
                else:
                    return ExecutionResult(False, stdout, stderr or stdout)

        except subprocess.TimeoutExpired:
            process.kill()
            return ExecutionResult(False, "", "Execution failed: The script timed out.")
        except Exception as e:
            return ExecutionResult(False, "", f"An unexpected error occurred: {e}")