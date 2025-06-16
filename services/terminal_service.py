# kintsugi_ava/services/terminal_service.py
# The brains behind the terminal! Executes commands in the right environment.

import asyncio
import subprocess
import sys
import os
from pathlib import Path

from core.event_bus import EventBus
from core.project_manager import ProjectManager


class TerminalService:
    """
    Handles the logic for executing commands from terminal widgets.
    This class is responsible for managing subprocesses and ensuring
    they run in the correct environment (e.g., project's virtual env).
    """

    def __init__(self, event_bus: EventBus, project_manager: ProjectManager):
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.processes: dict[int, asyncio.subprocess.Process] = {}

    async def execute_command(self, command: str, session_id: int):
        """
        Executes a command, capturing stdout and stderr. It now considers
        runtime warnings and non-crashing tracebacks as failures, triggering
        the full 'review-and-fix' workflow.
        """
        if session_id in self.processes and self.processes[session_id].returncode is None:
            self.event_bus.emit("terminal_error_received", f"Session {session_id} is already running a command.\n",
                                session_id)
            return

        project_path = self.project_manager.active_project_path
        if not project_path:
            self.event_bus.emit("terminal_error_received", "No active project. Cannot execute command.\n", session_id)
            return

        full_error_output = []

        try:
            python_executable = self.project_manager.venv_python_path
            env = self._get_subprocess_env(python_executable)
            cmd_to_run = self._prepare_command(command, python_executable)

            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            process = await asyncio.create_subprocess_shell(
                cmd_to_run,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=project_path,
                env=env,
                creationflags=creation_flags
            )
            self.processes[session_id] = process

            await asyncio.gather(
                self._stream_output(process.stdout, "terminal_output_received", session_id, None),
                self._stream_output(process.stderr, "terminal_error_received", session_id, full_error_output)
            )

            await process.wait()

            exit_message = f"\nProcess finished with exit code {process.returncode}\n"
            error_report = "".join(full_error_output)

            # A failure is now any non-zero exit code. The '-W error' flag handles the rest.
            if process.returncode != 0:
                self.event_bus.emit("terminal_error_received", exit_message, session_id)
                if error_report:
                    self.event_bus.emit("execution_failed", error_report)
            else:
                # Even with a 0 exit code, check for collected stderr output that isn't just a benign warning
                if error_report and "deprecationwarning" not in error_report.lower():
                     self.event_bus.emit("execution_failed", error_report)
                else:
                    self.event_bus.emit("terminal_success_received", exit_message, session_id)

        except FileNotFoundError:
            self.event_bus.emit("terminal_error_received", f"Command not found: {command.split()[0]}\n", session_id)
        except Exception as e:
            self.event_bus.emit("terminal_error_received", f"An error occurred: {str(e)}\n", session_id)
        finally:
            if session_id in self.processes:
                del self.processes[session_id]
            self.event_bus.emit("terminal_command_finished", session_id)

    def _prepare_command(self, command: str, python_executable: Path | None) -> str:
        """
        Modifies the command to use the venv, force unbuffered output (-u),
        and force warnings to raise exceptions (-W error) for better analysis.
        """
        parts = command.split()
        if not parts:
            return ""

        if python_executable and python_executable.exists():
            if parts[0] == 'python':
                # --- THIS IS THE FIX ---
                # -u: Force unbuffered stdout and stderr. CRITICAL for real-time output from GUI apps.
                # -W error: Treat warnings as errors to generate a full traceback.
                parts = [f'"{python_executable}"', '-u', '-W', 'error'] + parts[1:]
                # --- END OF FIX ---

            elif parts[0] == 'pip':
                parts = [f'"{python_executable}"', '-m', 'pip'] + parts[1:]

        return ' '.join(parts)

    def _get_subprocess_env(self, python_executable: Path | None):
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
        return env

    async def _stream_output(self, stream: asyncio.StreamReader, event_name: str, session_id: int,
                             collector: list | None):
        """Reads from a stream, emits events, and optionally collects the output."""
        while not stream.at_eof():
            try:
                line = await stream.readline()
                if line:
                    decoded_line = line.decode('utf-8', errors='replace')
                    self.event_bus.emit(event_name, decoded_line, session_id)
                    if collector is not None:
                        collector.append(decoded_line)
            except Exception as e:
                error_line = f"[Stream Read Error]: {e}\n"
                self.event_bus.emit("terminal_error_received", error_line, session_id)
                break

    def cancel_command(self, session_id: int) -> bool:
        """Cancels a running command for a specific session."""
        process = self.processes.get(session_id)
        if process and process.returncode is None:
            try:
                process.terminate()
                print(f"[TerminalService] Terminated process for session {session_id}")
                return True
            except ProcessLookupError:
                pass
            except Exception as e:
                print(f"[TerminalService] Error terminating process for session {session_id}: {e}")
        return False