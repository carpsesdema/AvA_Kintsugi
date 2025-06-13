# kintsugi_ava/core/project_manager.py
# V5: Enhanced with granular Git commands for staging and selective commits.

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import git
    from git.exc import InvalidGitRepositoryError, GitCommandError

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class ProjectManager:
    """
    Manages project lifecycles, including Git versioning, virtual environments,
    and sandboxed modification branches.
    """

    def __init__(self, workspace_path: str = "workspace"):
        if not GIT_AVAILABLE:
            raise ImportError("GitPython is not installed. Please run 'pip install GitPython'.")

        self.workspace_root = Path(workspace_path)
        self.workspace_root.mkdir(exist_ok=True)
        self.active_project_path: Path | None = None
        self.repo: git.Repo | None = None
        self.active_dev_branch: git.Head | None = None
        self.is_existing_project: bool = False

    @property
    def active_project_name(self) -> str:
        return self.active_project_path.name if self.active_project_path else "(none)"

    @property
    def venv_python_path(self) -> Path | None:
        if not self.active_project_path: return None
        venv_dir = self.active_project_path / ".venv"
        python_exe = venv_dir / "Scripts" / "python.exe" if sys.platform == "win32" else venv_dir / "bin" / "python"
        return python_exe if python_exe.exists() else None

    def new_project(self, project_name: str = "New_Project") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{''.join(c for c in project_name if c.isalnum())}_{timestamp}"
        project_path = self.workspace_root / dir_name
        project_path.mkdir()
        self.active_project_path = project_path
        self.is_existing_project = False
        self.active_dev_branch = None
        try:
            self.repo = git.Repo.init(self.active_project_path)
            self._create_gitignore_if_needed()
            self.repo.index.add([".gitignore"])
            self.repo.index.commit("Initial commit by Kintsugi AvA")
            self._create_virtual_environment()
        except (GitCommandError, subprocess.CalledProcessError) as e:
            print(f"[ProjectManager] Error during new project creation: {e}")
            self.repo = None
        return str(self.active_project_path)

    def load_project(self, path: str) -> str | None:
        project_path = Path(path)
        if not project_path.is_dir(): return None
        self.active_project_path = project_path
        self.is_existing_project = True
        self.active_dev_branch = None
        try:
            self.repo = git.Repo(self.active_project_path)
        except InvalidGitRepositoryError:
            self.repo = git.Repo.init(self.active_project_path)
            self._create_gitignore_if_needed()
            self.repo.index.add(all=True)
            if self.repo.index.diff(None): self.repo.index.commit("Baseline commit by Kintsugi AvA")
        except GitCommandError as e:
            print(f"[ProjectManager] Git error on project load: {e}")
            self.repo = None
            return None
        return str(self.active_project_path)

    def begin_modification_session(self) -> str | None:
        if not self.repo: return None
        try:
            main_branch = next((b for b in self.repo.heads if b.name in ['main', 'master']), None)
            if main_branch: main_branch.checkout()
        except GitCommandError as e:
            print(f"[ProjectManager] Warning: Could not switch to main/master. Error: {e}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"kintsugi-ava/dev-session-{timestamp}"
        try:
            self.active_dev_branch = self.repo.create_head(branch_name)
            self.active_dev_branch.checkout()
            return branch_name
        except GitCommandError as e:
            print(f"[ProjectManager] Could not create sandbox branch. Error: {e}")
            return None

    def save_and_commit_files(self, files: dict[str, str], commit_message: str):
        if not self.repo or not self.active_project_path: return
        file_paths_to_add = []
        for filename, content in files.items():
            file_path = self.active_project_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            file_paths_to_add.append(str(file_path.relative_to(self.repo.working_dir)))
        try:
            self.repo.index.add(file_paths_to_add)
            if self.repo.index.diff("HEAD"):
                self.repo.index.commit(commit_message)
            else:
                print(f"[ProjectManager] Saved {len(files)} files. No changes to commit.")
        except GitCommandError as e:
            print(f"[ProjectManager] Failed to commit changes. Error: {e}")

    def stage_file(self, file_path_str: str) -> str:
        """Stages a single file for the next commit."""
        if not self.repo or not self.active_project_path: return "Error: No active Git repository."

        # Ensure the file path is relative to the repo root
        try:
            relative_path = Path(file_path_str).relative_to(self.active_project_path)
            full_path = self.active_project_path / relative_path
        except ValueError:
            return f"Error: File '{file_path_str}' is not within the project directory."

        if not full_path.exists(): return f"Error: File not found: {relative_path}"

        try:
            self.repo.index.add([str(relative_path)])
            return f"Staged '{relative_path}' for commit."
        except GitCommandError as e:
            return f"Error staging file: {e}"

    def commit_staged_files(self, commit_message: str) -> str:
        """Commits all currently staged files."""
        if not self.repo: return "Error: No active Git repository."
        if not self.repo.index.diff("HEAD"): return "No changes staged for commit."

        try:
            self.repo.index.commit(commit_message)
            branch = self.repo.active_branch.name
            return f"Committed staged changes to branch '{branch}'."
        except GitCommandError as e:
            return f"Error committing changes: {e}"

    def get_project_files(self) -> dict[str, str]:
        if not self.repo: return {}
        project_files = {}
        tracked_files = self.repo.git.ls_files().split('\n')
        for file_str in tracked_files:
            if not file_str: continue
            try:
                file_path = self.active_project_path / file_str
                project_files[file_str] = file_path.read_text(encoding='utf-8')
            except Exception:
                pass
        return project_files

    def _create_gitignore_if_needed(self):
        if not self.repo: return
        gitignore_path = Path(self.repo.working_dir) / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("# Kintsugi AvA Default Ignore\n.venv/\n__pycache__/\n*.pyc\nrag_db/\n.env\n")

    def _create_virtual_environment(self):
        if not self.active_project_path: return
        venv_path = self.active_project_path / ".venv"
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True, capture_output=True)
            print(f"[ProjectManager] Virtual environment created in {venv_path}.")
        except (subprocess.CalledProcessError, Exception) as e:
            print(f"[ProjectManager] Failed to create virtual environment: {e}")