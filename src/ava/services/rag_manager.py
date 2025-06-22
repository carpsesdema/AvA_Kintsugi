# src/ava/services/rag_manager.py
import asyncio
import subprocess
import sys
import threading
import queue
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QFileDialog

from src.ava.services.rag_service import RAGService
from src.ava.services.directory_scanner_service import DirectoryScannerService
from src.ava.services.chunking_service import ChunkingService


class RAGManager(QObject):
    """
    Manages the RAG pipeline with enhanced error capture and diagnostics.
    """
    log_message = Signal(str, str, str)

    def __init__(self, event_bus, project_root: Path):
        super().__init__()
        self.event_bus = event_bus
        self.project_root = project_root
        self.project_manager = None

        self.rag_service = RAGService()
        self.scanner = DirectoryScannerService()
        self.chunker = ChunkingService()

        self.rag_server_process = None
        self._last_connection_status = None
        self._last_process_status = None
        self._server_output_queue = queue.Queue()
        self._server_error_queue = queue.Queue()

        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self.check_server_status_async)
        self.status_check_timer.start(10000)

        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )
        self.event_bus.subscribe("application_shutdown", self.terminate_rag_server)
        print("[RAGManager] Initialized with enhanced error capture.")

    def set_project_manager(self, project_manager):
        self.project_manager = project_manager

    async def launch_rag_server(self):
        if self.rag_server_process and self.rag_server_process.poll() is None:
            self.log_message.emit("RAGManager", "info", "RAG server process is already running.")
            return

        self.log_message.emit("RAGManager", "info", "Starting RAG server automatically...")
        try:
            if not self._perform_preflight_checks():
                return

            python_executable = sys.executable
            # --- THIS IS THE PATH FIX ---
            server_script_path = self.project_root / "src" / "ava" / "rag_server.py"
            requirements_path = self.project_root / "src" / "ava" / "requirements_rag.txt"
            # --- END OF FIX ---

            if not await self._install_dependencies(python_executable, requirements_path):
                return
            self._launch_server_process(python_executable, server_script_path)
            self._start_output_monitoring()
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Failed to launch RAG server automatically: {e}")

    def _perform_preflight_checks(self) -> bool:
        # --- THIS IS THE PATH FIX ---
        server_script_path = self.project_root / "src" / "ava" / "rag_server.py"
        requirements_path = self.project_root / "src" / "ava" / "requirements_rag.txt"
        # --- END OF FIX ---

        if not server_script_path.exists():
            msg = f"Could not find rag_server.py at {server_script_path}"
            self.log_message.emit("RAGManager", "error", msg)
            return False

        if not requirements_path.exists():
            msg = f"Could not find requirements_rag.txt at {requirements_path}"
            self.log_message.emit("RAGManager", "error", msg)
            return False

        if not self._check_port_availability():
            self.log_message.emit("RAGManager", "warning", "Port 8001 appears to be in use")
        if not self._check_database_permissions():
            return False
        return True

    def _check_port_availability(self) -> bool:
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', 8001))
                return True
        except OSError:
            return False

    def _check_database_permissions(self) -> bool:
        try:
            rag_db_path = self.project_root / "rag_db"
            rag_db_path.mkdir(exist_ok=True)
            test_file = rag_db_path / "test_permissions.tmp"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Cannot write to rag_db directory: {e}")
            return False

    async def _install_dependencies(self, python_executable: str, requirements_path: Path) -> bool:
        self.log_message.emit("RAGManager", "info", f"Installing RAG dependencies from {requirements_path}...")
        try:
            process = await asyncio.create_subprocess_exec(
                python_executable, "-m", "pip", "install", "-r", str(requirements_path),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

            if process.returncode != 0:
                error_msg = f"Failed to install RAG dependencies: {stderr.decode()}"
                self.log_message.emit("RAGManager", "error", error_msg)
                return False
            self.log_message.emit("RAGManager", "success", "RAG dependencies installed successfully.")
            return True
        except asyncio.TimeoutError:
            self.log_message.emit("RAGManager", "error", "Dependency installation timed out")
            return False
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Dependency installation failed: {e}")
            return False

    def _launch_server_process(self, python_executable: str, server_script_path: Path):
        try:
            while not self._server_output_queue.empty(): self._server_output_queue.get()
            while not self._server_error_queue.empty(): self._server_error_queue.get()

            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.rag_server_process = subprocess.Popen(
                [python_executable, str(server_script_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                universal_newlines=True, creationflags=creation_flags,
                cwd=self.project_root # Set CWD to ensure rag_db is created at the project root
            )
            self.log_message.emit("RAGManager", "info", f"RAG server process started with PID: {self.rag_server_process.pid}")
            self._last_connection_status = None
            self._last_process_status = None
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Failed to start RAG server process: {e}")
            raise

    def _start_output_monitoring(self):
        threading.Thread(target=self._monitor_server_output, args=(self.rag_server_process.stdout, self._server_output_queue, "OUTPUT"), daemon=True).start()
        threading.Thread(target=self._monitor_server_output, args=(self.rag_server_process.stderr, self._server_error_queue, "ERROR"), daemon=True).start()
        self.output_timer = QTimer()
        self.output_timer.timeout.connect(self._process_server_output)
        self.output_timer.start(1000)

    def _monitor_server_output(self, pipe, output_queue, output_type):
        try:
            for line in iter(pipe.readline, ''):
                if line: output_queue.put((output_type, line.strip()))
            pipe.close()
        except Exception as e:
            output_queue.put((output_type, f"Monitoring error: {e}"))

    def _process_server_output(self):
        while not self._server_output_queue.empty():
            try:
                output_type, line = self._server_output_queue.get_nowait()
                if line: self.log_message.emit("RAGServer", "info", f"[{output_type}] {line}")
            except queue.Empty: break
        while not self._server_error_queue.empty():
            try:
                output_type, line = self._server_error_queue.get_nowait()
                if line:
                    self.log_message.emit("RAGServer", "error", f"[{output_type}] {line}")
                    self._analyze_error_line(line)
            except queue.Empty: break

    def _analyze_error_line(self, error_line: str):
        error_lower = error_line.lower()
        if "address already in use" in error_lower: self.log_message.emit("RAGManager", "error", "Port 8001 is already in use.")
        elif "permission denied" in error_lower: self.log_message.emit("RAGManager", "error", "Permission denied for rag_db.")
        elif "modulenotfounderror" in error_lower: self.log_message.emit("RAGManager", "error", "Missing module. Reinstalling dependencies.")
        elif "sentence" in error_lower: self.log_message.emit("RAGManager", "error", "Embedding model download failed.")
        elif "chromadb" in error_lower: self.log_message.emit("RAGManager", "error", "Database error. Try deleting rag_db.")

    def terminate_rag_server(self):
        if hasattr(self, 'output_timer') and self.output_timer.isActive(): self.output_timer.stop()
        if hasattr(self, 'status_check_timer') and self.status_check_timer.isActive(): self.status_check_timer.stop()
        if self.rag_server_process and self.rag_server_process.poll() is None:
            self.log_message.emit("RAGManager", "info", f"Terminating RAG server (PID: {self.rag_server_process.pid})...")
            self.rag_server_process.terminate()
            try:
                self.rag_server_process.wait(timeout=5)
                self.log_message.emit("RAGManager", "success", "RAG server terminated.")
            except subprocess.TimeoutExpired:
                self.log_message.emit("RAGManager", "warning", "RAG server did not terminate gracefully. Killing.")
                self.rag_server_process.kill()
            self.rag_server_process = None
        self._last_connection_status = None
        self._last_process_status = None

    def open_scan_directory_dialog(self, parent_widget=None):
        directory = QFileDialog.getExistingDirectory(parent_widget, "Select Directory to Add to Knowledge Base", str(Path.home()))
        if directory:
            self.log_message.emit("RAGManager", "info", f"User selected directory: {directory}")
            asyncio.create_task(self.ingest_from_directory(directory))

    def ingest_active_project(self):
        if not hasattr(self, 'project_manager') or not self.project_manager or not self.project_manager.active_project_path:
            self.log_message.emit("RAGManager", "error", "No active project to ingest.")
            return
        project_path = self.project_manager.active_project_path
        self.log_message.emit("RAGManager", "info", f"Ingesting active project: {project_path}")
        asyncio.create_task(self.ingest_from_directory(str(project_path)))

    async def ingest_from_directory(self, directory_path: str):
        try:
            self.log_message.emit("RAGManager", "info", f"Starting ingestion from: {directory_path}")
            scanned_files = self.scanner.scan(directory_path)
            if not scanned_files:
                self.log_message.emit("RAGManager", "warning", "No supported files found.")
                return
            self.log_message.emit("RAGManager", "info", f"Found {len(scanned_files)} files.")
            all_chunks = []
            for file_path in scanned_files:
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    chunks = self.chunker.chunk_document(content, str(file_path))
                    all_chunks.extend(chunks)
                except Exception as e:
                    self.log_message.emit("RAGManager", "warning", f"Failed to chunk {file_path.name}: {e}")
            if not all_chunks:
                self.log_message.emit("RAGManager", "warning", "No chunks generated.")
                return
            self.log_message.emit("RAGManager", "info", f"Ingesting {len(all_chunks)} chunks...")
            success, message = await self.rag_service.add(all_chunks)
            if success: self.log_message.emit("RAGManager", "success", f"Ingestion complete. {message}")
            else: self.log_message.emit("RAGManager", "error", f"Ingestion failed. {message}")
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Ingestion process failed: {e}")

    def check_server_status_async(self):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running(): asyncio.create_task(self._check_and_log_status())
        except RuntimeError: pass

    async def _check_and_log_status(self):
        is_now_connected = await self.rag_service.check_connection()
        process_is_running = (self.rag_server_process and self.rag_server_process.poll() is None)
        if self._last_connection_status != is_now_connected:
            msg, level = ("RAG service is running.", "success") if is_now_connected else ("RAG service not responding.", "info")
            self.log_message.emit("RAGManager", level, msg)
            self._last_connection_status = is_now_connected
        if self._last_process_status != process_is_running:
            if not process_is_running and self.rag_server_process and self._last_process_status:
                self.log_message.emit("RAGManager", "error", "RAG server process terminated unexpectedly.")
                self._process_server_output()
            self.rag_server_process = None
            self._last_process_status = process_is_running