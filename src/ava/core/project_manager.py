import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

try:
    import git
    from git.exc import InvalidGitRepositoryError, GitCommandError

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class ProjectManager:
    """
    Manages project lifecycles, including Git versioning and virtual environments.
    Simplified with patch system removed - only handles full file operations.
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

    def rename_file(self, old_relative_path: str, new_relative_path: str) -> bool:
        """Renames a file or directory both on the filesystem and in the Git index."""
        if not self.repo or not self.active_project_path:
            print("[ProjectManager] Error: No active project or repository.")
            return False

        old_abs_path = self.active_project_path / old_relative_path
        new_abs_path = self.active_project_path / new_relative_path

        if not old_abs_path.exists():
            print(f"[ProjectManager] Error: Source path to rename does not exist: {old_abs_path}")
            return False

        if new_abs_path.exists():
            print(f"[ProjectManager] Error: Destination path already exists: {new_abs_path}")
            return False

        new_abs_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.repo.git.mv(str(old_abs_path), str(new_abs_path))
            commit_message = f"refactor: rename {old_relative_path} to {new_relative_path}"
            self.repo.index.commit(commit_message)
            print(f"[ProjectManager] Renamed and committed: '{old_relative_path}' -> '{new_relative_path}'")
            return True
        except GitCommandError as e:
            print(f"[ProjectManager] Git error during rename: {e}")
            return False
        except Exception as e:
            print(f"[ProjectManager] Unexpected error during rename: {e}")
            return False

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

    def delete_path(self, relative_path_to_delete: str) -> bool:
        """Deletes a file or directory and handles both tracked and untracked files."""
        if not self.repo or not self.active_project_path:
            print("[ProjectManager] Error: No active project or repository.")
            return False

        abs_path = self.active_project_path / relative_path_to_delete
        if not abs_path.exists():
            print(f"[ProjectManager] Error: Path to delete does not exist: {abs_path}")
            return False

        try:
            # Check if the file is tracked by Git.
            is_tracked = False
            try:
                # This command returns the path if tracked, or empty if not.
                if self.repo.git.ls_files(str(abs_path)):
                    is_tracked = True
            except GitCommandError:
                # A GitCommandError can occur if the path is not in the repo,
                # which we can treat as not tracked.
                is_tracked = False

            # Delete the path.
            if is_tracked:
                # Use git rm for tracked files/dirs.
                if abs_path.is_dir():
                    self.repo.git.rm('-r', str(abs_path))
                else:
                    self.repo.git.rm(str(abs_path))
            else:
                # Use standard filesystem calls for untracked files/dirs.
                if abs_path.is_dir():
                    shutil.rmtree(abs_path)
                else:
                    abs_path.unlink()

            # Commit the change if it was a tracked file.
            if is_tracked:
                commit_message = f"refactor: delete {relative_path_to_delete}"
                self.repo.index.commit(commit_message)

            print(f"[ProjectManager] Deleted path: '{relative_path_to_delete}' (Was Tracked: {is_tracked})")
            return True

        except (GitCommandError, OSError) as e:
            print(f"[ProjectManager] Error during deletion: {e}")
            return False

    def stage_file(self, relative_path: str) -> str:
        if not self.repo:
            return "Error: No active Git repository."
        full_path = self.active_project_path / relative_path
        if not full_path.exists():
            return f"Error: File not found: {relative_path}"
        try:
            self.repo.index.add([str(relative_path)])
            return f"Staged '{relative_path}' for commit."
        except GitCommandError as e:
            return f"Error staging file: {e}"

    def commit_staged_files(self, commit_message: str) -> str:
        if not self.repo:
            return "Error: No active Git repository."
        if not self.repo.index.diff("HEAD"):
            return "No changes staged for commit."
        try:
            self.repo.index.commit(commit_message)
            return f"Committed staged changes to branch '{self.repo.active_branch.name}'."
        except GitCommandError as e:
            return f"Error committing changes: {e}"

    def get_project_files(self) -> dict[str, str]:
        """
        Gets all project files by walking the directory, ignoring common
        temporary/binary directories. This ensures the most up-to-date
        file state is used for context.
        """
        if not self.active_project_path:
            return {}

        project_files = {}
        ignore_dirs = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'dist', 'build', 'rag_db'}

        try:
            for item in self.active_project_path.rglob('*'):
                # Check if any part of the path is an ignored directory
                if any(part in ignore_dirs for part in item.parts):
                    continue

                if item.is_file():
                    try:
                        relative_path = item.relative_to(self.active_project_path)
                        project_files[relative_path.as_posix()] = item.read_text(encoding='utf-8', errors='ignore')
                    except (IOError, UnicodeDecodeError) as e:
                        print(f"[ProjectManager] Skipping file {item}: {e}")

            print(f"[ProjectManager] Retrieved {len(project_files)} files by walking the project directory.")
            return project_files

        except Exception as e:
            print(f"[ProjectManager] An unexpected error occurred in get_project_files: {e}")
            return {}

    def get_git_diff(self) -> str:
        """
        Gets the git diff of staged and unstaged changes against the last commit.

        Returns:
            A string containing the git diff, or an explanatory string on error.
        """
        if not self.repo:
            return "No Git repository available."
        try:
            # Check if there is a HEAD commit to diff against.
            if not self.repo.head.is_valid():
                # If no HEAD, it's a new repo. Diff the index (staged files).
                # This will show the initial set of files.
                return self.repo.git.diff('--cached')

            # Diff working tree (staged & unstaged) against the last commit.
            return self.repo.git.diff('HEAD')

        except (GitCommandError, ValueError) as e:
            # A ValueError can be raised if `is_valid()` check itself has issues in edge cases.
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