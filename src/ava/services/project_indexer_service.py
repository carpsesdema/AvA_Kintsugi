# src/ava/services/project_indexer_service.py
import asyncio
from pathlib import Path
from typing import Dict, List

from src.ava.utils.code_summarizer import CodeSummarizer
from src.ava.core.project_manager import ProjectManager


class ProjectIndexerService:
    """
    Scans a Python project and builds a stateful, in-memory index of structural
    summaries for each file. This index is cached and updated incrementally.
    """

    def __init__(self, project_manager: ProjectManager):
        self.project_manager = project_manager
        self.index: Dict[str, str] = {}
        print("[ProjectIndexer] Initialized.")

    def clear_index(self):
        """Clears the current project index."""
        self.index.clear()
        print("[ProjectIndexer] Index cleared.")

    async def build_index(self, project_root: Path):
        """
        Scans all Python files in a project root and builds the summary index.
        This is an async background task.
        """
        self.clear_index()
        print(f"[ProjectIndexer] Starting async project summary scan: {project_root}")
        py_files_to_process = [
            py_file for py_file in project_root.rglob("*.py")
            if ".venv" not in py_file.parts and "venv" not in py_file.parts
        ]

        for i, py_file in enumerate(py_files_to_process):
            try:
                relative_path_str = str(py_file.relative_to(project_root).as_posix())
                content = py_file.read_text(encoding="utf-8")
                if content.strip():
                    self.index[relative_path_str] = self._get_summary_from_content(content)

                if i % 10 == 0:  # Yield control every 10 files
                    await asyncio.sleep(0)
            except Exception as e:
                print(f"[ProjectIndexer] Warning: Could not parse {py_file.name}: {e}")

        print(f"[ProjectIndexer] Background scan complete. Summarized {len(self.index)} files.")

    def update_index_for_file_content(self, relative_path_str: str, content: str):
        """
        Updates the index for a single file from its content synchronously.
        Used during a generation session.
        """
        if not relative_path_str.endswith('.py'):
            return
        summary = self._get_summary_from_content(content)
        self.index[relative_path_str] = summary
        print(f"[ProjectIndexer] Updated index for: {relative_path_str}")

    async def update_index_for_file_path(self, relative_path: Path, project_root: Path):
        """Updates the index for a single file by reading it from disk."""
        if not str(relative_path).endswith('.py'):
            return
        try:
            full_path = project_root / relative_path
            if full_path.exists() and full_path.is_file():
                content = full_path.read_text(encoding="utf-8")
                self.update_index_for_file_content(relative_path.as_posix(), content)
        except Exception as e:
            print(f"[ProjectIndexer] Error updating index for path {relative_path}: {e}")

    def remove_from_index(self, relative_path_str: str):
        """Removes a file or a directory's contents from the index."""
        # Handle single file deletion
        if relative_path_str in self.index:
            del self.index[relative_path_str]
            print(f"[ProjectIndexer] Removed file from index: {relative_path_str}")

        # Handle directory deletion by removing all files with that prefix
        dir_prefix = relative_path_str + '/'
        keys_to_delete = [
            key for key in self.index
            if key.startswith(dir_prefix)
        ]
        if keys_to_delete:
            for key in keys_to_delete:
                del self.index[key]
            print(f"[ProjectIndexer] Removed {len(keys_to_delete)} files under deleted directory: {relative_path_str}")

    async def handle_file_rename(self, old_rel_path_str: str, new_rel_path_str: str):
        """Handles renaming a file or directory in the index."""
        if not self.project_manager.active_project_path: return

        # Handle single file rename
        if old_rel_path_str in self.index:
            self.index[new_rel_path_str] = self.index.pop(old_rel_path_str)
            print(f"[ProjectIndexer] Renamed file in index: {old_rel_path_str} -> {new_rel_path_str}")
            return

        # Handle directory rename
        old_dir_prefix = old_rel_path_str + '/'
        new_dir_prefix = new_rel_path_str + '/'
        keys_to_rename = [key for key in self.index if key.startswith(old_dir_prefix)]
        if keys_to_rename:
            for old_key in keys_to_rename:
                new_key = new_dir_prefix + old_key[len(old_dir_prefix):]
                self.index[new_key] = self.index.pop(old_key)
            print(
                f"[ProjectIndexer] Renamed {len(keys_to_rename)} files in index for directory: {old_rel_path_str} -> {new_rel_path_str}")

    def _get_summary_from_content(self, content: str) -> str:
        """Generates a structural summary from Python code content."""
        if not content or not content.strip():
            return ""
        try:
            summarizer = CodeSummarizer(content)
            return summarizer.summarize()
        except Exception as e:
            print(f"[ProjectIndexer] Warning: Could not summarize content: {e}")
            return f"# Error: Could not summarize code. {e}"