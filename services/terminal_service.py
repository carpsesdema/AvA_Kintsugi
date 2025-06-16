# kintsugi_ava/services/terminal_service.py
# V4: Ensures all python and pip commands use the project's specific virtual environment.

import asyncio
import shlex
import subprocess
from pathlib import Path

from core.project_manager import ProjectManager
from core.execution_engine import ExecutionEngine
from gui.code_viewer import CodeViewerWindow


class TerminalService:
    """
    Parses and executes commands within the project's virtual environment,
    emitting events for success or failure to drive the user-in-control workflow.
    """

    def __init__(self, event_bus, project_manager: ProjectManager, execution_engine: ExecutionEngine,
                 code_viewer: CodeViewerWindow):
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.execution_engine = execution_engine
        self.code_viewer = code_viewer

    async def execute_command(self, command: str):
        """Asynchronously executes a command, ensuring it runs in the project's venv."""
        if command.startswith('/'):
            output = self._handle_slash_command(command)
            self.event_bus.emit("terminal_output_received", output)
            return

        # --- THIS IS THE CORE FIX ---
        # All commands are now routed through the generic runner which is venv-aware.
        await self._run_generic_command_in_venv(command)
        # --- END OF CORE FIX ---

    def _handle_slash_command(self, command: str) -> str:
        """Parses and executes slash commands, returning output immediately."""
        # This logic remains the same as it doesn't execute external processes.
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

    async def _run_generic_command_in_venv(self, command: str):
        """
        Runs a generic shell command, intelligently using the project's virtual
        environment if the command is for python or pip.
        """
        project_dir = self.project_manager.active_project_path
        if not project_dir:
            self.event_bus.emit("terminal_output_received", "ERROR: No active project to run a command in.\n")
            return

        try:
            # Prepare arguments for the subprocess
            args = shlex.split(command)

            # Check if we need to use the venv's executables
            if args[0] == "python" or args[0] == "pip":
                # Get the correct executable path from the venv
                exe_name = args[0]
                venv_exe_path = self.project_manager.venv_python_path if exe_name == "python" else self.project_manager.venv_pip_path

                if not venv_exe_path or not venv_exe_path.exists():
                    error_msg = f"ERROR: Could not find '{exe_name}' in the project's virtual environment.\n"
                    self.event_bus.emit("terminal_output_received", error_msg)
                    return

                # Replace the simple command (e.g., "python") with the full path to the venv executable
                args[0] = str(venv_exe_path)

            # Now, run the command with the corrected executable path
            self.event_bus.emit("terminal_output_received", f"> {' '.join(args)}\n")
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=project_dir
            )

            # Stream stdout and stderr in real-time
            async def read_stream(stream, is_error):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    output = line.decode('utf-8', 'ignore')
                    self.event_bus.emit("terminal_output_received", output)
                    if is_error:
                        self.event_bus.emit("execution_failed", output)

            await asyncio.gather(
                read_stream(process.stdout, is_error=False),
                read_stream(process.stderr, is_error=True)
            )

            await process.wait()

            if process.returncode != 0:
                self.event_bus.emit("terminal_output_received",
                                    f"\nProcess finished with exit code {process.returncode}\n")

        except FileNotFoundError:
            error_msg = f"ERROR: Command not found: '{args[0]}'. Is it in your system's PATH?\n"
            self.event_bus.emit("terminal_output_received", error_msg)
            self.event_bus.emit("execution_failed", error_msg)
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
Run main.py        - Executes 'python main.py' in the project's venv.
Install Reqs       - Runs 'pip install -r requirements.txt' in the project's venv.
"""