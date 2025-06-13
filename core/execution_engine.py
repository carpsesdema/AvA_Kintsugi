# kintsugi_ava/core/execution_engine.py
# Safely executes and validates generated code.

import subprocess
import sys
from pathlib import Path


class ExecutionResult:
    """A simple class to hold the results of a code execution attempt."""

    def __init__(self, success: bool, output: str, error: str):
        self.success = success
        self.output = output
        self.error = error


class ExecutionEngine:
    """
    Safely executes generated Python code in a sandboxed environment
    to validate its correctness.
    """

    def __init__(self, workspace_dir: str = "workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)

    def save_and_run(self, files: dict[str, str]) -> ExecutionResult:
        """
        Saves the files to a temporary project folder and attempts to run the main file.

        Args:
            files: A dictionary of {filename: content}. It assumes a 'main.py' exists.

        Returns:
            An ExecutionResult object with the outcome.
        """
        if "main.py" not in files:
            return ExecutionResult(False, "", "Execution failed: No 'main.py' file found in the generated project.")

        # Create a unique, sandboxed directory for this run
        project_dir = self.workspace_dir / f"run_{Path.cwd().name}_{len(list(self.workspace_dir.iterdir()))}"
        project_dir.mkdir()

        # Write all the files to this sandboxed directory
        for filename, content in files.items():
            (project_dir / filename).write_text(content, encoding='utf-8')

        main_file_path = project_dir / "main.py"

        print(f"[ExecutionEngine] Running project in sandbox: {project_dir}")

        try:
            # Execute the script using the same Python interpreter that is running this app
            process = subprocess.run(
                [sys.executable, str(main_file_path)],
                capture_output=True,
                text=True,
                timeout=15,  # 15-second timeout to prevent infinite loops
                check=False  # Don't raise an exception on non-zero exit codes
            )

            if process.returncode == 0:
                print("[ExecutionEngine] Execution successful.")
                return ExecutionResult(True, process.stdout, process.stderr)
            else:
                print(f"[ExecutionEngine] Execution failed with code {process.returncode}.")
                error_output = process.stderr or process.stdout
                return ExecutionResult(False, process.stdout, error_output)

        except subprocess.TimeoutExpired:
            print("[ExecutionEngine] Execution timed out.")
            return ExecutionResult(False, "", "Execution failed: The process timed out after 15 seconds.")
        except Exception as e:
            print(f"[ExecutionEngine] An unexpected error occurred during execution: {e}")
            return ExecutionResult(False, "", f"An unexpected error occurred: {e}")