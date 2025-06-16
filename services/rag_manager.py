# services/rag_manager.py
# V9: Enhanced with proper error capture and diagnostics

import asyncio
import subprocess
import sys
import threading
import queue
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QMessageBox, QFileDialog

from .rag_service import RAGService
from .directory_scanner_service import DirectoryScannerService
from .chunking_service import ChunkingService


class RAGManager(QObject):
    """
    Manages the RAG pipeline with enhanced error capture and diagnostics.
    """
    log_message = Signal(str, str, str)  # Emits (source, type, message)

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus

        # Create the RAG-related services internally
        self.rag_service = RAGService()
        self.scanner = DirectoryScannerService()
        self.chunker = ChunkingService()

        # RAG server process management
        self.rag_server_process = None
        self._last_connection_status = None
        self._last_process_status = None
        self._server_output_queue = queue.Queue()
        self._server_error_queue = queue.Queue()

        # Status monitoring
        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self.check_server_status_async)
        self.status_check_timer.start(10000)

        # Connect log messages to event bus
        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )

        print("[RAGManager] Initialized with enhanced error capture.")

    def set_project_manager(self, project_manager):
        """Set the project manager reference after it's available."""
        self.project_manager = project_manager

    def launch_rag_server(self, parent_widget=None):
        """Launch RAG server with enhanced error capture and diagnostics."""
        if self.rag_server_process and self.rag_server_process.poll() is None:
            QMessageBox.information(parent_widget, "Already Running", "The RAG server process is already running.")
            return

        self.log_message.emit("RAGManager", "info", "Starting RAG server with diagnostics...")

        try:
            # Pre-flight checks
            if not self._perform_preflight_checks(parent_widget):
                return

            python_executable = sys.executable
            server_script_path = Path(__file__).parent.parent / "rag_server.py"
            requirements_path = Path(__file__).parent.parent / "requirements_rag.txt"

            # Install dependencies first
            if not self._install_dependencies(python_executable, requirements_path, parent_widget):
                return

            # Launch the server with error capture
            self._launch_server_process(python_executable, server_script_path)

            # Start monitoring threads
            self._start_output_monitoring()

        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Failed to launch RAG server: {e}")
            QMessageBox.critical(parent_widget, "Launch Error", f"Could not launch the RAG server:\n{e}")

    def _perform_preflight_checks(self, parent_widget=None) -> bool:
        """Perform pre-flight checks before launching the server."""
        server_script_path = Path(__file__).parent.parent / "rag_server.py"
        requirements_path = Path(__file__).parent.parent / "requirements_rag.txt"

        if not server_script_path.exists():
            self.log_message.emit("RAGManager", "error", f"rag_server.py not found at {server_script_path}")
            QMessageBox.critical(parent_widget, "Error", f"Could not find rag_server.py at {server_script_path}")
            return False

        if not requirements_path.exists():
            self.log_message.emit("RAGManager", "error", f"requirements_rag.txt not found at {requirements_path}")
            QMessageBox.critical(parent_widget, "Error", f"Could not find requirements_rag.txt at {requirements_path}")
            return False

        # Check if port 8001 is available
        if not self._check_port_availability():
            self.log_message.emit("RAGManager", "warning", "Port 8001 appears to be in use")

        # Check if rag_db directory is writable
        if not self._check_database_permissions():
            return False

        return True

    def _check_port_availability(self) -> bool:
        """Check if port 8001 is available."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', 8001))
                return True
        except OSError:
            return False

    def _check_database_permissions(self) -> bool:
        """Check if we can create/write to the rag_db directory."""
        try:
            rag_db_path = Path(__file__).parent.parent / "rag_db"
            rag_db_path.mkdir(exist_ok=True)
            test_file = rag_db_path / "test_permissions.tmp"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Cannot write to rag_db directory: {e}")
            return False

    def _install_dependencies(self, python_executable: str, requirements_path: Path, parent_widget=None) -> bool:
        """Install RAG dependencies with proper error handling."""
        self.log_message.emit("RAGManager", "info", f"Installing RAG dependencies from {requirements_path}...")

        try:
            pip_install = subprocess.Popen(
                [python_executable, "-m", "pip", "install", "-r", str(requirements_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = pip_install.communicate(timeout=300)  # 5 minute timeout

            if pip_install.returncode != 0:
                error_msg = f"Failed to install RAG dependencies: {stderr}"
                self.log_message.emit("RAGManager", "error", error_msg)
                QMessageBox.critical(parent_widget, "Dependency Error",
                                     f"Failed to install RAG dependencies:\n{stderr}")
                return False

            self.log_message.emit("RAGManager", "success", "RAG dependencies installed successfully.")
            return True

        except subprocess.TimeoutExpired:
            self.log_message.emit("RAGManager", "error", "Dependency installation timed out")
            QMessageBox.critical(parent_widget, "Timeout Error", "Dependency installation timed out after 5 minutes")
            return False
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Dependency installation failed: {e}")
            return False

    def _launch_server_process(self, python_executable: str, server_script_path: Path):
        """Launch the server process with full error capture."""
        try:
            # Clear output queues
            while not self._server_output_queue.empty():
                self._server_output_queue.get()
            while not self._server_error_queue.empty():
                self._server_error_queue.get()

            # Launch with both stdout and stderr capture
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            self.rag_server_process = subprocess.Popen(
                [python_executable, str(server_script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                creationflags=creation_flags
            )

            self.log_message.emit("RAGManager", "info",
                                  f"RAG server process started with PID: {self.rag_server_process.pid}")
            self._last_connection_status = None
            self._last_process_status = None

        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Failed to start RAG server process: {e}")
            raise

    def _start_output_monitoring(self):
        """Start threads to monitor server output and errors."""
        # Start stdout monitoring thread
        stdout_thread = threading.Thread(
            target=self._monitor_server_output,
            args=(self.rag_server_process.stdout, self._server_output_queue, "OUTPUT"),
            daemon=True
        )
        stdout_thread.start()

        # Start stderr monitoring thread
        stderr_thread = threading.Thread(
            target=self._monitor_server_output,
            args=(self.rag_server_process.stderr, self._server_error_queue, "ERROR"),
            daemon=True
        )
        stderr_thread.start()

        # Start output processing timer
        self.output_timer = QTimer()
        self.output_timer.timeout.connect(self._process_server_output)
        self.output_timer.start(1000)  # Check every second

    def _monitor_server_output(self, pipe, output_queue, output_type):
        """Monitor server output in a separate thread."""
        try:
            for line in iter(pipe.readline, ''):
                if line:
                    output_queue.put((output_type, line.strip()))
            pipe.close()
        except Exception as e:
            output_queue.put((output_type, f"Monitoring error: {e}"))

    def _process_server_output(self):
        """Process queued server output and errors."""
        # Process stdout
        while not self._server_output_queue.empty():
            try:
                output_type, line = self._server_output_queue.get_nowait()
                if line:
                    self.log_message.emit("RAGServer", "info", f"[{output_type}] {line}")
            except queue.Empty:
                break

        # Process stderr
        while not self._server_error_queue.empty():
            try:
                output_type, line = self._server_error_queue.get_nowait()
                if line:
                    self.log_message.emit("RAGServer", "error", f"[{output_type}] {line}")
                    # Check for specific error patterns
                    self._analyze_error_line(line)
            except queue.Empty:
                break

    def _analyze_error_line(self, error_line: str):
        """Analyze error lines for specific issues and provide guidance."""
        error_lower = error_line.lower()

        if "address already in use" in error_lower or "port" in error_lower:
            self.log_message.emit("RAGManager", "error",
                                  "Port 8001 is already in use. Close other applications using this port.")
        elif "permission denied" in error_lower:
            self.log_message.emit("RAGManager", "error",
                                  "Permission denied. Check file/directory permissions for rag_db.")
        elif "modulenotfounderror" in error_lower or "importerror" in error_lower:
            self.log_message.emit("RAGManager", "error", "Missing Python module. Try reinstalling dependencies.")
        elif "sentence" in error_lower and "transform" in error_lower:
            self.log_message.emit("RAGManager", "error", "Embedding model download failed. Check internet connection.")
        elif "chromadb" in error_lower or "sqlite" in error_lower:
            self.log_message.emit("RAGManager", "error",
                                  "Database error. Try deleting the rag_db directory and restarting.")

    def terminate_rag_server(self):
        """Terminate the RAG server process."""
        if hasattr(self, 'output_timer'):
            self.output_timer.stop()

        if self.rag_server_process and self.rag_server_process.poll() is None:
            self.log_message.emit("RAGManager", "info",
                                  f"Terminating RAG server process (PID: {self.rag_server_process.pid})...")
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
        if not hasattr(self, 'project_manager') or not self.project_manager:
            self.log_message.emit("RAGManager", "error", "Project manager is not available.")
            return

        if not self.project_manager.active_project_path:
            self.log_message.emit("RAGManager", "error", "No active project to ingest.")
            return

        project_path = self.project_manager.active_project_path
        self.log_message.emit("RAGManager", "info", f"Ingesting active project: {project_path}")
        asyncio.create_task(self.ingest_from_directory(str(project_path)))

    async def ingest_from_directory(self, directory_path: str):
        """Ingests all supported files from a directory into the RAG system."""
        try:
            self.log_message.emit("RAGManager", "info", f"Starting ingestion from: {directory_path}")

            # Scan directory
            scanned_files = self.scanner.scan(directory_path)
            if not scanned_files:
                self.log_message.emit("RAGManager", "warning", "No supported files found for ingestion.")
                return

            self.log_message.emit("RAGManager", "info", f"Found {len(scanned_files)} files to process.")

            # Chunk all files
            all_chunks = []
            for file_path in scanned_files:
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    chunks = self.chunker.chunk_document(content, str(file_path))
                    all_chunks.extend(chunks)
                    self.log_message.emit("RAGManager", "info", f"Chunked {file_path.name}: {len(chunks)} chunks")
                except Exception as e:
                    self.log_message.emit("RAGManager", "warning", f"Failed to chunk {file_path.name}: {e}")

            if not all_chunks:
                self.log_message.emit("RAGManager", "warning", "No chunks generated. Ingestion aborted.")
                return

            self.log_message.emit("RAGManager", "info", f"Chunking complete. Ingesting {len(all_chunks)} chunks...")
            success, message = await self.rag_service.add(all_chunks)

            if success:
                self.log_message.emit("RAGManager", "success", f"Ingestion complete. {message}")
            else:
                self.log_message.emit("RAGManager", "error", f"Ingestion failed. {message}")

        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Ingestion process failed: {e}")


    def check_server_status_async(self):
        """Check server status asynchronously."""
        asyncio.create_task(self._check_and_log_status())

    async def _check_and_log_status(self):
        """Check and log server status changes."""
        is_now_connected = await self.rag_service.check_connection()
        process_is_running = (self.rag_server_process and self.rag_server_process.poll() is None)

        if self._last_connection_status != is_now_connected:
            if is_now_connected:
                self.log_message.emit("RAGManager", "success", "RAG service is running and responding.")
            else:
                self.log_message.emit("RAGManager", "info", "RAG service is not responding.")
            self._last_connection_status = is_now_connected

        if self._last_process_status != process_is_running:
            if not process_is_running and self.rag_server_process:
                if self._last_process_status is True:
                    self.log_message.emit("RAGManager", "error", "RAG server process has terminated unexpectedly.")
                    # Try to get any remaining error output
                    self._process_server_output()
                self.rag_server_process = None
            self._last_process_status = process_is_running