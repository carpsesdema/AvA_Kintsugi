import asyncio
import os
import subprocess
import sys
from pathlib import Path
from .project_manager import ProjectManager


class ExecutionResult:
    """A simple class to hold the results of a code execution attempt."""

    def __init__(self, success: bool, output: str, error: str, command: str):
        self.success = success
        self.output = output
        self.error = error
        self.command = command


class ExecutionEngine:
    """
    Safely executes Python code and arbitrary commands from a managed project
    directory, using the project's own virtual environment if it exists.
    """

    def __init__(self, project_manager: ProjectManager):
        """The engine is initialized with a reference to the central ProjectManager."""
        self.project_manager = project_manager

    def run_main_in_project(self) -> ExecutionResult:
        """
        Attempts to run the main file within the currently active project.
        This is a convenience method that wraps run_command.
        """
        return asyncio.run(self.run_command("python main.py"))

    async def run_command(self, command: str) -> ExecutionResult:
        """
        Executes an arbitrary shell command within the project's context,
        capturing and returning all output.
        """
        project_dir = self.project_manager.active_project_path
        if not project_dir:
            return ExecutionResult(False, "", "Execution failed: No project is active.", command)

        # --- NEW GODOT-SPECIFIC LOGIC ---
        if command.strip() == "run_godot":
            godot_executable = os.getenv("GODOT_EXECUTABLE_PATH")
            if not godot_executable or not Path(godot_executable).exists():
                err_msg = "Execution failed: GODOT_EXECUTABLE_PATH is not set in your .env file or the path is invalid."
                return ExecutionResult(False, "", err_msg, command)

            # Command to launch Godot editor for the current project
            cmd_to_run = f'"{godot_executable}" --path "{project_dir}"'
            print(f"[ExecutionEngine] Launching Godot Editor: {cmd_to_run}")

            try:
                # For launching a GUI like Godot, we use Popen and don't wait for it to finish.
                # We won't capture stdout/stderr as it's a separate GUI process.
                process = subprocess.Popen(
                    cmd_to_run,
                    shell=True,
                    cwd=project_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                return ExecutionResult(True, f"Godot editor launched for project '{project_dir.name}'.", "", command)
            except Exception as e:
                err_msg = f"An unexpected error occurred while launching Godot: {e}"
                return ExecutionResult(False, "", err_msg, command)
        # --- END NEW LOGIC ---

        python_executable = self.project_manager.venv_python_path
        if not python_executable:
            error_msg = (
                "Execution failed: Could not find the project's virtual environment (.venv).\n"
                "Please create the project or run the install command to set up the venv."
            )
            return ExecutionResult(False, "", error_msg, command)

        env = self._get_subprocess_env(python_executable)
        cmd_to_run = self._prepare_command(command, python_executable)

        print(f"[ExecutionEngine] Running command: '{cmd_to_run}' in '{project_dir}'")

        try:
            process = await asyncio.create_subprocess_shell(
                cmd_to_run,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=project_dir,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            stdout_bytes, stderr_bytes = await process.communicate()
            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')

            full_output = stdout + stderr

            if process.returncode == 0:
                print(f"[ExecutionEngine] Command '{command}' executed successfully.")
                return ExecutionResult(True, stdout, stderr, command)
            else:
                print(f"[ExecutionEngine] Command '{command}' failed with exit code {process.returncode}.")
                return ExecutionResult(False, stdout, stderr, command)

        except FileNotFoundError:
            err_msg = f"Command not found: {command.split()[0]}"
            return ExecutionResult(False, "", err_msg, command)
        except Exception as e:
            err_msg = f"An unexpected error occurred during execution: {e}"
            return ExecutionResult(False, "", err_msg, command)

    def _get_subprocess_env(self, python_executable: Path | None) -> dict:
        """Prepare the environment variables for the subprocess to use the venv."""
        env = os.environ.copy()
        if python_executable and python_executable.exists():
            venv_dir = python_executable.parent.parent
            scripts_dir = str(python_executable.parent)
            if 'PATH' in env:
                env['PATH'] = f"{scripts_dir}{os.pathsep}{env['PATH']}"
            else:
                env['PATH'] = scripts_dir
            env['VIRTUAL_ENV'] = str(venv_dir)
            # Add PYTHONUNBUFFERED to ensure output streams are not delayed
            env['PYTHONUNBUFFERED'] = "1"
        return env

    def _prepare_command(self, command: str, python_executable: Path | None) -> str:
        """
        Modifies the command to use the venv python interpreter where appropriate.
        """
        parts = command.split()
        if not parts:
            return ""

        if python_executable and python_executable.exists():
            if parts[0] == 'python':
                parts[0] = f'"{python_executable}"'
            elif parts[0] == 'pip':
                parts = [f'"{python_executable}"', '-m', 'pip'] + parts[1:]

        return ' '.join(parts)