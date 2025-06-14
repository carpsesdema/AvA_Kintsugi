# kintsugi_ava/services/rag_manager.py
# V5: Manages the RAGService client and launches the external server process.

import asyncio
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QMessageBox

from .rag_service import RAGService
from core.project_manager import ProjectManager


class RAGManager(QObject):
    """
    Manages the RAG pipeline by orchestrating the RAGService client and
    launching/monitoring the external RAG server process.
    """
    log_message = Signal(str, str, str)  # Emits (source, type, message)

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.rag_service = RAGService()
        self.rag_server_process = None

        # Timer to periodically check the server status
        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self.check_server_status_async)
        self.status_check_timer.start(5000)  # Check every 5 seconds

        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )
        print("[RAGManager] Initialized.")

    def check_server_status_async(self):
        """Asynchronously checks server status and updates UI via logs."""
        asyncio.create_task(self._check_and_log_status())

    async def _check_and_log_status(self):
        """Helper to check connection and emit log messages."""
        is_now_connected = await self.rag_service.check_connection()

        if is_now_connected:
            self.log_message.emit("RAGManager", "success", "RAG service is running.")
        else:
            if self.rag_server_process and self.rag_server_process.poll() is not None:
                self.log_message.emit("RAGManager", "error", "RAG server process has terminated.")
                self.rag_server_process = None
            else:
                self.log_message.emit("RAGManager", "info", "RAG service is not running.")

    def launch_rag_server(self, parent_widget=None):
        """
        Launches the rag_server.py script as a separate background process.
        """
        if self.rag_server_process and self.rag_server_process.poll() is None:
            QMessageBox.information(parent_widget, "Already Running", "The RAG server process is already running.")
            return

        self.log_message.emit("RAGManager", "info", "Attempting to launch RAG server...")

        try:
            # Determine the path to the python executable in the current venv
            # This is crucial for ensuring it uses the same environment
            python_executable = sys.executable
            server_script_path = Path(__file__).parent.parent / "rag_server.py"
            requirements_path = Path(__file__).parent.parent / "requirements_rag.txt"

            if not server_script_path.exists():
                 QMessageBox.critical(parent_widget, "Error", f"Could not find rag_server.py at {server_script_path}")
                 return

            if not requirements_path.exists():
                 QMessageBox.critical(parent_widget, "Error", f"Could not find requirements_rag.txt at {requirements_path}")
                 return

            # First, ensure dependencies are installed
            print(f"Installing RAG server dependencies from {requirements_path}...")
            # Using Popen to avoid blocking while pip runs
            pip_install = subprocess.Popen([python_executable, "-m", "pip", "install", "-r", str(requirements_path)],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = pip_install.communicate()
            if pip_install.returncode != 0:
                self.log_message.emit("RAGManager", "error", f"Failed to install RAG dependencies: {stderr}")
                QMessageBox.critical(parent_widget, "Dependency Error", f"Failed to install RAG dependencies:\n{stderr}")
                return
            self.log_message.emit("RAGManager", "success", "RAG dependencies are up to date.")

            # Launch the server in a new process, hiding the console window on Windows
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            self.rag_server_process = subprocess.Popen(
                [python_executable, str(server_script_path)],
                creationflags=creation_flags
            )
            self.log_message.emit("RAGManager", "info", f"RAG server process started with PID: {self.rag_server_process.pid}")

        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Failed to launch RAG server: {e}")
            QMessageBox.critical(parent_widget, "Launch Error", f"Could not launch the RAG server:\n{e}")

    def terminate_rag_server(self):
        """Terminates the RAG server process if it's running."""
        if self.rag_server_process and self.rag_server_process.poll() is None:
            self.log_message.emit("RAGManager", "info", f"Terminating RAG server process (PID: {self.rag_server_process.pid})...")
            self.rag_server_process.terminate()
            try:
                self.rag_server_process.wait(timeout=5)
                self.log_message.emit("RAGManager", "success", "RAG server terminated successfully.")
            except subprocess.TimeoutExpired:
                self.log_message.emit("RAGManager", "warning", "RAG server did not terminate gracefully. Forcing kill.")
                self.rag_server_process.kill()
            self.rag_server_process = None