# kintsugi_ava/core/project_manager.py
# Handles creating, loading, and managing project directories.

from pathlib import Path
from datetime import datetime
import shutil


class ProjectManager:
    """Manages project lifecycles within the workspace."""

    def __init__(self, workspace_path: str = "workspace"):
        self.workspace_root = Path(workspace_path)
        self.workspace_root.mkdir(exist_ok=True)
        self.current_project_path = None

    def create_new_project(self, project_name: str = "New_Project"):
        """Creates a new, timestamped project directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize the project name for the directory
        sanitized_name = "".join(c for c in project_name if c.isalnum() or c in ('_', '-')).rstrip()
        dir_name = f"{sanitized_name}_{timestamp}"

        self.current_project_path = self.workspace_root / dir_name
        self.current_project_path.mkdir()
        print(f"[ProjectManager] Created new project at: {self.current_project_path}")
        return self.current_project_path

    def load_project(self, path: str):
        """Sets the current project path."""
        project_path = Path(path)
        if project_path.is_dir() and project_path.exists():
            self.current_project_path = project_path
            print(f"[ProjectManager] Loaded project: {self.current_project_path}")
            return self.current_project_path
        return None

    def save_files_to_project(self, files: dict[str, str]):
        """Saves generated files to the current project directory."""
        if not self.current_project_path:
            print("[ProjectManager] Error: No project is currently loaded. Creating a new one.")
            self.create_new_project()

        for filename, content in files.items():
            file_path = self.current_project_path / filename
            # Ensure parent directories exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
        print(f"[ProjectManager] Saved {len(files)} files to {self.current_project_path}")