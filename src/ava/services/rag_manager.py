# src/ava/services/rag_manager.py
import asyncio
from pathlib import Path
from typing import List, Dict, Any  # Added for type hinting

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.ava.services.rag_service import RAGService
from src.ava.services.directory_scanner_service import DirectoryScannerService
from src.ava.services.chunking_service import ChunkingService
from src.ava.core.event_bus import EventBus  # Added EventBus import


class RAGManager(QObject):
    """
    Manages RAG pipeline interactions. Process lifecycle is now handled by ServiceManager.
    """
    log_message = Signal(str, str, str)

    def __init__(self, event_bus: EventBus, project_root: Path):  # Added EventBus type hint
        super().__init__()
        self.event_bus = event_bus
        self.project_root = project_root
        self.project_manager = None  # Should be type hinted: Optional[ProjectManager]
        self.rag_service = RAGService()
        self.scanner = DirectoryScannerService()
        self.chunker = ChunkingService()

        self.log_message.connect(
            lambda src, type, msg: self.event_bus.emit("log_message_received", src, type, msg)
        )
        print("[RAGManager] Initialized for RAG service communication.")

    def set_project_manager(self, project_manager):  # Add type hint: project_manager: ProjectManager
        self.project_manager = project_manager

    async def switch_project_context(self, project_path: Path):
        """Tells the RAG service to switch its database to the new project path."""
        self.log_message.emit("RAGManager", "info", f"Switching RAG PROJECT context to project: {project_path.name}")
        success, msg = await self.rag_service.set_project_db(str(project_path))
        if success:
            self.log_message.emit("RAGManager", "success", "RAG project context switched successfully.")
        else:
            self.log_message.emit("RAGManager", "error", f"Failed to switch RAG project context: {msg}")

    def open_add_knowledge_dialog(self, parent_widget=None):
        """
        Opens a file dialog to select one or more files to add to the
        CURRENT PROJECT'S knowledge base.
        """
        if not self.project_manager or not self.project_manager.active_project_path:
            QMessageBox.warning(parent_widget, "No Project Loaded", "Please load a project before adding knowledge.")
            return

        file_paths_str, _ = QFileDialog.getOpenFileNames(
            parent_widget,
            "Add File(s) to Project Knowledge Base",
            str(Path.home()),  # Start at user's home directory
            "All Files (*);;Text Files (*.txt);;Markdown (*.md);;Python Files (*.py)"  # Added Python
        )
        if file_paths_str:
            self.log_message.emit("RAGManager", "info",
                                  f"User selected {len(file_paths_str)} file(s) to add to project KB.")
            path_objects = [Path(fp) for fp in file_paths_str]
            # Explicitly target "project" collection
            asyncio.create_task(self.ingest_files(path_objects, target_collection="project"))

    def ingest_active_project(self):
        """Ingests all source files from the currently active project into the PROJECT knowledge base."""
        if not self.project_manager or not self.project_manager.active_project_path:
            self.log_message.emit("RAGManager", "error", "No active project to ingest into project KB.")
            return
        project_path = self.project_manager.active_project_path
        self.log_message.emit("RAGManager", "info",
                              f"Ingesting all source files from active project '{project_path.name}' into PROJECT KB.")
        files_to_ingest = self.scanner.scan(str(project_path))
        if files_to_ingest:
            # Explicitly target "project" collection
            asyncio.create_task(self.ingest_files(files_to_ingest, target_collection="project"))
        else:
            self.log_message.emit("RAGManager", "warning", "No supported source files found in the project to ingest.")

    async def ingest_files(self, file_paths: List[Path], target_collection: str):
        """
        Chunks and ingests a list of files into the specified RAG collection.

        Args:
            file_paths: List of Path objects for the files to ingest.
            target_collection: "project" or "global".
        """
        try:
            self.log_message.emit("RAGManager", "info",
                                  f"Starting ingestion for {len(file_paths)} file(s) into '{target_collection}' KB...")
            all_chunks: List[Dict[str, Any]] = []  # Ensure all_chunks is typed
            for file_path in file_paths:
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    chunks = self.chunker.chunk_document(content, str(file_path))
                    all_chunks.extend(chunks)
                except Exception as e:
                    self.log_message.emit("RAGManager", "warning",
                                          f"Failed to chunk {file_path.name} for '{target_collection}' KB: {e}")

            if not all_chunks:
                self.log_message.emit("RAGManager", "warning",
                                      f"No content to ingest for '{target_collection}' KB after chunking.")
                return

            self.log_message.emit("RAGManager", "info",
                                  f"Ingesting {len(all_chunks)} chunks into '{target_collection}' knowledge base...")
            success, message = await self.rag_service.add(all_chunks, target_collection=target_collection)
            if success:
                self.log_message.emit("RAGManager", "success",
                                      f"Ingestion into '{target_collection}' KB complete. {message}")
            else:
                self.log_message.emit("RAGManager", "error",
                                      f"Ingestion into '{target_collection}' KB failed. {message}")
        except Exception as e:
            self.log_message.emit("RAGManager", "error", f"Ingestion process for '{target_collection}' KB failed: {e}")

    # --- NEW METHOD for Global Knowledge ---
    def open_add_global_knowledge_dialog(self, parent_widget=None):
        """
        Opens a directory dialog to select a root directory of code examples
        to add to the GLOBAL knowledge base.
        """
        dir_path_str = QFileDialog.getExistingDirectory(
            parent_widget,
            "Select Directory for Global Knowledge Base (e.g., Python Code Examples)",
            str(Path.home())  # Start at user's home directory
        )

        if dir_path_str:
            directory_path = Path(dir_path_str)
            self.log_message.emit("RAGManager", "info",
                                  f"User selected directory '{directory_path.name}' to add to GLOBAL KB.")

            # Inform user this might take time
            QMessageBox.information(parent_widget, "Global Ingestion Started",
                                    f"Scanning and ingesting '{directory_path.name}' into the global knowledge base. "
                                    "This may take some time depending on the size. "
                                    "Check logs for progress.")

            files_to_ingest = self.scanner.scan(str(directory_path))
            if files_to_ingest:
                # Explicitly target "global" collection
                asyncio.create_task(self.ingest_files(files_to_ingest, target_collection="global"))
            else:
                self.log_message.emit("RAGManager", "warning",
                                      f"No supported files found in '{directory_path.name}' for GLOBAL KB.")
                QMessageBox.warning(parent_widget, "No Files Found",
                                    f"No supported files found in '{directory_path.name}' to add to the global knowledge base.")