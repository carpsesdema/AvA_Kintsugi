# kintsugi_ava/core/managers/task_manager.py
# Background task lifecycle management

import asyncio
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QMessageBox

from core.event_bus import EventBus


class TaskManager:
    """
    Manages background task lifecycle and coordination.
    Single responsibility: Task creation, monitoring, and cleanup.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Active tasks
        self.ai_task: Optional[asyncio.Task] = None
        self.terminal_task: Optional[asyncio.Task] = None

        # Manager references (set by Application)
        self.service_manager = None
        self.window_manager = None

        print("[TaskManager] Initialized")

    def set_managers(self, service_manager, window_manager):
        """
        Set references to other managers.

        Args:
            service_manager: ServiceManager instance
            window_manager: WindowManager instance
        """
        self.service_manager = service_manager
        self.window_manager = window_manager

    def start_ai_workflow_task(self, workflow_coroutine) -> bool:
        """
        Start an AI workflow task.

        Args:
            workflow_coroutine: Async coroutine to execute

        Returns:
            True if task was started, False if another AI task is running
        """
        if self.ai_task and not self.ai_task.done():
            main_window = self.window_manager.get_main_window() if self.window_manager else None
            QMessageBox.warning(main_window, "AI Busy", "The AI is currently processing another request.")
            return False

        self.ai_task = asyncio.create_task(workflow_coroutine)
        self.ai_task.add_done_callback(self._on_ai_task_done)

        print("[TaskManager] Started AI workflow task")
        return True

    def start_terminal_command_task(self, command_coroutine) -> bool:
        """
        Start a terminal command task.

        Args:
            command_coroutine: Async coroutine to execute

        Returns:
            True if task was started, False if another terminal task is running
        """
        if self.terminal_task and not self.terminal_task.done():
            self.event_bus.emit("terminal_output_received", "A command is already running.\n")
            return False

        # Clear previous error state when starting new command
        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        if code_viewer:
            code_viewer.clear_all_error_highlights()
            code_viewer.hide_fix_button()

        self.terminal_task = asyncio.create_task(command_coroutine)

        print("[TaskManager] Started terminal command task")
        return True

    def handle_terminal_command(self, command: str):
        """
        Handle terminal command execution.

        Args:
            command: Command string to execute
        """
        if not self.service_manager:
            print("[TaskManager] Cannot handle terminal command: ServiceManager not set")
            return

        terminal_service = self.service_manager.get_terminal_service()
        if not terminal_service:
            print("[TaskManager] Cannot handle terminal command: TerminalService not available")
            return

        command_coroutine = terminal_service.execute_command(command)
        self.start_terminal_command_task(command_coroutine)

    def _on_ai_task_done(self, task: asyncio.Task):
        """
        Handle AI task completion.

        Args:
            task: Completed asyncio Task
        """
        try:
            task.result()
            self.event_bus.emit("ai_response_ready", "Code generation complete. Run the code or ask for modifications.")
        except asyncio.CancelledError:
            print("[TaskManager] AI task was cancelled")
        except Exception as e:
            print(f"[TaskManager] CRITICAL ERROR IN AI TASK: {e}")
            import traceback
            traceback.print_exc()

            main_window = self.window_manager.get_main_window() if self.window_manager else None
            QMessageBox.critical(main_window, "Workflow Error",
                                 f"The AI workflow failed unexpectedly.\n\nError: {e}")
        finally:
            # Clean up UI state
            code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
            if code_viewer:
                code_viewer.hide_fix_button()

    def cancel_ai_task(self) -> bool:
        """
        Cancel the current AI task.

        Returns:
            True if task was cancelled, False if no task was running
        """
        if self.ai_task and not self.ai_task.done():
            self.ai_task.cancel()
            print("[TaskManager] Cancelled AI task")
            return True
        return False

    def cancel_terminal_task(self) -> bool:
        """
        Cancel the current terminal task.

        Returns:
            True if task was cancelled, False if no task was running
        """
        if self.terminal_task and not self.terminal_task.done():
            self.terminal_task.cancel()
            print("[TaskManager] Cancelled terminal task")
            return True
        return False

    async def cancel_all_tasks(self):
        """Cancel all running tasks and wait for them to complete."""
        print("[TaskManager] Cancelling all tasks...")

        tasks_to_cancel = []

        if self.ai_task and not self.ai_task.done():
            self.ai_task.cancel()
            tasks_to_cancel.append(self.ai_task)

        if self.terminal_task and not self.terminal_task.done():
            self.terminal_task.cancel()
            tasks_to_cancel.append(self.terminal_task)

        # Wait for all tasks to complete
        for task in tasks_to_cancel:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[TaskManager] Error during task cancellation: {e}")

        print("[TaskManager] All tasks cancelled")

    def is_ai_task_running(self) -> bool:
        """Check if an AI task is currently running."""
        return self.ai_task is not None and not self.ai_task.done()

    def is_terminal_task_running(self) -> bool:
        """Check if a terminal task is currently running."""
        return self.terminal_task is not None and not self.terminal_task.done()

    def get_task_status(self) -> Dict[str, Any]:
        """Get current task status for debugging."""
        return {
            "ai_task": {
                "exists": self.ai_task is not None,
                "running": self.is_ai_task_running(),
                "done": self.ai_task.done() if self.ai_task else None,
                "cancelled": self.ai_task.cancelled() if self.ai_task else None
            },
            "terminal_task": {
                "exists": self.terminal_task is not None,
                "running": self.is_terminal_task_running(),
                "done": self.terminal_task.done() if self.terminal_task else None,
                "cancelled": self.terminal_task.cancelled() if self.terminal_task else None
            }
        }