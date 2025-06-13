# kintsugi_ava/services/rag_manager.py
# V2: The coordinator for all RAG activities, now with async processing.

import asyncio
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .directory_scanner_service import DirectoryScannerService
from .rag_service import RAGService


class RAGManager(QObject):
    """
    Manages the RAG pipeline, from scanning files to querying the database.
    This class orchestrates the underlying services and handles async operations
    to avoid blocking the UI.
    """
    # Signals for communicating with the UI/Log
    log_message = Signal(str, str, str)  # Emits (source, type, message)

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.scanner_service = DirectoryScannerService()
        self.rag_service = RAGService()
        self._is_scanning = False

        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )
        print("[RAGManager] Initialized.")

    def start_async_initialization(self):
        """
        Starts the RAG service's potentially long initialization process in a
        background task.
        """
        if not self.rag_service.is_initialized:
            self.log_message.emit("RAGManager", "info", "Starting RAG service initialization...")
            asyncio.create_task(self._initialize_rag_service_async())

    async def _initialize_rag_service_async(self):
        """Runs the blocking RAG service initialization in a thread."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.rag_service._initialize)
        if self.rag_service.is_initialized:
            self.log_message.emit("RAGManager", "success", "RAG service is now ready.")
        else:
            self.log_message.emit("RAGManager", "error", "RAG service failed to initialize.")

    def open_scan_directory_dialog(self, parent_widget=None):
        """
        Opens a dialog for the user to select a directory to scan and ingest.
        """
        if self._is_scanning:
            QMessageBox.information(parent_widget, "Scan in Progress",
                                    "A directory scan is already in progress. Please wait for it to finish.")
            return

        if not self.rag_service.is_initialized:
            QMessageBox.warning(parent_widget, "RAG Not Ready",
                                "The RAG service is not ready yet. Please wait for initialization to complete.")
            self.start_async_initialization()  # Try to kick it off again
            return

        directory = QFileDialog.getExistingDirectory(
            parent_widget,
            "Select Directory to Scan for Knowledge",
            str(Path.home())
        )

        if directory:
            self._is_scanning = True
            asyncio.create_task(self.scan_and_ingest_directory_async(directory))

    async def scan_and_ingest_directory_async(self, directory_path: str):
        """
        Coordinates the entire scan-and-ingest process asynchronously.
        """
        try:
            self.log_message.emit("RAGManager", "info", f"Scanning directory: {directory_path}...")

            # Scanning is fast, so we can do it directly
            files_to_process = self.scanner_service.scan(directory_path)

            if not files_to_process:
                self.log_message.emit("RAGManager", "info", "No new supported files found to ingest.")
                return

            self.log_message.emit("RAGManager", "info",
                                  f"Found {len(files_to_process)} files. Starting ingestion (this may take a while)...")

            loop = asyncio.get_running_loop()
            # Ingestion is slow, run it in a thread pool
            processed_count = await loop.run_in_executor(
                None, self.rag_service.ingest_files, files_to_process
            )

            self.log_message.emit("RAGManager", "success",
                                  f"Ingestion complete. Added or updated {processed_count} files in the knowledge base.")

        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"An error occurred during scan and ingest: {e}")
        finally:
            self._is_scanning = False