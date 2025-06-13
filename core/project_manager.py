# kintsugi_ava/core/project_manager.py
# V3: Git-powered sandboxing for safe project modifications.

import os
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
    Manages project lifecycles using Git for versioning and sandboxing.
    Ensures that modifications to existing projects are done in isolated
    development branches, protecting the user's main work.
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

    def new_project(self, project_name: str = "New_Project") -> str:
        """Creates a new project directory, initializes a Git repository, and sets it as active."""
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
            print(f"[ProjectManager] Created new Git-tracked project at: {self.active_project_path}")
        except GitCommandError as e:
            print(f"[ProjectManager] Git error during new project creation: {e}")
            self.repo = None

        return str(self.active_project_path)

    def load_project(self, path: str) -> str | None:
        """Loads an existing directory as the active project, ensuring it's a Git repository."""
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
            print(f"[ProjectManager] Directory is not a Git repository. Initializing one now.")
            self.repo = git.Repo.init(self.active_project_path)
            self._create_gitignore_if_needed()
            self.repo.index.add(all=True)
            if self.repo.index.diff(None):  # Only commit if there are changes
                self.repo.index.commit("Baseline commit by Kintsugi AvA")
        except GitCommandError as e:
            print(f"[ProjectManager] Git error during project load: {e}")
            self.repo = None
            return None

        return str(self.active_project_path)

    def begin_modification_session(self) -> str | None:
        """
        Creates and checks out a new, timestamped development branch for sandboxed modifications.
        This is the primary safety mechanism.
        """
        if not self.repo or not self.active_project_path:
            print("[ProjectManager] Error: No active project to begin modification session on.")
            return None

        # Return to the main branch to ensure a clean start
        try:
            # Find a common main branch name and check it out
            main_branch = next((b for b in self.repo.heads if b.name in ['main', 'master']), None)
            if main_branch:
                main_branch.checkout()
        except GitCommandError as e:
            print(f"[ProjectManager] Could not switch to main/master branch. Sticking to current. Error: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"kintsugi-ava/dev-session-{timestamp}"

        try:
            self.active_dev_branch = self.repo.create_head(branch_name)
            self.active_dev_branch.checkout()
            print(f"[ProjectManager] Created and checked out sandbox branch: '{branch_name}'")
            return branch_name
        except GitCommandError as e:
            print(f"[ProjectManager] Could not create sandbox branch. Error: {e}")
            return None

    def save_files_to_project(self, files: dict[str, str], commit_message: str):
        """Saves generated files and commits them to the active (development) branch."""
        if not self.repo or not self.active_project_path:
            print("[ProjectManager] Error: Cannot save files, no repository is active.")
            return

        if not self.active_dev_branch:
            print("[ProjectManager] Warning: Saving files outside of a sandboxed session. This is not recommended.")

        file_paths_to_add = []
        for filename, content in files.items():
            file_path = self.active_project_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            file_paths_to_add.append(str(file_path.relative_to(self.repo.working_dir)))

        try:
            self.repo.index.add(file_paths_to_add)
            if self.repo.index.diff("HEAD"):  # Only commit if there are staged changes
                self.repo.index.commit(commit_message)
                print(f"[ProjectManager] Committed {len(files)} files to branch '{self.repo.active_branch.name}'")
            else:
                print(f"[ProjectManager] Saved {len(files)} files. No new changes to commit.")

        except GitCommandError as e:
            print(f"[ProjectManager] Failed to commit changes. Error: {e}")

    def get_project_files(self) -> dict[str, str]:
        """Reads all text files in the active project directory that are tracked by Git."""
        if not self.repo or not self.active_project_path:
            return {}

        project_files = {}
        # List files tracked by git, this is more reliable than walking the dir
        tracked_files = self.repo.git.ls_files().split('\n')

        for file_str in tracked_files:
            if not file_str: continue
            try:
                file_path = self.active_project_path / file_str
                project_files[file_str] = file_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"[ProjectManager] Warning: Could not read git-tracked file {file_path}. Error: {e}")
                pass

        print(f"[ProjectManager] Found {len(project_files)} git-tracked files.")
        return project_files

    def _create_gitignore_if_needed(self):
        """Creates a sensible .gitignore file if one doesn't exist."""
        if not self.repo: return
        gitignore_path = Path(self.repo.working_dir) / ".gitignore"
        if not gitignore_path.exists():
            gitignore_content = (
                "# Kintsugi AvA Default Ignore\n"
                ".venv/\n"
                "venv/\n"
                "__pycache__/\n"
                ".idea/\n"
                ".vscode/\n"
                "*.pyc\n"
                "rag_db/\n"
                ".env\n"
            )
            gitignore_path.write_text(gitignore_content)
            print("[ProjectManager] Created default .gitignore file.")