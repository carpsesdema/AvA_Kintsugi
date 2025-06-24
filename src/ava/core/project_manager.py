import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Optional  # Added List and Optional

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
        load_dotenv()
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
        for relative_path, content in files.items():
            full_path = self.active_project_path / relative_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                full_path.write_text(content, encoding='utf-8')
            except Exception as e:
                print(f"[ProjectManager] Error writing file {relative_path}: {e}")
        paths_to_stage = [str(self.active_project_path / p) for p in files.keys()]
        if paths_to_stage:
            try:
                self.repo.index.add(paths_to_stage)
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
                        print(f"[ProjectManager] Skipping non-text/non-code file: {item.name}")
                        continue
                    try:
                        relative_path = item.relative_to(self.active_project_path)
                        project_files[relative_path.as_posix()] = item.read_text(encoding='utf-8', errors='ignore')
                    except (IOError, UnicodeDecodeError) as e:
                        print(f"[ProjectManager] Skipping unreadable file {item}: {e}")
            print(f"[ProjectManager] Retrieved {len(project_files)} relevant project files.")
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

    # --- NEW FILE OPERATION METHODS ---

    def rename_item(self, relative_item_path_str: str, new_name_str: str) -> tuple[bool, str, Optional[str]]:
        """
        Renames a file or directory within the active project and stages the change in Git.
        Returns (success_status, message, new_relative_path_str).
        """
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository.", None

        old_abs_path = self.active_project_path / relative_item_path_str
        if not old_abs_path.exists():
            return False, f"Error: Item not found: {relative_item_path_str}", None

        # Basic validation for new name (e.g., no slashes)
        if '/' in new_name_str or '\\' in new_name_str:
            return False, "Error: New name cannot contain path separators.", None

        new_abs_path = old_abs_path.parent / new_name_str
        new_relative_path_str = new_abs_path.relative_to(self.active_project_path).as_posix()

        if new_abs_path.exists():
            return False, f"Error: An item named '{new_name_str}' already exists.", None

        try:
            # Use git mv for renaming, as it handles staging correctly
            self.repo.git.mv(str(old_abs_path), str(new_abs_path))
            print(f"[ProjectManager] Renamed '{relative_item_path_str}' to '{new_relative_path_str}' and staged.")
            return True, f"Renamed to '{new_name_str}'.", new_relative_path_str
        except GitCommandError as e:
            msg = f"Error renaming item with Git: {e}"
            print(f"[ProjectManager] {msg}")
            # Attempt a fallback manual rename + stage if git mv fails (e.g., on case-insensitive filesystems sometimes)
            try:
                old_abs_path.rename(new_abs_path)
                self.repo.index.add([str(new_abs_path)])
                self.repo.index.remove([str(old_abs_path)], working_tree=False)  # Remove old path from index
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
        """
        Deletes files or directories within the active project and stages the changes in Git.
        """
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository."

        deleted_paths_git = []
        errors = []

        for rel_path_str in relative_item_paths:
            abs_path = self.active_project_path / rel_path_str
            if not abs_path.exists():
                errors.append(f"Item not found: {rel_path_str}")
                continue

            try:
                if abs_path.is_file():
                    abs_path.unlink()
                elif abs_path.is_dir():
                    shutil.rmtree(abs_path)
                deleted_paths_git.append(str(abs_path))  # Use absolute path for git rm
                print(f"[ProjectManager] Deleted item: {rel_path_str}")
            except Exception as e:
                err_msg = f"Error deleting '{rel_path_str}': {e}"
                print(f"[ProjectManager] {err_msg}")
                errors.append(err_msg)

        if deleted_paths_git:
            try:
                # Stage the removals. Git handles whether it's a file or directory.
                # The files/dirs are already deleted from the working tree.
                self.repo.index.remove(deleted_paths_git, r=True, f=True, working_tree=True)
                print(f"[ProjectManager] Staged deletion of: {', '.join(relative_item_paths)}")
            except GitCommandError as e:
                err_msg = f"Error staging deletions with Git: {e}"
                print(f"[ProjectManager] {err_msg}")
                errors.append(err_msg)

        if errors:
            return False, "Some items could not be deleted:\n" + "\n".join(errors)
        if not deleted_paths_git and not errors:
            return False, "No items were specified for deletion."
        return True, f"Successfully deleted and staged {len(deleted_paths_git)} item(s)."

    def create_file(self, relative_parent_dir_str: str, new_filename_str: str) -> tuple[bool, str, Optional[str]]:
        """
        Creates a new empty file in the specified directory and stages it in Git.
        Returns (success_status, message, new_relative_file_path_str).
        """
        if not self.active_project_path or not self.repo:
            return False, "No active project or repository.", None

        parent_abs_path = self.active_project_path / relative_parent_dir_str
        if not parent_abs_path.is_dir():  # Ensure parent is a directory
            parent_abs_path = parent_abs_path.parent  # If a file was selected, use its parent

        if not parent_abs_path.exists():  # Create parent if it doesn't exist
            parent_abs_path.mkdir(parents=True, exist_ok=True)
            print(f"[ProjectManager] Created directory: {parent_abs_path}")
            # Need to stage the parent directory if it's new and we want to commit it (e.g., via .gitkeep)
            # For now, just creating it is fine. Git will track it once a file is added.

        # Basic validation for new file name
        if not new_filename_str or '/' in new_filename_str or '\\' in new_filename_str:
            return False, "Error: Invalid file name.", None

        new_file_abs_path = parent_abs_path / new_filename_str
        new_file_rel_path_str = new_file_abs_path.relative_to(self.active_project_path).as_posix()

        if new_file_abs_path.exists():
            return False, f"Error: File '{new_filename_str}' already exists.", None

        try:
            new_file_abs_path.touch()  # Create empty file
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
        """
        Creates a new empty folder in the specified directory.
        Git doesn't track empty folders, but we create it. A .gitkeep file could be added to track it.
        Returns (success_status, message, new_relative_folder_path_str).
        """
        if not self.active_project_path:  # No repo check needed as Git doesn't track empty folders.
            return False, "No active project.", None

        parent_abs_path = self.active_project_path / relative_parent_dir_str
        if not parent_abs_path.is_dir():  # Ensure parent is a directory
            parent_abs_path = parent_abs_path.parent  # If a file was selected, use its parent

        if not parent_abs_path.exists():
            parent_abs_path.mkdir(parents=True, exist_ok=True)
            print(f"[ProjectManager] Created directory: {parent_abs_path}")

        # Basic validation for new folder name
        if not new_folder_name_str or '/' in new_folder_name_str or '\\' in new_folder_name_str:
            return False, "Error: Invalid folder name.", None

        new_folder_abs_path = parent_abs_path / new_folder_name_str
        new_folder_rel_path_str = new_folder_abs_path.relative_to(self.active_project_path).as_posix()

        if new_folder_abs_path.exists():
            return False, f"Error: Folder '{new_folder_name_str}' already exists.", None

        try:
            new_folder_abs_path.mkdir()
            # Optionally, add a .gitkeep file to make Git track it.
            # (new_folder_abs_path / ".gitkeep").touch()
            # self.repo.index.add([str(new_folder_abs_path / ".gitkeep")])
            print(f"[ProjectManager] Created new folder: {new_folder_rel_path_str}")
            return True, f"Folder '{new_folder_name_str}' created.", new_folder_rel_path_str
        except Exception as e:
            msg = f"Unexpected error creating folder: {e}"
            print(f"[ProjectManager] {msg}")
            return False, msg, None

    # --- END NEW METHODS ---

    def commit_staged_files(self, commit_message: str) -> str:
        if not self.repo:
            return "Error: No active Git repository."
        if not self.repo.index.diff("HEAD") and not self.repo.untracked_files:
            # Check if there are staged changes OR untracked files that might have been added
            if not any(True for _ in self.repo.index.diff(None)):  # diff against working tree for newly added
                return "No changes staged for commit."
        try:
            self.repo.index.commit(commit_message)
            return f"Committed staged changes to branch '{self.repo.active_branch.name}'."
        except GitCommandError as e:
            # This can happen if there are absolutely no changes, even after adding.
            if "nothing to commit" in str(e).lower():
                return "No changes staged for commit."
            return f"Error committing changes: {e}"