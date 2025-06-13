# kintsugi_ava/services/terminal_service.py
# The engine that powers the integrated terminal.

import asyncio
import subprocess
from core.project_manager import ProjectManager
from core.execution_engine import ExecutionEngine


class TerminalService:
    """
    Parses and executes commands from the integrated terminal, using the
    active project's context and virtual environment.
    """

    def __init__(self, event_bus, project_manager: ProjectManager, execution_engine: ExecutionEngine):
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.execution_engine = execution_engine

    async def execute_command(self, command: str):
        """Asynchronously executes a command and emits the output."""
        output = ""
        if command == "run_main":
            output = self._run_main_script()
        elif command == "install_reqs":
            output = await self._run_pip_install()
        else:
            output = await self._run_generic_command(command)

        self.event_bus.emit("terminal_output_received", output)

    def _run_main_script(self) -> str:
        """Uses the ExecutionEngine to run the project's main file."""
        self.event_bus.emit("terminal_output_received", "Running main.py...\n")
        result = self.execution_engine.run_main_in_project()
        if result.success:
            return f"SUCCESS: main.py ran successfully.\n\nOutput:\n{result.output}"
        else:
            return f"ERROR: main.py failed to run.\n\nDetails:\n{result.error}"

    async def _run_pip_install(self) -> str:
        """Installs dependencies from requirements.txt in the project's venv."""
        project_dir = self.project_manager.active_project_path
        if not project_dir:
            return "ERROR: No active project."

        requirements_file = project_dir / "requirements.txt"
        if not requirements_file.exists():
            return "ERROR: requirements.txt not found in the project root."

        python_executable = self.project_manager.venv_python_path
        if not python_executable:
            return "ERROR: No virtual environment found for this project."

        command_to_run = f'"{python_executable}" -m pip install -r "{requirements_file}"'
        self.event_bus.emit("terminal_output_received", f"Running: {command_to_run}\n")

        return await self._run_generic_command(command_to_run)

    async def _run_generic_command(self, command: str) -> str:
        """Runs a generic shell command in the project's directory."""
        project_dir = self.project_manager.active_project_path
        if not project_dir:
            return "ERROR: No active project to run a command in."

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=project_dir
            )
            stdout, stderr = await process.communicate()

            response = ""
            if stdout:
                response += f"{stdout.decode('utf-8')}\n"
            if stderr:
                response += f"ERROR:\n{stderr.decode('utf-8')}\n"

            return response or "Command executed with no output.\n"
        except Exception as e:
            return f"Failed to execute command: {e}\n"