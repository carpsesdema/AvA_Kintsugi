# kintsugi_ava/services/rag_manager.py
# V7: Implemented directory scanning and ingestion orchestration.

import asyncio
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QMessageBox, QFileDialog

# --- FIX: Import necessary services ---
from .rag_service import RAGService
from .directory_scanner_service import DirectoryScannerService
from .chunking_service import ChunkingService
from core.project_manager import ProjectManager
# --- END FIX ---


class RAGManager(QObject):
    """
    Manages the RAG pipeline by orchestrating the RAGService client and
    launching/monitoring the external RAG server process.
    """
    log_message = Signal(str, str, str)  # Emits (source, type, message)

    # --- FIX: Update constructor to accept required services ---
    def __init__(self, event_bus, project_manager: ProjectManager, rag_service: RAGService,
                 scanner: DirectoryScannerService, chunker: ChunkingService):
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.rag_service = rag_service
        self.scanner = scanner
        self.chunker = chunker
    # --- END FIX ---
        self.rag_server_process = None
        self._last_connection_status = None
        self._last_process_status = None
        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self.check_server_status_async)
        self.status_check_timer.start(10000)
        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )
        print("[RAGManager] Initialized.")

    # --- FIX: Add methods to handle directory scanning and ingestion ---
    def open_scan_directory_dialog(self, parent_widget=None):
        """Opens a dialog for the user to select a directory to ingest."""
        directory = QFileDialog.getExistingDirectory(
            parent_widget,
            "Select Directory to Add to Knowledge Base",
            str(Path.home())
        )
        if directory:
            self.log_message.emit("RAGManager", "info", f"User selected directory for ingestion: {directory}")
            asyncio.create_task(self.ingest_from_directory(directory))

    def ingest_active_project(self):
        """Ingests all files from the currently active project."""
        if not self.project_manager.active_project_path:
            self.log_message.emit("RAGManager", "warning", "No active project to ingest.")
            QMessageBox.warning(None, "No Project", "Please load or create a project first.")
            return

        project_path = str(self.project_manager.active_project_path)
        self.log_message.emit("RAGManager", "info", f"Starting ingestion of active project: {project_path}")
        asyncio.create_task(self.ingest_from_directory(project_path))

    async def ingest_from_directory(self, directory_path: str):
        """Scans, chunks, and ingests all supported files from a directory."""
        self.log_message.emit("RAGManager", "info", f"Scanning {directory_path} for files...")
        files_to_process = self.scanner.scan(directory_path)

        if not files_to_process:
            self.log_message.emit("RAGManager", "warning", "No supported files found in the selected directory.")
            return

        self.log_message.emit("RAGManager", "info", f"Found {len(files_to_process)} files. Starting chunking process...")
        all_chunks = []
        for file_path in files_to_process:
            try:
                content = file_path.read_text(encoding='utf-8')
                chunks = self.chunker.chunk_document(content, str(file_path))
                all_chunks.extend(chunks)
            except Exception as e:
                self.log_message.emit("RAGManager", "error", f"Could not process file {file_path.name}: {e}")

        if not all_chunks:
            self.log_message.emit("RAGManager", "error", "Chunking process resulted in zero chunks. Ingestion aborted.")
            return

        self.log_message.emit("RAGManager", "info", f"Chunking complete. Ingesting {len(all_chunks)} chunks...")
        success, message = await self.rag_service.add(all_chunks)

        if success:
            self.log_message.emit("RAGManager", "success", f"Ingestion complete. {message}")
        else:
            self.log_message.emit("RAGManager", "error", f"Ingestion failed. {message}")
    # --- END FIX ---

    def check_server_status_async(self):
        asyncio.create_task(self._check_and_log_status())

    async def _check_and_log_status(self):
        is_now_connected = await self.rag_service.check_connection()
        process_is_running = (self.rag_server_process and self.rag_server_process.poll() is None)
        if self._last_connection_status != is_now_connected:
            if is_now_connected:
                self.log_message.emit("RAGManager", "success", "RAG service is running.")
            else:
                self.log_message.emit("RAGManager", "info", "RAG service is not running.")
            self._last_connection_status = is_now_connected
        if self._last_process_status != process_is_running:
            if not process_is_running and self.rag_server_process:
                if self._last_process_status is True:
                    self.log_message.emit("RAGManager", "error", "RAG server process has terminated.")
                self.rag_server_process = None
            self._last_process_status = process_is_running

    def launch_rag_server(self, parent_widget=None):
        if self.rag_server_process and self.rag_server_process.poll() is None:
            QMessageBox.information(parent_widget, "Already Running", "The RAG server process is already running.")
            return
        self.log_message.emit("RAGManager", "info", "Attempting to launch RAG server...")
        try:
            python_executable = sys.executable
            server_script_path = Path(__file__).parent.parent / "rag_server.py"
            requirements_path = Path(__file__).parent.parent / "requirements_rag.txt"
            if not server_script_path.exists():
                QMessageBox.critical(parent_widget, "Error", f"Could not find rag_server.py at {server_script_path}")
                return
            if not requirements_path.exists():
                QMessageBox.critical(parent_widget, "Error", f"Could not find requirements_rag.txt at {requirements_path}")
                return
            print(f"Installing RAG server dependencies from {requirements_path}...")
            pip_install = subprocess.Popen([python_executable, "-m", "pip", "install", "-r", str(requirements_path)],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = pip_install.communicate()
            if pip_install.returncode != 0:
                self.log_message.emit("RAGManager", "error", f"Failed to install RAG dependencies: {stderr}")
                QMessageBox.critical(parent_widget, "Dependency Error", f"Failed to install RAG dependencies:\n{stderr}")
                return
            self.log_message.emit("RAGManager", "success", "RAG dependencies are up to date.")
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW
            self.rag_server_process = subprocess.Popen([python_executable, str(server_script_path)], creationflags=creation_flags)
            self.log_message.emit("RAGManager", "info", f"RAG server process started with PID: {self.rag_server_process.pid}")
            self._last_connection_status = None
            self._last_process_status = None
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Failed to launch RAG server: {e}")
            QMessageBox.critical(parent_widget, "Launch Error", f"Could not launch the RAG server:\n{e}")

    def terminate_rag_server(self):
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
            self._last_connection_status = None
            self._last_process_status = None