# kintsugi_ava/core/project_manager.py
# V9: Resolves all project paths to be absolute, fixing path comparison errors.

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

try:
    from unidiff import PatchSet

    UNIDIFF_AVAILABLE = True
except ImportError:
    UNIDIFF_AVAILABLE = False


class ProjectManager:
    """
    Manages project lifecycles, including Git versioning, virtual environments,
    and applying surgical patch files using the unidiff library.
    """

    def __init__(self, workspace_path: str = "workspace"):
        if not GIT_AVAILABLE: raise ImportError("GitPython not installed. Run 'pip install GitPython'.")
        if not UNIDIFF_AVAILABLE: raise ImportError("unidiff not installed. Run 'pip install unidiff'.")

        # --- THE FIX (PART 1) ---
        # We resolve the workspace path to get a full, absolute path.
        # This prevents mix-ups between relative and absolute paths later on.
        self.workspace_root = Path(workspace_path).resolve()
        # --- END OF FIX ---

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
        timestamp = datetime.now().strftime("%Ym%d_%H%M%S")
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
        # --- THE FIX (PART 2) ---
        # We also resolve the path here to ensure consistency.
        project_path = Path(path).resolve()
        # --- END OF FIX ---

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
        timestamp = datetime.now().strftime("%Ym%d_%H%M%S")
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

    def patch_file(self, filename: str, patch_content: str, commit_message: str) -> bool:
        """Applies a diff patch to a file using unidiff, then stages and commits it."""
        if not self.repo or not self.active_project_path:
            print("[ProjectManager] Error: No active project to patch.")
            return False

        file_to_patch = self.active_project_path / filename
        if not file_to_patch.exists():
            print(f"[ProjectManager] Error: Cannot patch non-existent file: {filename}")
            return False

        # unidiff needs the original file content to apply the patch correctly.
        original_content = file_to_patch.read_text(encoding='utf-8').splitlines(keepends=True)

        # We must add the diff headers for unidiff to work
        patch_str = f"--- a/{filename}\n+++ b/{filename}\n{patch_content}"

        try:
            patch_set = PatchSet(patch_str)
            if not patch_set:
                print(f"[ProjectManager] Warning: AI returned an empty or invalid patch for {filename}.")
                return False

            print(f"[ProjectManager] Applying patch to {filename}...")
            # Apply the patch in memory
            patched_file = next(patch_set.patch(original=original_content, target=None))

            # Write the patched content back to the file
            with open(file_to_patch, 'w', encoding='utf-8', newline='\n') as f:
                f.writelines(str(line) for line in patched_file)

            # Stage and commit the change
            self.repo.index.add([filename])
            if self.repo.index.diff("HEAD"):
                self.repo.index.commit(commit_message)
                print(f"[ProjectManager] Committed patch for {filename}.")
            else:
                print(f"[ProjectManager] Patch applied but resulted in no net change to {filename}.")
            return True
        except Exception as e:
            print(f"[ProjectManager] Failed to apply or commit patch for {filename}. Error: {e}")
            try:
                self.repo.git.checkout('--', filename)
            except GitCommandError:
                pass
            return False

    def stage_file(self, file_path_str: str) -> str:
        if not self.repo or not self.active_project_path: return "Error: No active Git repository."
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
        if not self.repo: return "Error: No active Git repository."
        if not self.repo.index.diff("HEAD"): return "No changes staged for commit."
        try:
            self.repo.index.commit(commit_message)
            return f"Committed staged changes to branch '{self.repo.active_branch.name}'."
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