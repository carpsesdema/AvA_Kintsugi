# src/ava/core/project_manager.py
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

from src.ava.core.venv_manager import VenvManager


class ProjectManager:
    """
    Manages project lifecycles by coordinating file system operations and the VenvManager.
    This class handles the high-level state of the active project.
    """
    def __init__(self, workspace_path: str = "workspace"):
        self.workspace_root = Path(workspace_path).resolve()
        self.workspace_root.mkdir(exist_ok=True)

        self.active_project_path: Optional[Path] = None
        self.venv_manager: Optional[VenvManager] = None
        self.is_existing_project: bool = False

    def clear_active_project(self):
        """Resets the active project context."""
        print("[ProjectManager] Clearing active project.")
        self.active_project_path = None
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
        """Creates a new project directory and virtual environment."""
        timestamp = datetime.now().strftime("%Ym%d_%H%M%S")
        dir_name = f"{''.join(c for c in project_name if c.isalnum())}_{timestamp}"
        project_path = self.workspace_root / dir_name
        project_path.mkdir(parents=True, exist_ok=True)
        print(f"[ProjectManager] Creating new project at: {project_path}")

        self.active_project_path = project_path
        self.is_existing_project = False
        self.venv_manager = VenvManager(project_path)

        # Create virtual environment
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
        self.venv_manager = VenvManager(project_path)

        if not self.venv_manager.is_active:
            print("[ProjectManager] Warning: No virtual environment found. Please run install command.")

        print(f"[ProjectManager] Project loaded: {self.active_project_path}")
        return str(self.active_project_path)

    def get_project_files(self) -> dict[str, str]:
        """Reads all relevant text files from the project directory."""
        if not self.active_project_path: return {}
        project_files = {}
        ignore_dirs = {'.venv', 'venv', '__pycache__', 'node_modules', 'dist', 'build', 'rag_db'}
        allowed_extensions = {
            '.py', '.md', '.txt', '.json', '.toml', '.ini', '.cfg', '.yaml', '.yml',
            '.html', '.css', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.hpp',
            '.cs', '.go', '.rb', '.php', '.sh', '.bat', '.ps1', '.dockerfile',
            '.gitignore', '.env'
        }
        for item in self.active_project_path.rglob('*'):
            if any(part in ignore_dirs for part in item.relative_to(self.active_project_path).parts):
                continue
            if item.is_file() and item.suffix.lower() in allowed_extensions:
                try:
                    project_files[item.relative_to(self.active_project_path).as_posix()] = item.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    pass # Ignore unreadable files
        return project_files

    def read_file(self, relative_path: str) -> Optional[str]:
        if not self.active_project_path: return None
        full_path = self.active_project_path / relative_path
        if not full_path.exists(): return None
        try:
            return full_path.read_text(encoding='utf-8')
        except Exception:
            return None

    # --- New/Re-implemented Methods ---
    def save_files(self, files: dict[str, str]):
        """Writes files to disk."""
        if not self.active_project_path: return
        for relative_path_str, content in files.items():
            full_path = self.active_project_path / relative_path_str
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding='utf-8')
            except Exception as e:
                print(f"[ProjectManager] Error writing file {relative_path_str}: {e}")

    def rename_item(self, relative_item_path_str: str, new_name_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.active_project_path: return False, "No active project.", None
        old_abs_path = self.active_project_path / relative_item_path_str
        new_abs_path = old_abs_path.parent / new_name_str

        if not old_abs_path.exists():
            return False, f"Source item '{relative_item_path_str}' does not exist.", None
        if new_abs_path.exists():
            return False, f"Target name '{new_name_str}' already exists.", None

        try:
            old_abs_path.rename(new_abs_path)
            new_relative_path_str = new_abs_path.relative_to(self.active_project_path).as_posix()
            return True, f"Renamed to '{new_name_str}'.", new_relative_path_str
        except Exception as e:
            return False, f"Error renaming: {e}", None

    def delete_items(self, relative_item_paths: List[str]) -> tuple[bool, str]:
        if not self.active_project_path: return False, "No active project."
        errors = []
        for rel_path_str in relative_item_paths:
            abs_path = self.active_project_path / rel_path_str
            try:
                if abs_path.is_file(): abs_path.unlink()
                elif abs_path.is_dir(): shutil.rmtree(abs_path)
            except Exception as e:
                errors.append(f"Error deleting '{rel_path_str}': {e}")

        if errors:
            return False, "\n".join(errors)
        return True, f"Successfully deleted {len(relative_item_paths)} item(s)."

    def create_file(self, relative_parent_dir_str: str, new_filename_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.active_project_path: return False, "No active project.", None
        parent_abs_path = self.active_project_path / relative_parent_dir_str
        new_file_abs_path = parent_abs_path / new_filename_str
        new_file_rel_path_str = new_file_abs_path.relative_to(self.active_project_path).as_posix()
        try:
            parent_abs_path.mkdir(parents=True, exist_ok=True)
            new_file_abs_path.touch()
            return True, f"File '{new_filename_str}' created.", new_file_rel_path_str
        except Exception as e:
            return False, f"Error creating file: {e}", None

    def create_folder(self, relative_parent_dir_str: str, new_folder_name_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.active_project_path: return False, "No active project.", None
        parent_abs_path = self.active_project_path / relative_parent_dir_str
        new_folder_abs_path = parent_abs_path / new_folder_name_str
        new_folder_rel_path_str = new_folder_abs_path.relative_to(self.project_path).as_posix()
        try:
            new_folder_abs_path.mkdir(parents=True, exist_ok=True)
            return True, f"Folder '{new_folder_name_str}' created.", new_folder_rel_path_str
        except Exception as e:
            return False, f"Error creating folder: {e}", None

    def move_item(self, relative_item_path_str: str, relative_target_dir_str: str, new_name_str: Optional[str] = None) -> tuple[bool, str, Optional[str]]:
        if not self.active_project_path: return False, "No active project.", None
        source_abs_path = self.active_project_path / relative_item_path_str
        target_dir_abs_path = self.active_project_path / relative_target_dir_str

        if not source_abs_path.exists():
            return False, "Source item does not exist.", None
        if not target_dir_abs_path.is_dir():
            return False, "Target must be a directory.", None

        final_name = new_name_str if new_name_str else source_abs_path.name
        destination_abs_path = target_dir_abs_path / final_name

        if destination_abs_path.exists():
            return False, "An item with the same name already exists in the target directory.", None

        try:
            shutil.move(str(source_abs_path), str(destination_abs_path))
            new_final_rel_path = destination_abs_path.relative_to(self.project_path).as_posix()
            return True, "Item moved successfully.", new_final_rel_path
        except Exception as e:
            return False, f"Error moving item: {e}", None

    def copy_external_items(self, source_abs_paths: List[str], target_project_rel_dir: str) -> tuple[bool, str, List[Dict[str, str]]]:
        if not self.active_project_path: return False, "No active repository.", []
        target_dir_abs_path = self.active_project_path / target_project_rel_dir
        target_dir_abs_path.mkdir(parents=True, exist_ok=True)
        copied_infos, errors = [], []
        for src_path_str in source_abs_paths:
            src_path = Path(src_path_str)
            dest_path = target_dir_abs_path / src_path.name
            if dest_path.exists():
                errors.append(f"Item '{src_path.name}' already exists.")
                continue
            try:
                if src_path.is_file(): shutil.copy2(src_path, dest_path)
                else: shutil.copytree(src_path, dest_path)
                new_rel_path = dest_path.relative_to(self.project_path).as_posix()
                copied_infos.append({'original_abs_path': src_path_str, 'new_project_rel_path': new_rel_path})
            except Exception as e:
                errors.append(f"Error copying '{src_path.name}': {e}")
        if errors:
            return False, "\n".join(errors), copied_infos
        return True, f"Copied {len(copied_infos)} items.", copied_infos