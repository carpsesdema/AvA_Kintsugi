# src/ava/services/rag_manager.py
import asyncio
import os
import sys
import threading
from pathlib import Path
import uvicorn

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QFileDialog

from src.ava.rag_server import rag_app, HOST, PORT
from src.ava.services.rag_service import RAGService
from src.ava.services.directory_scanner_service import DirectoryScannerService
from src.ava.services.chunking_service import ChunkingService


class RAGManager(QObject):
    """
    Manages the RAG pipeline by running the Uvicorn server in a separate thread,
    with its own dedicated asyncio event loop to prevent conflicts with qasync.
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

        self.server_thread = None
        self.uvicorn_server = None
        self._last_connection_status = None

        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self.check_server_status_async)
        self.status_check_timer.start(5000)

        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )
        self.event_bus.subscribe("application_shutdown", lambda: asyncio.create_task(self.terminate_rag_server()))
        print("[RAGManager] Initialized for threaded server management.")

    def set_project_manager(self, project_manager):
        self.project_manager = project_manager

    def _run_server_in_thread(self, server: uvicorn.Server):
        """
        Runs the uvicorn server in a dedicated thread with its own event loop,
        explicitly setting a standard policy to avoid qasync conflicts.
        """
        # --- THIS IS THE FIX ---
        try:
            # On Windows, we must set a specific policy to avoid conflicts.
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # Ensure the server knows it should be running
            server.should_exit = False
            loop.run_until_complete(server.serve())
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"RAG server thread error: {e}")
        finally:
            self.log_message.emit("RAGManager", "info", "RAG server thread has exited.")
        # --- END OF FIX ---

    async def launch_rag_server(self):
        """Launches the Uvicorn server in a background thread."""
        if self.server_thread and self.server_thread.is_alive():
            self.log_message.emit("RAGManager", "info", "RAG server thread is already running.")
            return

        self.log_message.emit("RAGManager", "info", "Starting RAG server in a background thread...")
        try:
            db_parent_dir = self._get_db_parent_directory()
            if not self._check_database_permissions(db_parent_dir):
                return

            config = uvicorn.Config("src.ava.rag_server:rag_app", host=HOST, port=PORT, log_level="info",
                                    loop="asyncio")
            self.uvicorn_server = uvicorn.Server(config)

            original_cwd = os.getcwd()
            os.chdir(db_parent_dir)

            self.server_thread = threading.Thread(target=self._run_server_in_thread, args=(self.uvicorn_server,),
                                                  daemon=True)
            self.server_thread.start()

            os.chdir(original_cwd)

            self.log_message.emit("RAGManager", "info", f"RAG server thread started in CWD: {db_parent_dir}")
            await asyncio.sleep(2)
            await self._check_and_log_status()

        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Failed to launch RAG server thread: {e}")
            import traceback
            traceback.print_exc()

    def _get_db_parent_directory(self) -> Path:
        if getattr(sys, 'frozen', False):
            return self.project_root
        else:
            return self.project_root.parent

    def _check_database_permissions(self, db_base_path: Path) -> bool:
        try:
            rag_db_path = db_base_path / "rag_db"
            rag_db_path.mkdir(exist_ok=True, parents=True)
            test_file = rag_db_path / "test_permissions.tmp"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Cannot write to rag_db directory ({rag_db_path}): {e}")
            return False

    async def terminate_rag_server(self):
        """Gracefully shuts down the running Uvicorn server."""
        if self.status_check_timer.isActive():
            self.status_check_timer.stop()

        if self.uvicorn_server and not self.uvicorn_server.should_exit:
            self.log_message.emit("RAGManager", "info", "Sending shutdown signal to RAG server...")
            self.uvicorn_server.should_exit = True

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
            if self.server_thread.is_alive():
                self.log_message.emit("RAGManager", "warning", "RAG server thread did not exit gracefully.")
            else:
                self.log_message.emit("RAGManager", "success", "RAG server thread terminated.")

        self.server_thread = None
        self.uvicorn_server = None
        self._last_connection_status = None

    def open_scan_directory_dialog(self, parent_widget=None):
        directory = QFileDialog.getExistingDirectory(parent_widget, "Select Directory to Add to Knowledge Base",
                                                     str(Path.home()))
        if directory:
            self.log_message.emit("RAGManager", "info", f"User selected directory: {directory}")
            asyncio.create_task(self.ingest_from_directory(directory))

    def ingest_active_project(self):
        if not hasattr(self,
                       'project_manager') or not self.project_manager or not self.project_manager.active_project_path:
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
            if success:
                self.log_message.emit("RAGManager", "success", f"Ingestion complete. {message}")
            else:
                self.log_message.emit("RAGManager", "error", f"Ingestion failed. {message}")
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Ingestion process failed: {e}")

    def check_server_status_async(self):
        try:
            main_loop = asyncio.get_event_loop()
            if main_loop.is_running():
                asyncio.run_coroutine_threadsafe(self._check_and_log_status(), main_loop)
        except RuntimeError:
            pass

    async def _check_and_log_status(self):
        """Checks the connection to the RAG service and updates status."""
        server_is_supposed_to_be_running = (self.uvicorn_server is not None and not self.uvicorn_server.should_exit)

        if not server_is_supposed_to_be_running:
            if self._last_connection_status is not False:
                self.log_message.emit("RAGManager", "info", "RAG service is offline.")
                self._last_connection_status = False
            return

        is_now_connected = await self.rag_service.check_connection()

        if self._last_connection_status != is_now_connected:
            msg, level = ("RAG service is running.", "success") if is_now_connected else (
                "RAG service is starting or not responding...", "info")
            self.log_message.emit("RAGManager", level, msg)
            self._last_connection_status = is_now_connected

        if self.server_thread and not self.server_thread.is_alive() and server_is_supposed_to_be_running:
            self.log_message.emit("RAGManager", "error", "RAG server thread terminated unexpectedly.")
            self.uvicorn_server.should_exit = True