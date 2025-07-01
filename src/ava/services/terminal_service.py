# src/ava/services/terminal_service.py
# UPDATED: Now uses the centralized ExecutionEngine to run commands.

import asyncio
from src.ava.core.event_bus import EventBus
from src.ava.core.project_manager import ProjectManager
from src.ava.core.execution_engine import ExecutionEngine


class TerminalService:
    """
    Handles the logic for executing commands from terminal widgets.
    This class now delegates the actual execution to the ExecutionEngine,
    making it a pure orchestrator of terminal I/O.
    """

    def __init__(self, event_bus: EventBus, project_manager: ProjectManager):
        self.event_bus = event_bus
        self.project_manager = project_manager
        # Now uses the execution engine for all command processing
        self.execution_engine = ExecutionEngine(self.project_manager)
        self.active_processes: dict[int, asyncio.Task] = {}

    async def execute_command(self, command: str, session_id: int):
        """
        Delegates command execution to the ExecutionEngine and streams the results back.
        """
        if session_id in self.active_processes and not self.active_processes[session_id].done():
            self.event_bus.emit("terminal_error_received", f"Session {session_id} is already running a command.\n",
                                session_id)
            return

        # Create and store the execution task
        exec_task = asyncio.create_task(self.execution_engine.run_command(command))
        self.active_processes[session_id] = exec_task

        try:
            # Wait for the result from the execution engine
            result = await exec_task

            # Stream the captured output and error back to the terminal
            if result.output:
                self.event_bus.emit("terminal_output_received", result.output, session_id)
            if result.error:
                self.event_bus.emit("terminal_error_received", result.error, session_id)

            exit_message = f"\nProcess finished with exit code {'0' if result.success else '1'}\n"

            if result.success:
                self.event_bus.emit("terminal_success_received", exit_message, session_id)
            else:
                self.event_bus.emit("terminal_error_received", exit_message, session_id)
                # Combine stdout and stderr for a complete error report
                # This ensures the full traceback and any related print statements are captured.
                full_error_report = (result.output + "\n" + result.error).strip()
                self.event_bus.emit("execution_failed", full_error_report)

        except asyncio.CancelledError:
            self.event_bus.emit("terminal_error_received", "\nCommand was cancelled.\n", session_id)
        except Exception as e:
            self.event_bus.emit("terminal_error_received", f"An unexpected error occurred: {str(e)}\n", session_id)
        finally:
            if session_id in self.active_processes:
                del self.active_processes[session_id]
            self.event_bus.emit("terminal_command_finished", session_id)

    def cancel_command(self, session_id: int) -> bool:
        """Cancels a running command for a specific session."""
        task = self.active_processes.get(session_id)
        if task and not task.done():
            try:
                task.cancel()
                print(f"[TerminalService] Cancelled task for session {session_id}")
                return True
            except Exception as e:
                print(f"[TerminalService] Error cancelling task for session {session_id}: {e}")
        return False