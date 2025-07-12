# src/ava/core/project_manager.py
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

from src.ava.core.git_manager import GitManager
from src.ava.core.venv_manager import VenvManager


class ProjectManager:
    """
    Manages project lifecycles by coordinating Git and Venv managers.
    This class handles the high-level state of the active project.
    """
    def __init__(self, workspace_path: str = "workspace"):
        self.workspace_root = Path(workspace_path).resolve()
        self.workspace_root.mkdir(exist_ok=True)

        self.active_project_path: Optional[Path] = None
        self.git_manager: Optional[GitManager] = None
        self.venv_manager: Optional[VenvManager] = None
        self.is_existing_project: bool = False

    def clear_active_project(self):
        """Resets the active project context."""
        print("[ProjectManager] Clearing active project.")
        self.active_project_path = None
        self.git_manager = None
        self.venv_manager = None
        self.is_existing_project = False

    @property
    def active_project_name(self) -> str:
        return self.active_project_path.name if self.active_project_path else "(none)"

    @property
    def venv_python_path(self) -> Optional[Path]:
        """Delegates getting the venv Python path."""
        return self.venv_manager.python_path if self.venv_manager else None

    @property
    def is_venv_active(self) -> bool:
        """Delegates checking the venv status."""
        return self.venv_manager.is_active if self.venv_manager else False

    def get_venv_info(self) -> dict:
        """Delegates getting venv info."""
        if self.venv_manager:
            return self.venv_manager.get_info()
        return {"active": False, "reason": "No project"}

    def new_project(self, project_name: str = "New_Project") -> Optional[str]:
        """Creates a new project directory, repo, and virtual environment."""
        timestamp = datetime.now().strftime("%Ym%d_%H%M%S")
        dir_name = f"{''.join(c for c in project_name if c.isalnum())}_{timestamp}"
        project_path = self.workspace_root / dir_name
        project_path.mkdir(parents=True, exist_ok=True)
        print(f"[ProjectManager] Creating new project at: {project_path}")

        self.active_project_path = project_path
        self.is_existing_project = False
        self.git_manager = GitManager(project_path)
        self.venv_manager = VenvManager(project_path)

        if self.git_manager.repo:
            self.git_manager.init_repo_for_new_project()
        else:
            print("[ProjectManager] GitManager failed to initialize a repository.")

        if not self.venv_manager.create_venv():
            print("[ProjectManager] CRITICAL: VenvManager failed to create a virtual environment.")
            shutil.rmtree(project_path, ignore_errors=True)
            self.clear_active_project()
            return None

        print(f"[ProjectManager] Successfully created new project: {project_path}")
        return str(project_path)

    def load_project(self, path: str) -> Optional[str]:
        """Loads an existing project, initializing managers for it."""
        project_path = Path(path).resolve()
        if not project_path.is_dir():
            print(f"[ProjectManager] Load failed: {path} is not a directory.")
            return None

        print(f"[ProjectManager] Loading project from: {project_path}")
        self.active_project_path = project_path
        self.is_existing_project = True
        self.git_manager = GitManager(project_path)
        self.venv_manager = VenvManager(project_path)

        if self.git_manager.repo:
            self.git_manager.ensure_initial_commit()
        else:
            print("[ProjectManager] Project loaded, but Git features will be unavailable.")

        if not self.venv_manager.is_active:
            print("[ProjectManager] Warning: No virtual environment found. Please run install command.")

        print(f"[ProjectManager] Project loaded: {self.active_project_path}")
        return str(self.active_project_path)

    def get_project_files(self) -> dict[str, str]:
        """Reads all relevant text files from the project directory."""
        if not self.active_project_path: return {}
        project_files = {}
        ignore_dirs = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'dist', 'build', 'rag_db'}
        allowed_extensions = {
            '.py', '.md', '.txt', '.json', '.toml', '.ini', '.cfg', '.yaml', '.yml',
            '.html', '.css', '.js', '.ts'
        }
        common_filenames = {'Dockerfile', '.gitignore', '.env'}

        for item in self.active_project_path.rglob('*'):
            if any(part in ignore_dirs for part in item.relative_to(self.active_project_path).parts):
                continue
            if item.is_file() and (item.suffix.lower() in allowed_extensions or item.name in common_filenames):
                try:
                    project_files[item.relative_to(self.active_project_path).as_posix()] = item.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    pass
        return project_files

    def read_file(self, relative_path: str) -> Optional[str]:
        if not self.active_project_path: return None
        full_path = self.active_project_path / relative_path
        if not full_path.exists(): return None
        try:
            return full_path.read_text(encoding='utf-8')
        except Exception:
            return None

    def save_and_commit_files(self, files: dict[str, str], commit_message: str):
        if self.git_manager:
            self.git_manager.write_and_stage_files(files)
            self.git_manager.commit_staged_files(commit_message)

    def get_git_diff(self) -> str:
        return self.git_manager.get_diff() if self.git_manager else "Git not available."

    def begin_modification_session(self) -> Optional[str]:
        return self.git_manager.begin_modification_session() if self.git_manager else None

    def rename_item(self, relative_item_path_str: str, new_name_str: str) -> tuple[bool, str, Optional[str]]:
        if self.git_manager:
            return self.git_manager.rename_item(relative_item_path_str, new_name_str)
        return False, "Git not available.", None

    def delete_items(self, relative_item_paths: List[str]) -> tuple[bool, str]:
        if self.git_manager:
            return self.git_manager.delete_items(relative_item_paths)
        return False, "Git not available."

    def create_file(self, relative_parent_dir_str: str, new_filename_str: str) -> tuple[bool, str, Optional[str]]:
        if self.git_manager:
            return self.git_manager.create_file(relative_parent_dir_str, new_filename_str)
        return False, "Git not available.", None

    def create_folder(self, relative_parent_dir_str: str, new_folder_name_str: str) -> tuple[bool, str, Optional[str]]:
        if self.git_manager:
            return self.git_manager.create_folder(relative_parent_dir_str, new_folder_name_str)
        return False, "Git not available.", None

    def move_item(self, relative_item_path_str: str, relative_target_dir_str: str, new_name_str: Optional[str] = None) -> tuple[bool, str, Optional[str]]:
        if self.git_manager:
            return self.git_manager.move_item(relative_item_path_str, relative_target_dir_str, new_name_str)
        return False, "Git not available.", None

    def copy_external_items(self, source_abs_paths: List[str], target_project_rel_dir: str) -> tuple[bool, str, List[Dict[str, str]]]:
        if self.git_manager:
            return self.git_manager.copy_external_items(source_abs_paths, target_project_rel_dir)
        return False, "Git not available.", []

    def stage_file(self, relative_path_str: str) -> tuple[bool, str]:
        if self.git_manager:
            return self.git_manager.stage_file(relative_path_str)
        return False, "Git not available."