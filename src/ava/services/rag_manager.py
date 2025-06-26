# src/ava/services/rag_manager.py
import asyncio
import os
import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QFileDialog

from src.ava.services.rag_service import RAGService
from src.ava.services.directory_scanner_service import DirectoryScannerService
from src.ava.services.chunking_service import ChunkingService


class RAGManager(QObject):
    """
    Manages RAG pipeline interactions. Process lifecycle is now handled by ServiceManager.
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
        self._last_connection_status = None

        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self.check_server_status_async)
        self.status_check_timer.start(5000)

        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )
        print("[RAGManager] Initialized for RAG service communication.")

    def set_project_manager(self, project_manager):
        self.project_manager = project_manager

    async def switch_project_context(self, project_path: Path):
        """Tells the RAG service to switch its database to the new project path."""
        self.log_message.emit("RAGManager", "info", f"Switching RAG context to project: {project_path.name}")
        success, msg = await self.rag_service.set_project_db(str(project_path))
        if success:
            self.log_message.emit("RAGManager", "success", "RAG context switched successfully.")
        else:
            self.log_message.emit("RAGManager", "error", f"Failed to switch RAG context: {msg}")

    def check_server_status_async(self):
        try:
            main_loop = asyncio.get_event_loop()
            if main_loop.is_running():
                asyncio.run_coroutine_threadsafe(self._check_and_log_status(), main_loop)
        except RuntimeError:
            pass

    async def _check_and_log_status(self):
        is_now_connected = await self.rag_service.check_connection()
        if self._last_connection_status != is_now_connected:
            msg, level = ("RAG service is running.", "success") if is_now_connected else (
                "RAG service is offline or starting...", "info")
            self.log_message.emit("RAGManager", level, msg)
            self._last_connection_status = is_now_connected

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