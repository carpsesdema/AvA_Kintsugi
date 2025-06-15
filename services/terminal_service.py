# kintsugi_ava/services/terminal_service.py
# V4: Ensures pip install uses the project's specific virtual environment.

import asyncio
import shlex
import subprocess
from core.project_manager import ProjectManager
from core.execution_engine import ExecutionEngine
from gui.code_viewer import CodeViewerWindow


class TerminalService:
    """
    Parses and executes commands, emitting events for success or failure
    to drive the new user-in-control workflow.
    """

    def __init__(self, event_bus, project_manager: ProjectManager, execution_engine: ExecutionEngine,
                 code_viewer: CodeViewerWindow):
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.execution_engine = execution_engine
        self.code_viewer = code_viewer

    async def execute_command(self, command: str):
        """Asynchronously executes a command and emits events based on the result."""
        # --- COMMAND ROUTING ---
        if command.startswith('/'):
            output = self._handle_slash_command(command)
            self.event_bus.emit("terminal_output_received", output)
        elif command == "run_main":
            await self._run_main_script()
        elif command == "install_reqs":
            await self._run_pip_install()
        elif command == "review_and_fix":
            self.event_bus.emit("review_and_fix_requested")
        else:
            await self._run_generic_command(command)

    def _handle_slash_command(self, command: str) -> str:
        """Parses and executes slash commands, returning output immediately."""
        parts = shlex.split(command)
        base_command = parts[0].lower()
        args = parts[1:]

        if base_command == "/add":
            if not args:
                active_file = self.code_viewer.get_active_file_path()
                if not active_file: return "Usage: /add <filename> or open a file to add it implicitly."
                args = [active_file]
            return self.project_manager.stage_file(args[0])

        elif base_command == "/commit":
            if not args: return "Usage: /commit <message>"
            commit_message = " ".join(args)
            return self.project_manager.commit_staged_files(commit_message)

        elif base_command == "/help":
            return self._get_help_message()

        else:
            return f"Unknown command: '{base_command}'. Type /help for a list of commands."

    async def _run_main_script(self):
        """Runs the main script and emits success or failure events."""
        self.event_bus.emit("terminal_output_received", "Running main.py...\n")
        result = self.execution_engine.run_main_in_project()

        if result.success:
            output = f"SUCCESS: main.py ran successfully.\n\nOutput:\n{result.output}\n"
            self.event_bus.emit("terminal_output_received", output)
        else:
            error_output = f"ERROR: main.py failed to run.\n\nDetails:\n{result.error}\n"
            self.event_bus.emit("terminal_output_received", error_output)
            self.event_bus.emit("execution_failed", result.error)

    # --- FIX: This method is now venv-aware ---
    async def _run_pip_install(self):
        """Runs pip install using the project's specific virtual environment."""
        project_dir = self.project_manager.active_project_path
        if not project_dir:
            self.event_bus.emit("terminal_output_received", "ERROR: No active project.\n")
            return

        requirements_file = project_dir / "requirements.txt"
        if not requirements_file.exists():
            self.event_bus.emit("terminal_output_received", "ERROR: requirements.txt not found.\n")
            return

        # THIS IS THE CRITICAL FIX: Get the python executable *from the project's .venv*
        python_executable = self.project_manager.venv_python_path
        if not python_executable:
            self.event_bus.emit("terminal_output_received",
                                "ERROR: No virtual environment found for this project. Cannot install requirements.\n")
            return

        # Construct the command using the correct, full path to the venv's python
        command_to_run = f'"{python_executable}" -m pip install -r "{requirements_file}"'
        self.event_bus.emit("terminal_output_received", f"Running: {command_to_run}\n")

        # Use the generic command runner to execute it
        await self._run_generic_command(command_to_run)

    # --- END FIX ---

    async def _run_generic_command(self, command: str):
        """Runs a generic shell command and emits success or failure events."""
        project_dir = self.project_manager.active_project_path
        if not project_dir:
            self.event_bus.emit("terminal_output_received", "ERROR: No active project to run a command in.\n")
            return

        try:
            # We can run the command directly without needing the shell, which is safer
            # shlex.split helps handle paths with spaces correctly.
            args = shlex.split(command)
            process = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=project_dir
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                response = stdout.decode('utf-8',
                                         'ignore') if stdout else "Command executed successfully with no output.\n"
                self.event_bus.emit("terminal_output_received", response)
            else:
                response = f"ERROR:\n{stderr.decode('utf-8', 'ignore')}\n" if stderr else f"Command failed with exit code {process.returncode}\n"
                self.event_bus.emit("terminal_output_received", response)
                self.event_bus.emit("execution_failed", stderr.decode('utf-8', 'ignore'))

        except Exception as e:
            error_msg = f"Failed to execute command: {e}\n"
            self.event_bus.emit("terminal_output_received", error_msg)
            self.event_bus.emit("execution_failed", error_msg)

    def _get_help_message(self) -> str:
        """Returns the help text for available slash commands."""
        return """Kintsugi AvA Terminal Help:
/add [filename]    - Stage a file for commit. Uses active file if none specified.
/commit <message>  - Commit staged files with a message.
/help              - Display this help message.

Button Commands:
Run main.py        - Executes the main.py file in the project's venv.
Install Reqs       - Runs 'pip install -r requirements.txt' in the project's venv.
"""