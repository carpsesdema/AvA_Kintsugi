# kintsugi_ava/services/terminal_service.py
# V2: Now a smart command parser with slash command support.

import asyncio
import shlex
import subprocess
from core.project_manager import ProjectManager
from core.execution_engine import ExecutionEngine
from gui.code_viewer import CodeViewerWindow


class TerminalService:
    """
    Parses and executes commands from the integrated terminal, handling special
    slash commands and delegating to other services.
    """

    def __init__(self, event_bus, project_manager: ProjectManager, execution_engine: ExecutionEngine, code_viewer: CodeViewerWindow):
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.execution_engine = execution_engine
        self.code_viewer = code_viewer

    async def execute_command(self, command: str):
        """Asynchronously executes a command and emits the output."""
        output = ""
        # --- COMMAND ROUTING ---
        if command.startswith('/'):
            output = self._handle_slash_command(command)
        elif command == "run_main": # Keep button commands simple
            output = self._run_main_script()
        elif command == "install_reqs":
            output = await self._run_pip_install()
        else:
            output = await self._run_generic_command(command)
        # --- END ROUTING ---

        self.event_bus.emit("terminal_output_received", output)

    def _handle_slash_command(self, command: str) -> str:
        """Parses and executes slash commands."""
        parts = shlex.split(command)
        base_command = parts[0].lower()
        args = parts[1:]

        if base_command == "/add":
            if not args: # If no filename, use the active one
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

    def _run_main_script(self) -> str:
        self.event_bus.emit("terminal_output_received", "Running main.py...\n")
        result = self.execution_engine.run_main_in_project()
        if result.success: return f"SUCCESS: main.py ran successfully.\n\nOutput:\n{result.output}\n"
        else: return f"ERROR: main.py failed to run.\n\nDetails:\n{result.error}\n"

    async def _run_pip_install(self) -> str:
        project_dir = self.project_manager.active_project_path
        if not project_dir: return "ERROR: No active project.\n"
        requirements_file = project_dir / "requirements.txt"
        if not requirements_file.exists(): return "ERROR: requirements.txt not found.\n"
        python_executable = self.project_manager.venv_python_path
        if not python_executable: return "ERROR: No virtual environment found for this project.\n"
        command_to_run = f'"{python_executable}" -m pip install -r "{requirements_file}"'
        self.event_bus.emit("terminal_output_received", f"Running: {command_to_run}\n")
        return await self._run_generic_command(command_to_run)

    async def _run_generic_command(self, command: str) -> str:
        project_dir = self.project_manager.active_project_path
        if not project_dir: return "ERROR: No active project to run a command in.\n"
        try:
            process = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=project_dir
            )
            stdout, stderr = await process.communicate()
            response = ""
            if stdout: response += f"{stdout.decode('utf-8', 'ignore')}\n"
            if stderr: response += f"ERROR:\n{stderr.decode('utf-8', 'ignore')}\n"
            return response or "Command executed with no output.\n"
        except Exception as e:
            return f"Failed to execute command: {e}\n"

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