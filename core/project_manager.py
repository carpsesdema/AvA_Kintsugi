# kintsugi_ava/core/project_manager.py
# V4: Now manages virtual environments for each project.

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
        """Returns the path to the Python executable in the project's venv, if it exists."""
        if not self.active_project_path:
            return None

        # Standard venv paths for Windows and Unix-like systems
        venv_dir = self.active_project_path / ".venv"
        if sys.platform == "win32":
            python_exe = venv_dir / "Scripts" / "python.exe"
        else:
            python_exe = venv_dir / "bin" / "python"

        return python_exe if python_exe.exists() else None

    def new_project(self, project_name: str = "New_Project") -> str:
        """Creates a new project with a Git repo and a virtual environment."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{''.join(c for c in project_name if c.isalnum())}_{timestamp}"
        project_path = self.workspace_root / dir_name
        project_path.mkdir()

        self.active_project_path = project_path
        self.is_existing_project = False
        self.active_dev_branch = None

        try:
            # 1. Initialize Git
            self.repo = git.Repo.init(self.active_project_path)
            self._create_gitignore_if_needed()
            self.repo.index.add([".gitignore"])
            self.repo.index.commit("Initial commit by Kintsugi AvA")
            print(f"[ProjectManager] Created new Git-tracked project at: {self.active_project_path}")

            # 2. Create Virtual Environment
            self._create_virtual_environment()

        except (GitCommandError, subprocess.CalledProcessError) as e:
            print(f"[ProjectManager] Error during new project creation: {e}")
            self.repo = None

        return str(self.active_project_path)

    def load_project(self, path: str) -> str | None:
        """Loads an existing directory, ensuring it's a Git repo."""
        project_path = Path(path)
        if not project_path.is_dir():
            return None

        self.active_project_path = project_path
        self.is_existing_project = True
        self.active_dev_branch = None

        try:
            self.repo = git.Repo(self.active_project_path)
            print(f"[ProjectManager] Loaded existing Git repository: {self.active_project_path}")
        except InvalidGitRepositoryError:
            print(f"[ProjectManager] Directory not a Git repo. Initializing one.")
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
        """Creates and checks out a new development branch for sandboxed work."""
        if not self.repo or not self.active_project_path: return None
        try:
            main_branch = next((b for b in self.repo.heads if b.name in ['main', 'master']), None)
            if main_branch: main_branch.checkout()
        except GitCommandError as e:
            print(f"[ProjectManager] Warning: Could not switch to main/master branch. Error: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"kintsugi-ava/dev-session-{timestamp}"
        try:
            self.active_dev_branch = self.repo.create_head(branch_name)
            self.active_dev_branch.checkout()
            print(f"[ProjectManager] Created sandbox branch: '{branch_name}'")
            return branch_name
        except GitCommandError as e:
            print(f"[ProjectManager] Could not create sandbox branch. Error: {e}")
            return None

    def save_files_to_project(self, files: dict[str, str], commit_message: str):
        """Saves generated files and commits them to the active branch."""
        if not self.repo or not self.active_project_path: return
        if not self.active_dev_branch:
            print("[ProjectManager] Warning: Saving files outside a sandbox session.")

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
                print(f"[ProjectManager] Committed {len(files)} files to branch '{self.repo.active_branch.name}'")
            else:
                print(f"[ProjectManager] Saved {len(files)} files. No changes to commit.")
        except GitCommandError as e:
            print(f"[ProjectManager] Failed to commit changes. Error: {e}")

    def get_project_files(self) -> dict[str, str]:
        """Reads all text files in the project tracked by Git."""
        if not self.repo or not self.active_project_path: return {}
        project_files = {}
        tracked_files = self.repo.git.ls_files().split('\n')
        for file_str in tracked_files:
            if not file_str: continue
            try:
                file_path = self.active_project_path / file_str
                project_files[file_str] = file_path.read_text(encoding='utf-8')
            except Exception:
                pass
        print(f"[ProjectManager] Found {len(project_files)} git-tracked files.")
        return project_files

    def _create_gitignore_if_needed(self):
        """Creates a sensible .gitignore file if one doesn't exist."""
        if not self.repo: return
        gitignore_path = Path(self.repo.working_dir) / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text(
                "# Kintsugi AvA Default Ignore\n.venv/\nvenv/\n__pycache__/\n*.pyc\nrag_db/\n.env\n"
            )
            print("[ProjectManager] Created default .gitignore file.")

    def _create_virtual_environment(self):
        """Creates a .venv folder in the active project."""
        if not self.active_project_path:
            print("[ProjectManager] Cannot create venv: No active project.")
            return

        venv_path = self.active_project_path / ".venv"
        print(f"[ProjectManager] Creating virtual environment in {venv_path}...")
        try:
            # Use the same python that is running this app to create the venv
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True, capture_output=True)
            print("[ProjectManager] Virtual environment created successfully.")
        except subprocess.CalledProcessError as e:
            print(f"[ProjectManager] Failed to create virtual environment. Stderr: {e.stderr.decode()}")
        except Exception as e:
            print(f"[ProjectManager] An unexpected error occurred creating venv: {e}")