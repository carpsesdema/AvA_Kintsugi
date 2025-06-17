# kintsugi_ava/core/project_manager.py
# UPDATED: Added a clear_active_project method for session resets.

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
            result = subprocess.run([python_path, "-m", "venv", "--help"], capture_output=True, text=True, timeout=10, check=False)
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
            self._create_gitignore_if_needed()
            self.repo.index.add(all=True)
            if self.repo.index.diff(None):
                self.repo.index.commit("Baseline commit by Kintsugi AvA")
        except GitCommandError as e:
            print(f"[ProjectManager] Git error on project load: {e}")
            self.repo = None
            return None
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

    def delete_file(self, relative_path: str) -> str:
        if not self.active_project_path or not self.repo:
            return "Error: No active project."
        full_path = self.active_project_path / relative_path
        if not full_path.exists():
            return f"Error: File not found: {relative_path}"
        try:
            full_path.unlink()
            self.repo.index.remove([str(relative_path)])
            return f"Deleted and staged removal: {relative_path}"
        except GitCommandError as e:
            return f"Error removing file from Git: {e}"
        except Exception as e:
            return f"Error deleting file: {e}"

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
        if not self.active_project_path or not self.repo:
            return {}
        project_files = {}
        try:
            for py_file in self.active_project_path.rglob("*.py"):
                if any(part in ['.venv', 'venv'] for part in py_file.parts):
                    continue
                relative_path = py_file.relative_to(self.active_project_path)
                try:
                    project_files[relative_path.as_posix()] = py_file.read_text(encoding='utf-8')
                except Exception as e:
                    print(f"[ProjectManager] Error reading Python file {relative_path}: {e}")
            tracked_files = self.repo.git.ls_files().split('\n')
            for file_str in tracked_files:
                if not file_str or file_str in project_files:
                    continue
                try:
                    file_path = self.active_project_path / file_str
                    if not file_str.endswith('.py') and file_path.exists() and file_path.is_file():
                        project_files[file_str] = file_path.read_text(encoding='utf-8')
                except Exception as e:
                    print(f"[ProjectManager] Error reading tracked file {file_str}: {e}")
            print(f"[ProjectManager] Retrieved {len(project_files)} project files for context.")
            return project_files
        except Exception as e:
            print(f"[ProjectManager] An unexpected error occurred in get_project_files: {e}")
            return {}

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
            result = subprocess.run([base_python, "-m", "venv", str(venv_path)], check=True, capture_output=True, text=True, timeout=120)
            print(f"[ProjectManager] Virtual environment created successfully in {venv_path}.")
            expected_python = self.venv_python_path
            if not expected_python or not expected_python.exists():
                raise RuntimeError(f"Virtual environment creation appeared to succeed, but Python executable not found at expected location: {expected_python}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Virtual environment creation timed out.")
        except subprocess.CalledProcessError as e:
            error_details = f"Command: {e.cmd}\nReturn code: {e.returncode}\nStderr: {e.stderr}"
            raise RuntimeError(f"Virtual environment creation failed: {e.stderr}")
        except Exception as e:
            raise