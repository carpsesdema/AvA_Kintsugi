# kintsugi_ava/core/execution_engine.py
# V4: Now venv-aware, using the project's own interpreter if available.

import subprocess
import sys
import time
from pathlib import Path
from .project_manager import ProjectManager


class ExecutionResult:
    """A simple class to hold the results of a code execution attempt."""
    def __init__(self, success: bool, output: str, error: str):
        self.success = success
        self.output = output
        self.error = error


class ExecutionEngine:
    """
    Safely executes generated Python code from a managed project directory,
    using the project's own virtual environment if it exists.
    """

    def __init__(self, project_manager: ProjectManager):
        """The engine is initialized with a reference to the central ProjectManager."""
        self.project_manager = project_manager

    def run_main_in_project(self) -> ExecutionResult:
        """
        Attempts to run the main file within the currently active project.
        """
        project_dir = self.project_manager.active_project_path
        if not project_dir:
            return ExecutionResult(False, "", "Execution failed: No project is active.")

        main_file_path = project_dir / "main.py"
        if not main_file_path.exists():
            return ExecutionResult(False, "", "Execution failed: No 'main.py' file found.")

        # --- VENV-AWARE LOGIC (THE FIX) ---
        # Be strict. We MUST use the project's venv. If it doesn't exist, fail loudly.
        python_executable = self.project_manager.venv_python_path
        if not python_executable:
            error_msg = (
                "Execution failed: Could not find the project's virtual environment (.venv).\n"
                "Please try creating a new project to ensure the venv is set up correctly."
            )
            return ExecutionResult(False, "", error_msg)

        print(f"[ExecutionEngine] Using interpreter: {python_executable}")
        # --- END VENV-AWARE LOGIC ---

        try:
            with open(main_file_path, "r", encoding="utf-8") as f:
                main_content = f.read()
        except Exception as e:
            return ExecutionResult(False, "", f"Execution failed: Could not read main.py. Error: {e}")

        print(f"[ExecutionEngine] Running project in: {project_dir}")
        is_gui_app = "mainloop()" in main_content or "app.exec()" in main_content or "app.run()" in main_content

        try:
            process = subprocess.Popen(
                [str(python_executable), str(main_file_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8',
                cwd=project_dir
            )

            if is_gui_app:
                print("[ExecutionEngine] GUI application detected. Monitoring for stability...")
                time.sleep(3)
                poll_result = process.poll()
                if poll_result is not None and poll_result != 0:
                    stdout, stderr = process.communicate()
                    error_output = stderr or stdout
                    print(f"[ExecutionEngine] GUI app crashed on launch. Error:\n{error_output}")
                    return ExecutionResult(False, stdout, error_output)
                print("[ExecutionEngine] GUI app is stable. Terminating process and reporting success.")
                process.terminate()
                return ExecutionResult(True, "GUI app launched successfully.", "")

            else:
                print("[ExecutionEngine] Command-line script detected. Waiting for completion...")
                stdout, stderr = process.communicate(timeout=15)
                if process.returncode == 0:
                    print("[ExecutionEngine] Execution successful.")
                    return ExecutionResult(True, stdout, stderr)
                else:
                    print(f"[ExecutionEngine] Execution failed with code {process.returncode}.")
                    error_output = stderr or stdout
                    return ExecutionResult(False, stdout, error_output)

        except subprocess.TimeoutExpired:
            process.kill()
            return ExecutionResult(False, "", "Execution timed out after 15 seconds.")
        except Exception as e:
            return ExecutionResult(False, "", f"An unexpected error occurred during execution: {e}")