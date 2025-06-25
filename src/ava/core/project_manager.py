import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
# REMOVED: from dotenv import load_dotenv
from typing import List, Optional, Dict

try:
    import git
    from git.exc import InvalidGitRepositoryError, GitCommandError

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class ProjectManager:
    """
    Manages project lifecycles, including Git versioning and virtual environments.
    """

    def __init__(self, workspace_path: str = "workspace"):
        # REMOVED: load_dotenv()
        if not GIT_AVAILABLE:
            raise ImportError("GitPython not installed. Run 'pip install GitPython'.")

        self.workspace_root = Path(workspace_path).resolve()
        self.workspace_root.mkdir(exist_ok=True)
        self.active_project_path: Path | None = None
        self.repo: git.Repo | None = None
        self.active_dev_branch: git.Head | None = None
        self.is_existing_project: bool = False

        git_executable_path = os.getenv("GIT_EXECUTABLE_PATH")
        if git_executable_path:
            os.environ['GIT_PYTHON_GIT_EXECUTABLE'] = git_executable_path
            print(f"[ProjectManager] Using Git executable from environment: {git_executable_path}")

    def clear_active_project(self):
        """Resets the active project context."""
        print("[ProjectManager] Clearing active project.")
        self.active_project_path = None
        self.repo = None
        self.active_dev_branch = None
        self.is_existing_project = False

    @property
    def active_project_name(self) -> str:
        return self.active_project_path.name if self.active_project_path else "(none)"

    @property
    def venv_python_path(self) -> Path | None:
        if not self.active_project_path:
            return None
        venv_dir = self.active_project_path / ".venv"
        python_exe = venv_dir / "Scripts" / "python.exe" if sys.platform == "win32" else venv_dir / "bin" / "python"
        return python_exe if python_exe.exists() else None

    @property
    def is_venv_active(self) -> bool:
        """Check if the virtual environment is active and usable."""
        return self.venv_python_path is not None and self.venv_python_path.exists()

    def get_venv_info(self) -> dict:
        """Get information about the virtual environment status."""
        if not self.active_project_path:
            return {"active": False, "reason": "No project"}

        venv_path = self.active_project_path / ".venv"
        if not venv_path.exists():
            return {"active": False, "reason": "No venv"}

        python_path = self.venv_python_path
        if not python_path or not python_path.exists():
            return {"active": False, "reason": "No Python"}

        return {"active": True}

    def _get_base_python_executable(self) -> str:
        candidates = []
        if sys.prefix == sys.base_prefix:
            candidates.append(sys.executable)
        else:
            if sys.platform == "win32":
                candidates.extend([
                    str(Path(sys.base_prefix) / "python.exe"),
                    str(Path(sys.base_prefix) / "Scripts" / "python.exe"),
                ])
            else:
                candidates.extend([
                    str(Path(sys.base_prefix) / "bin" / "python"),
                    str(Path(sys.base_prefix) / "bin" / "python3"),
                ])
        candidates.extend(["python", "python3", sys.executable])
        for candidate in candidates:
            if self._validate_python_executable(candidate):
                print(f"[ProjectManager] Using Python executable: {candidate}")
                return candidate
        raise RuntimeError(f"No valid Python executable found.")

    def _validate_python_executable(self, python_path: str) -> bool:
        try:
            result = subprocess.run([python_path, "--version"], capture_output=True, text=True, timeout=10, check=False)
            if result.returncode != 0:
                return False
            result = subprocess.run([python_path, "-m", "venv", "--help"], capture_output=True, text=True, timeout=10,
                                    check=False)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError):
            return False

    def new_project(self, project_name: str = "New_Project") -> str | None:
        timestamp = datetime.now().strftime("%Ym%d_%H%M%S")
        dir_name = f"{''.join(c for c in project_name if c.isalnum())}_{timestamp}"
        project_path = self.workspace_root / dir_name
        project_path.mkdir()
        try:
            self.active_project_path = project_path
            self.is_existing_project = False
            self.active_dev_branch = None
            self.repo = git.Repo.init(self.active_project_path)
            self._create_gitignore_if_needed()
            self.repo.index.add([".gitignore"])
            self.repo.index.commit("Initial commit by Kintsugi AvA")
            self._create_virtual_environment()
            print(f"[ProjectManager] Successfully created new project at: {self.active_project_path}")
            return str(self.active_project_path)
        except (GitCommandError, subprocess.CalledProcessError, FileNotFoundError, RuntimeError) as e:
            print(f"[ProjectManager] CRITICAL ERROR during new project creation: {e}")
            self.active_project_path = None
            self.repo = None
            shutil.rmtree(project_path, ignore_errors=True)
            return None
        except Exception as e:
            print(f"[ProjectManager] UNEXPECTED ERROR during new project creation: {e}")
            self.active_project_path = None
            self.repo = None
            shutil.rmtree(project_path, ignore_errors=True)
            return None

    def load_project(self, path: str) -> str | None:
        project_path = Path(path).resolve()
        if not project_path.is_dir():
            return None
        self.active_project_path = project_path
        self.is_existing_project = True
        self.active_dev_branch = None
        try:
            self.repo = git.Repo(self.active_project_path)
        except InvalidGitRepositoryError:
            self.repo = git.Repo.init(self.active_project_path)
        except GitCommandError as e:
            print(f"[ProjectManager] Git error on project load: {e}")
            self.repo = None
            return None

        try:
            _ = self.repo.head.commit
        except (ValueError, GitCommandError):
            print("[ProjectManager] Loaded repo has no commits. Creating initial baseline commit.")
            self._create_gitignore_if_needed()
            self.repo.git.add(A=True)
            if self.repo.index.entries:
                self.repo.index.commit("Baseline commit by Kintsugi AvA")
                print("[ProjectManager] Created baseline commit for existing files.")
            else:
                print("[ProjectManager] Repo is empty, no baseline commit needed.")

        return str(self.active_project_path)

    def begin_modification_session(self) -> str | None:
        if not self.repo:
            return None
        dev_branch_name = f"dev_{datetime.now().strftime('%Ym%d_%H%M%S')}"
        try:
            self.active_dev_branch = self.repo.create_head(dev_branch_name)
            self.active_dev_branch.checkout()
            return dev_branch_name
        except GitCommandError as e:
            return f"Error creating branch: {e}"

    def write_and_stage_files(self, files: dict[str, str]):
        if not self.active_project_path or not self.repo:
            print("[ProjectManager] Error: No active project or repository.")
            return

        paths_to_stage = []
        for relative_path_str, content in files.items():
            full_path = self.active_project_path / relative_path_str
            full_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                full_path.write_text(content, encoding='utf-8')
                paths_to_stage.append(str(full_path))  # Add to stage list only if write succeeds
            except Exception as e:
                print(f"[ProjectManager] Error writing file {relative_path_str}: {e}")

        if paths_to_stage:
            try:
                self.repo.index.add(paths_to_stage)
                print(f"[ProjectManager] Staged {len(paths_to_stage)} files.")
            except GitCommandError as e:
                print(f"[ProjectManager] Error staging files: {e}")

    def save_and_commit_files(self, files: dict[str, str], commit_message: str):
        self.write_and_stage_files(files)
        self.commit_staged_files(commit_message)

    def read_file(self, relative_path: str) -> str | None:
        if not self.active_project_path:
            return None
        full_path = self.active_project_path / relative_path
        if not full_path.exists():
            return None
        try:
            return full_path.read_text(encoding='utf-8')
        except Exception:
            return None

    def get_project_files(self) -> dict[str, str]:
        if not self.active_project_path:
            return {}
        project_files = {}
        ignore_dirs = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'dist', 'build', 'rag_db'}
        allowed_extensions = {
            '.py', '.md', '.txt', '.json', '.toml', '.ini', '.cfg', '.yaml', '.yml',
            '.html', '.css', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.hpp',
            '.cs', '.go', '.rb', '.php', '.sh', '.bat', '.ps1', '.dockerfile',
            '.gitignore', '.env',
        }
        try:
            for item in self.active_project_path.rglob('*'):
                if any(part in ignore_dirs for part in item.parts):
                    continue
                if item.is_file():
                    if item.suffix.lower() not in allowed_extensions:
                        continue
                    try:
                        relative_path = item.relative_to(self.active_project_path)
                        project_files[relative_path.as_posix()] = item.read_text(encoding='utf-8', errors='ignore')
                    except (IOError, UnicodeDecodeError) as e:
                        print(f"[ProjectManager] Skipping unreadable file {item}: {e}")
            return project_files
        except Exception as e:
            print(f"[ProjectManager] An unexpected error occurred in get_project_files: {e}")
            return {}

    def get_git_diff(self) -> str:
        if not self.repo:
            return "No Git repository available."
        try:
            if not self.repo.head.is_valid():
                return self.repo.git.diff('--cached')
            return self.repo.git.diff('HEAD')
        except (GitCommandError, ValueError) as e:
            print(f"[ProjectManager] Warning: Could not get git diff (might be a new repo): {e}")
            return "Could not retrieve git diff. Repository might be in an empty state."
        except Exception as e:
            print(f"[ProjectManager] An unexpected error occurred while getting git diff: {e}")
            return "An unexpected error occurred while getting the git diff."

    def _create_gitignore_if_needed(self):
        if not self.repo:
            return
        gitignore_path = Path(self.repo.working_dir) / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("# Kintsugi AvA Default Ignore\n.venv/\n__pycache__/\n*.pyc\nrag_db/\n.env\n")

    def _create_virtual_environment(self):
        if not self.active_project_path:
            return
        venv_path = self.active_project_path / ".venv"
        try:
            base_python = self._get_base_python_executable()
            print(f"[ProjectManager] Creating virtual environment using: {base_python}")
            result = subprocess.run([base_python, "-m", "venv", str(venv_path)], check=True, capture_output=True,
                                    text=True, timeout=120)
            print(f"[ProjectManager] Virtual environment created successfully in {venv_path}.")
            expected_python = self.venv_python_path
            if not expected_python or not expected_python.exists():
                raise RuntimeError(
                    f"Virtual environment creation appeared to succeed, but Python executable not found at expected location: {expected_python}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Virtual environment creation timed out.")
        except subprocess.CalledProcessError as e:
            error_details = f"Command: {e.cmd}\nReturn code: {e.returncode}\nStderr: {e.stderr}"
            raise RuntimeError(f"Virtual environment creation failed: {e.stderr}")
        except Exception as e:
            raise

    def rename_item(self, relative_item_path_str: str, new_name_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository.", None
        old_abs_path = self.active_project_path / relative_item_path_str
        if not old_abs_path.exists():
            return False, f"Error: Item not found: {relative_item_path_str}", None
        if '/' in new_name_str or '\\' in new_name_str:
            return False, "Error: New name cannot contain path separators.", None
        new_abs_path = old_abs_path.parent / new_name_str
        new_relative_path_str = new_abs_path.relative_to(self.active_project_path).as_posix()
        if new_abs_path.exists():
            return False, f"Error: An item named '{new_name_str}' already exists.", None
        try:
            self.repo.git.mv(str(old_abs_path), str(new_abs_path))
            print(f"[ProjectManager] Renamed '{relative_item_path_str}' to '{new_relative_path_str}' and staged.")
            return True, f"Renamed to '{new_name_str}'.", new_relative_path_str
        except GitCommandError as e:
            msg = f"Error renaming item with Git: {e}"
            print(f"[ProjectManager] {msg}")
            try:
                old_abs_path.rename(new_abs_path)
                self.repo.index.add([str(new_abs_path)])
                if old_abs_path.is_dir():  # If renaming a dir, git needs explicit rm for old path contents
                    self.repo.index.remove([relative_item_path_str], r=True, f=True)
                else:
                    self.repo.index.remove([relative_item_path_str])
                print(
                    f"[ProjectManager] Fallback: Manually renamed '{relative_item_path_str}' to '{new_relative_path_str}' and staged.")
                return True, f"Renamed to '{new_name_str}'. (Used fallback)", new_relative_path_str
            except Exception as manual_e:
                msg_manual = f"Fallback rename also failed: {manual_e}"
                print(f"[ProjectManager] {msg_manual}")
                return False, f"Error: {msg}. Fallback: {msg_manual}", None
        except Exception as e:
            msg = f"Unexpected error renaming item: {e}"
            print(f"[ProjectManager] {msg}")
            return False, msg, None

    def delete_items(self, relative_item_paths: List[str]) -> tuple[bool, str]:
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository."
        deleted_paths_git_ops = []
        abs_paths_to_delete_from_fs = []
        errors = []
        for rel_path_str in relative_item_paths:
            abs_path = self.active_project_path / rel_path_str
            if not abs_path.exists():
                errors.append(f"Item not found: {rel_path_str}")
                continue
            abs_paths_to_delete_from_fs.append(abs_path)
            deleted_paths_git_ops.append(rel_path_str)
            print(f"[ProjectManager] Marked for deletion: {rel_path_str}")
        for abs_path in abs_paths_to_delete_from_fs:
            try:
                if abs_path.is_file():
                    abs_path.unlink()
                elif abs_path.is_dir():
                    shutil.rmtree(abs_path)
            except Exception as e:
                rel_path_str_err = abs_path.relative_to(self.active_project_path).as_posix()
                err_msg = f"Error deleting '{rel_path_str_err}' from filesystem: {e}"
                print(f"[ProjectManager] {err_msg}")
                errors.append(err_msg)
                if rel_path_str_err in deleted_paths_git_ops:
                    deleted_paths_git_ops.remove(rel_path_str_err)
        if deleted_paths_git_ops:
            try:
                self.repo.index.remove(deleted_paths_git_ops, r=True)
                print(f"[ProjectManager] Staged deletion of: {', '.join(deleted_paths_git_ops)}")
            except GitCommandError as e:
                err_msg = f"Error staging deletions with Git: {e}"
                print(f"[ProjectManager] {err_msg}")
                errors.append(err_msg)
        if errors:
            return False, "Some items could not be deleted or staged:\n" + "\n".join(errors)
        if not deleted_paths_git_ops and not abs_paths_to_delete_from_fs and not errors:
            return False, "No items were specified for deletion."
        return True, f"Successfully deleted and staged {len(deleted_paths_git_ops)} item(s)."

    def create_file(self, relative_parent_dir_str: str, new_filename_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository.", None
        parent_abs_path = (self.active_project_path / relative_parent_dir_str).resolve()
        if not parent_abs_path.is_dir():
            return False, "Error: Parent path for new file must be a directory.", None
        parent_abs_path.mkdir(parents=True, exist_ok=True)
        if not new_filename_str or '/' in new_filename_str or '\\' in new_filename_str:
            return False, "Error: Invalid file name.", None
        new_file_abs_path = parent_abs_path / new_filename_str
        new_file_rel_path_str = new_file_abs_path.relative_to(self.active_project_path).as_posix()
        if new_file_abs_path.exists():
            return False, f"Error: File '{new_filename_str}' already exists.", None
        try:
            new_file_abs_path.touch()
            self.repo.index.add([str(new_file_abs_path)])
            print(f"[ProjectManager] Created and staged new file: {new_file_rel_path_str}")
            return True, f"File '{new_filename_str}' created.", new_file_rel_path_str
        except GitCommandError as e:
            msg = f"Error staging new file with Git: {e}"
            print(f"[ProjectManager] {msg}")
            return False, msg, None
        except Exception as e:
            msg = f"Unexpected error creating file: {e}"
            print(f"[ProjectManager] {msg}")
            return False, msg, None

    def create_folder(self, relative_parent_dir_str: str, new_folder_name_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.active_project_path:
            return False, "No active project.", None
        parent_abs_path = (self.active_project_path / relative_parent_dir_str).resolve()
        if not parent_abs_path.is_dir():
            return False, "Error: Parent path for new folder must be a directory.", None
        parent_abs_path.mkdir(parents=True, exist_ok=True)
        if not new_folder_name_str or '/' in new_folder_name_str or '\\' in new_folder_name_str:
            return False, "Error: Invalid folder name.", None
        new_folder_abs_path = parent_abs_path / new_folder_name_str
        new_folder_rel_path_str = new_folder_abs_path.relative_to(self.active_project_path).as_posix()
        if new_folder_abs_path.exists():
            return False, f"Error: Folder '{new_folder_name_str}' already exists.", None
        try:
            new_folder_abs_path.mkdir()
            gitkeep_path = new_folder_abs_path / ".gitkeep"
            gitkeep_path.touch()
            if self.repo:
                self.repo.index.add([str(gitkeep_path)])
            print(f"[ProjectManager] Created new folder: {new_folder_rel_path_str} (with .gitkeep)")
            return True, f"Folder '{new_folder_name_str}' created.", new_folder_rel_path_str
        except GitCommandError as e:
            msg = f"Error staging .gitkeep for new folder: {e}"
            print(f"[ProjectManager] {msg}")
            return True, f"Folder '{new_folder_name_str}' created, but .gitkeep staging failed: {msg}", new_folder_rel_path_str
        except Exception as e:
            msg = f"Unexpected error creating folder: {e}"
            print(f"[ProjectManager] {msg}")
            return False, msg, None

    def move_item(self, relative_item_path_str: str, relative_target_dir_str: str,
                  new_name_str: Optional[str] = None) -> tuple[bool, str, Optional[str]]:
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository.", None
        source_abs_path = (self.active_project_path / relative_item_path_str).resolve()
        target_dir_abs_path = (self.active_project_path / relative_target_dir_str).resolve()
        if not source_abs_path.exists():
            return False, f"Error: Source item not found: {relative_item_path_str}", None
        if not target_dir_abs_path.is_dir():
            return False, f"Error: Target path is not a directory: {relative_target_dir_str}", None
        final_name = new_name_str if new_name_str else source_abs_path.name
        if '/' in final_name or '\\' in final_name:
            return False, "Error: New name for move/rename cannot contain path separators.", None
        destination_abs_path = target_dir_abs_path / final_name
        if destination_abs_path.exists():
            return False, f"Error: An item named '{final_name}' already exists in the target directory.", None
        if source_abs_path == destination_abs_path:
            return False, "Error: Source and destination are the same.", None
        if destination_abs_path.is_relative_to(source_abs_path) and source_abs_path.is_dir():
            return False, "Error: Cannot move a directory into itself or one of its subdirectories.", None
        try:
            self.repo.git.mv(str(source_abs_path), str(destination_abs_path))
            new_final_rel_path = destination_abs_path.relative_to(self.active_project_path).as_posix()
            action = "Moved" if new_name_str is None else "Moved and Renamed"
            print(f"[ProjectManager] {action} '{relative_item_path_str}' to '{new_final_rel_path}' and staged.")
            return True, f"{action} to '{new_final_rel_path}'.", new_final_rel_path
        except GitCommandError as e_git:
            print(f"[ProjectManager] git.mv failed: {e_git}. Attempting manual move and stage.")
            try:
                shutil.move(str(source_abs_path), str(destination_abs_path))
                self.repo.index.add([str(destination_abs_path)])
                self.repo.index.remove([relative_item_path_str], r=True)
                new_final_rel_path = destination_abs_path.relative_to(self.active_project_path).as_posix()
                action = "Moved" if new_name_str is None else "Moved and Renamed"
                print(
                    f"[ProjectManager] Fallback: Manually {action.lower()} '{relative_item_path_str}' to '{new_final_rel_path}' and staged.")
                return True, f"{action} to '{new_final_rel_path}' (manual fallback).", new_final_rel_path
            except Exception as e_manual:
                msg = f"Error moving item: Git failed ({e_git}), Manual fallback also failed ({e_manual})"
                print(f"[ProjectManager] {msg}")
                return False, msg, None
        except Exception as e:
            msg = f"Unexpected error moving item: {e}"
            print(f"[ProjectManager] {msg}")
            return False, msg, None

    def copy_external_items(self, source_abs_paths: List[str], target_project_rel_dir: str) -> tuple[
        bool, str, List[Dict[str, str]]]:
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository.", []
        target_dir_abs_path = (self.active_project_path / target_project_rel_dir).resolve()
        if not target_dir_abs_path.is_dir():
            if target_dir_abs_path.exists():
                target_dir_abs_path = target_dir_abs_path.parent
            else:
                target_dir_abs_path.mkdir(parents=True, exist_ok=True)
        if not target_dir_abs_path.is_dir():
            return False, f"Target '{target_project_rel_dir}' is not a valid directory in the project.", []
        copied_item_infos = []
        paths_to_stage = []
        errors = []
        for src_abs_path_str in source_abs_paths:
            src_path = Path(src_abs_path_str)
            if not src_path.exists():
                errors.append(f"Source item not found: {src_abs_path_str}")
                continue
            dest_path = target_dir_abs_path / src_path.name
            if dest_path.exists():
                errors.append(f"Item '{src_path.name}' already exists in target directory. Skipping.")
                continue
            try:
                if src_path.is_file():
                    shutil.copy2(src_path, dest_path)
                elif src_path.is_dir():
                    shutil.copytree(src_path, dest_path)
                new_rel_path = dest_path.relative_to(self.active_project_path).as_posix()
                copied_item_infos.append({'original_abs_path': src_abs_path_str, 'new_project_rel_path': new_rel_path})
                paths_to_stage.append(str(dest_path))
                print(f"[ProjectManager] Copied '{src_abs_path_str}' to '{new_rel_path}'")
            except Exception as e:
                errors.append(f"Error copying '{src_path.name}': {e}")
        if paths_to_stage:
            try:
                self.repo.index.add(paths_to_stage)
                print(f"[ProjectManager] Staged {len(paths_to_stage)} copied items.")
            except GitCommandError as e:
                errors.append(f"Error staging copied items with Git: {e}")
        if errors:
            return False, "Some items could not be copied or staged:\n" + "\n".join(errors), copied_item_infos
        if not copied_item_infos and not errors:
            return False, "No items were specified or could be copied.", []
        return True, f"Successfully copied and staged {len(copied_item_infos)} item(s).", copied_item_infos

    # --- THIS IS THE NEW METHOD ---
    def stage_file(self, relative_path_str: str) -> tuple[bool, str]:
        """Stages a single file in Git."""
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository."

        abs_path = self.active_project_path / relative_path_str
        if not abs_path.is_file():
            return False, f"Error: '{relative_path_str}' is not a valid file to stage."

        try:
            self.repo.index.add([str(abs_path)])
            msg = f"File '{relative_path_str}' staged successfully."
            print(f"[ProjectManager] {msg}")
            return True, msg
        except GitCommandError as e:
            msg = f"Error staging file '{relative_path_str}': {e}"
            print(f"[ProjectManager] {msg}")
            return False, msg
        except Exception as e:
            msg = f"Unexpected error staging file '{relative_path_str}': {e}"
            print(f"[ProjectManager] {msg}")
            return False, msg

    # --- END NEW METHOD ---

    def commit_staged_files(self, commit_message: str) -> str:
        if not self.repo:
            return "Error: No active Git repository."
        # More robust check for "nothing to commit"
        if not self.repo.is_dirty(index=True, working_tree=False, untracked_files=False):
            # This checks if the index is different from HEAD.
            # If you also want to commit newly added (but not yet tracked) files that were staged,
            # the previous check was okay. repo.is_dirty() is more comprehensive for "are there changes".
            return "No changes staged for commit."
        try:
            self.repo.index.commit(commit_message)
            return f"Committed staged changes to branch '{self.repo.active_branch.name}'."
        except GitCommandError as e:
            if "nothing to commit" in str(e).lower() or "no changes added to commit" in str(e).lower():
                return "No changes staged for commit."
            return f"Error committing changes: {e}"