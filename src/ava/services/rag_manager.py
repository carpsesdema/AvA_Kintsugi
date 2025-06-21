# src/ava/services/rag_manager.py
import asyncio
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread, QMetaObject, Q_ARG, Qt
from PySide6.QtWidgets import QMessageBox, QFileDialog

from .rag_service import RAGService
from .directory_scanner_service import DirectoryScannerService
from .chunking_service import ChunkingService
from .rag_worker import RAGWorker  # The new worker class


class RAGManager(QObject):
    """
    Manages the RAG pipeline by running the RAGWorker on a separate QThread,
    eliminating the need for a separate server process.
    """
    log_message = Signal(str, str, str)  # Emits (source, type, message)

    # Signals to forward results from the worker
    query_result_received = Signal(str)
    add_result_received = Signal(bool, str)

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus

        # RAG services that run in the main thread
        self.scanner = DirectoryScannerService()
        self.chunker = ChunkingService()

        # The RAGService now acts as a thread-safe proxy to the worker
        self.rag_service = RAGService(self)

        # Worker and thread management
        self.rag_thread = None
        self.rag_worker = None
        self._is_running = False

        # Connect log messages to the main application event bus
        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )
        self.event_bus.subscribe("application_shutdown", self.shutdown)

        print("[RAGManager] Refactored to use in-process QThread worker.")

    def set_project_manager(self, project_manager):
        self.project_manager = project_manager

    def is_service_running(self):
        return self._is_running

    def launch_rag_server(self, parent_widget=None):
        """
        Starts the RAG service on a background thread.
        This replaces the old subprocess-based server launch.
        """
        if self.rag_thread and self.rag_thread.isRunning():
            QMessageBox.information(parent_widget, "Already Running", "The RAG service is already running.")
            return

        self.log_message.emit("RAGManager", "info", "Starting RAG service on a background thread...")

        self.rag_thread = QThread()
        self.rag_worker = RAGWorker()
        self.rag_worker.moveToThread(self.rag_thread)

        # Connect worker signals to manager slots
        self.rag_thread.started.connect(self.rag_worker.initialize)
        self.rag_worker.initialized.connect(self._on_worker_initialized)
        self.rag_worker.log_message.connect(lambda type, msg: self.log_message.emit("RAGWorker", type, msg))

        # Forward results to the RAGService proxy
        self.rag_worker.query_finished.connect(self.query_result_received)
        self.rag_worker.add_finished.connect(self.add_result_received)

        self.rag_thread.start()

    def stop_rag_service(self):
        """Stops the RAG worker thread."""
        if self.rag_thread and self.rag_thread.isRunning():
            self.log_message.emit("RAGManager", "info", "Stopping RAG service thread...")
            self.rag_thread.quit()
            # Wait 5s for graceful shutdown
            if not self.rag_thread.wait(5000):
                self.log_message.emit("RAGManager", "warning", "RAG thread did not quit gracefully, terminating.")
                self.rag_thread.terminate()

            self._is_running = False
            self.rag_thread = None
            self.rag_worker = None
            self.log_message.emit("RAGManager", "info", "RAG service stopped.")

    def shutdown(self):
        """Public method to be called by ServiceManager for graceful shutdown."""
        self.stop_rag_service()

    def _on_worker_initialized(self, success: bool, message: str):
        if success:
            self._is_running = True
            self.log_message.emit("RAGManager", "success", message)
        else:
            self._is_running = False
            self.log_message.emit("RAGManager", "error", f"RAG worker failed to initialize: {message}")
            self.stop_rag_service()  # Clean up the failed thread

    def trigger_query(self, query_text: str, n_results: int):
        """Thread-safely invokes the query method on the worker."""
        if self._is_running and self.rag_worker:
            QMetaObject.invokeMethod(self.rag_worker, "perform_query", Qt.ConnectionType.QueuedConnection,
                                     Q_ARG(str, query_text), Q_ARG(int, n_results))

    def trigger_add(self, chunks: list):
        """Thread-safely invokes the add method on the worker."""
        if self._is_running and self.rag_worker:
            QMetaObject.invokeMethod(self.rag_worker, "perform_add", Qt.ConnectionType.QueuedConnection,
                                     Q_ARG(list, chunks))

    def open_scan_directory_dialog(self, parent_widget=None):
        directory = QFileDialog.getExistingDirectory(
            parent_widget, "Select Directory to Add to Knowledge Base", str(Path.home())
        )
        if directory:
            self.log_message.emit("RAGManager", "info", f"User selected directory for ingestion: {directory}")
            asyncio.create_task(self.ingest_from_directory(directory))

    def ingest_active_project(self):
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
        try:
            self.log_message.emit("RAGManager", "info", f"Starting ingestion from: {directory_path}")
            scanned_files = self.scanner.scan(directory_path)
            if not scanned_files:
                self.log_message.emit("RAGManager", "warning", "No supported files found for ingestion.")
                return

            self.log_message.emit("RAGManager", "info", f"Found {len(scanned_files)} files to process.")
            all_chunks = []
            for file_path in scanned_files:
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    chunks = self.chunker.chunk_document(content, str(file_path))
                    all_chunks.extend(chunks)
                except Exception as e:
                    self.log_message.emit("RAGManager", "warning", f"Failed to chunk {file_path.name}: {e}")

            if not all_chunks:
                self.log_message.emit("RAGManager", "warning", "No chunks generated. Ingestion aborted.")
                return

            self.log_message.emit("RAGManager", "info",
                                  f"Chunking complete. Requesting ingestion of {len(all_chunks)} chunks...")

            # Use RAGService to asynchronously trigger 'add' and wait for result
            success, message = await self.rag_service.add(all_chunks)

            if success:
                self.log_message.emit("RAGManager", "success", f"Ingestion complete. {message}")
            else:
                self.log_message.emit("RAGManager", "error", f"Ingestion failed. {message}")

        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Ingestion process failed: {e}")