# src/ava/core/managers/task_manager.py
import asyncio
from typing import Optional, Dict
from PySide6.QtWidgets import QMessageBox

from src.ava.core.event_bus import EventBus
from src.ava.core.managers.service_manager import ServiceManager
from src.ava.core.managers.window_manager import WindowManager


class TaskManager:
    """
    Manages background task lifecycle and coordination.
    Single responsibility: Task creation, monitoring, and cleanup.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Active tasks
        self.ai_task: Optional[asyncio.Task] = None
        self.terminal_task: Optional[asyncio.Task] = None  # For backward compatibility
        self.terminal_tasks: Dict[int, asyncio.Task] = {}  # session_id -> task

        # Manager references (set by Application)
        self.service_manager: ServiceManager = None
        self.window_manager: WindowManager = None

        print("[TaskManager] Initialized")

    def set_managers(self, service_manager: ServiceManager, window_manager: WindowManager):
        """Set references to other managers."""
        self.service_manager = service_manager
        self.window_manager = window_manager

    def start_ai_workflow_task(self, workflow_coroutine) -> bool:
        """Start an AI workflow task."""
        if self.ai_task and not self.ai_task.done():
            main_window = self.window_manager.get_main_window() if self.window_manager else None
            QMessageBox.warning(main_window, "AI Busy", "The AI is currently processing another request.")
            return False

        self.ai_task = asyncio.create_task(workflow_coroutine)
        self.ai_task.add_done_callback(self._on_ai_task_done)

        print("[TaskManager] Started AI workflow task")
        return True

    def start_terminal_command_task(self, command_coroutine, session_id: int = 0) -> bool:
        """Start a terminal command task for a specific session."""
        if session_id in self.terminal_tasks and not self.terminal_tasks[session_id].done():
            self.event_bus.emit("terminal_error_received",
                                "A command is already running in this session.\n",
                                session_id)
            return False

        # Clear previous error state when starting new command
        code_viewer = self.window_manager.get_code_viewer() if self.window_manager else None
        if code_viewer:
            code_viewer.clear_all_error_highlights()
            code_viewer.hide_fix_button()

        # Create and store the task
        task = asyncio.create_task(command_coroutine)
        task.add_done_callback(lambda t: self._on_terminal_task_done(t, session_id))
        self.terminal_tasks[session_id] = task

        # Also update the single terminal_task for backward compatibility
        if session_id == 0:
            self.terminal_task = task

        print(f"[TaskManager] Started terminal command task for session {session_id}")
        return True

    def handle_terminal_command(self, command: str):
        """Handle terminal command execution (backward compatibility)."""
        if not self.service_manager:
            print("[TaskManager] Cannot handle terminal command: ServiceManager not set")
            return

        terminal_service = self.service_manager.get_terminal_service()
        if not terminal_service:
            print("[TaskManager] Cannot handle terminal command: Terminal service not available")
            return

        # Route to session 0 for backward compatibility
        command_coroutine = terminal_service.execute_command(command, 0)
        self.start_terminal_command_task(command_coroutine, 0)

    def cancel_terminal_command(self, session_id: int) -> bool:
        """Cancel a running terminal command for a specific session."""
        if session_id in self.terminal_tasks and not self.terminal_tasks[session_id].done():
            # Try to cancel via the terminal service first
            if self.service_manager:
                terminal_service = self.service_manager.get_terminal_service()
                if terminal_service and terminal_service.cancel_command(session_id):
                    return True

            # Fallback to task cancellation
            self.terminal_tasks[session_id].cancel()
            print(f"[TaskManager] Cancelled terminal task for session {session_id}")
            return True
        return False

    def _on_ai_task_done(self, task: asyncio.Task):
        """Handle AI task completion."""
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
            self.event_bus.emit("ai_workflow_finished")

    def _on_terminal_task_done(self, task: asyncio.Task, session_id: int):
        """Handle terminal task completion."""
        try:
            task.result()
            print(f"[TaskManager] Terminal task completed for session {session_id}")
        except asyncio.CancelledError:
            print(f"[TaskManager] Terminal task was cancelled for session {session_id}")
            self.event_bus.emit("terminal_output_received",
                                "Command cancelled\n",
                                session_id)
        except Exception as e:
            print(f"[TaskManager] Error in terminal task for session {session_id}: {e}")
            self.event_bus.emit("terminal_error_received",
                                f"Terminal task error: {e}\n",
                                session_id)
        finally:
            # Clean up the task reference
            if session_id in self.terminal_tasks:
                del self.terminal_tasks[session_id]

            # Emit command finished signal
            self.event_bus.emit("terminal_command_finished", session_id)

    def cancel_ai_task(self) -> bool:
        """Cancel the current AI task."""
        if self.ai_task and not self.ai_task.done():
            self.ai_task.cancel()
            print("[TaskManager] Cancelled AI task")
            return True
        return False

    def cancel_all_terminal_tasks(self) -> int:
        """Cancel all running terminal tasks."""
        cancelled_count = 0

        for session_id, task in list(self.terminal_tasks.items()):
            if not task.done():
                if self.cancel_terminal_command(session_id):
                    cancelled_count += 1

        return cancelled_count

    def cancel_terminal_task(self) -> bool:
        """Cancel the running terminal task (backward compatibility)."""
        return self.cancel_terminal_command(0)

    async def cancel_all_tasks(self):
        """Cancel all running tasks and wait for them to complete."""
        tasks_to_cancel = []

        # Cancel AI task
        if self.ai_task and not self.ai_task.done():
            self.ai_task.cancel()
            tasks_to_cancel.append(self.ai_task)

        # Cancel all terminal tasks (new multi-session)
        for session_id, task in self.terminal_tasks.items():
            if not task.done():
                task.cancel()
                tasks_to_cancel.append(task)

        # Cancel old single terminal task for backward compatibility
        if hasattr(self, 'terminal_task') and self.terminal_task and not self.terminal_task.done():
            if self.terminal_task not in tasks_to_cancel:  # Don't double-cancel
                self.terminal_task.cancel()
                tasks_to_cancel.append(self.terminal_task)

        # Wait for all cancelled tasks to complete
        if tasks_to_cancel:
            print(f"[TaskManager] Waiting for {len(tasks_to_cancel)} tasks to cancel...")
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        # Clear terminal tasks
        self.terminal_tasks.clear()
        self.terminal_task = None

        print("[TaskManager] All tasks cancelled")

    def get_task_summary(self) -> dict:
        """Get a summary of all active tasks."""
        return {
            "ai_task_running": self.ai_task is not None and not self.ai_task.done(),
            "terminal_task_running": self.terminal_task is not None and not self.terminal_task.done(),
            # Backward compatibility
            "terminal_sessions_active": len([t for t in self.terminal_tasks.values() if not t.done()]),
            "total_terminal_sessions": len(self.terminal_tasks),
            "active_sessions": list(self.terminal_tasks.keys())
        }