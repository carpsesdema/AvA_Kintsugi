# kintsugi_ava/core/project_manager.py
# V2: Aligns with the interface used by Application and other services.

from pathlib import Path
from datetime import datetime
import shutil
import os


class ProjectManager:
    """Manages project lifecycles, including creation, loading, and file access."""

    def __init__(self, workspace_path: str = "workspace"):
        self.workspace_root = Path(workspace_path)
        self.workspace_root.mkdir(exist_ok=True)
        self.active_project_path: Path | None = None
        self.is_existing_project: bool = False

    @property
    def active_project_name(self) -> str:
        """Returns the name of the active project folder, or '(none)'."""
        return self.active_project_path.name if self.active_project_path else "(none)"

    def new_project(self, project_name: str = "New_Project") -> str:
        """Creates a new, timestamped project directory and sets it as active."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_name = "".join(c for c in project_name if c.isalnum() or c in ('_', '-')).rstrip()
        dir_name = f"{sanitized_name}_{timestamp}"

        self.active_project_path = self.workspace_root / dir_name
        self.active_project_path.mkdir()
        self.is_existing_project = False  # This is a new, empty project
        print(f"[ProjectManager] Created new project at: {self.active_project_path}")
        return str(self.active_project_path)

    def load_project(self, path: str) -> str | None:
        """Sets an existing directory as the active project."""
        project_path = Path(path)
        if project_path.is_dir() and project_path.exists():
            self.active_project_path = project_path
            self.is_existing_project = True  # This project was loaded from disk
            print(f"[ProjectManager] Loaded project: {self.active_project_path}")
            return str(self.active_project_path)
        return None

    def save_files_to_project(self, files: dict[str, str]):
        """Saves generated files to the active project directory."""
        if not self.active_project_path:
            print("[ProjectManager] Error: No project is active. Creating a new one to save files.")
            self.new_project() # Call the corrected method name

        for filename, content in files.items():
            file_path = self.active_project_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
        print(f"[ProjectManager] Saved {len(files)} files to {self.active_project_path}")

    def get_project_files(self) -> dict[str, str]:
        """Reads all readable text files in the active project directory."""
        if not self.active_project_path:
            return {}

        print(f"[ProjectManager] Getting project files from: {self.active_project_path}")
        project_files = {}
        ignore_list = ['.git', 'venv', '.venv', '__pycache__', 'node_modules', 'build', 'dist', '.idea', '.vscode', 'rag_db']

        for root, dirs, files in os.walk(self.active_project_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in ignore_list]
            for file in files:
                try:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(self.active_project_path)
                    # Simple check to avoid trying to read binary files
                    if file_path.suffix.lower() in ['.py', '.js', '.html', '.css', '.md', '.txt', '.json', '.toml', '.pyc', '.gitignore', '.env']:
                        project_files[str(relative_path)] = file_path.read_text(encoding='utf-8')
                except Exception:
                    # Ignore files that can't be read
                    pass
        print(f"[ProjectManager] Found {len(project_files)} readable files.")
        return project_files