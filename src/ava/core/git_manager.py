# src/ava/core/git_manager.py

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple, Dict

try:
    import git
    from git.exc import InvalidGitRepositoryError, GitCommandError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class GitManager:
    """
    Manages all Git-related operations for a single project.
    This class encapsulates all direct interactions with the GitPython library.
    """
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.repo: Optional[git.Repo] = None

        if not GIT_AVAILABLE:
            print("[GitManager] WARNING: GitPython not installed. Git features will be disabled.")
            return

        git_executable_path = os.getenv("GIT_EXECUTABLE_PATH")
        if git_executable_path:
            os.environ['GIT_PYTHON_GIT_EXECUTABLE'] = git_executable_path

        self._load_or_init_repo()

    def _load_or_init_repo(self):
        """Loads an existing repository or initializes a new one."""
        if not self.project_path.is_dir():
            print(f"[GitManager] Error: Project path does not exist: {self.project_path}")
            return
        try:
            self.repo = git.Repo(self.project_path)
            print(f"[GitManager] Loaded existing Git repository at {self.project_path}")
        except InvalidGitRepositoryError:
            print(f"[GitManager] No repo found at {self.project_path}. Initializing new one.")
            self.repo = git.Repo.init(self.project_path)
        except GitCommandError as e:
            print(f"[GitManager] Git error on repo load/init: {e}")
            self.repo = None

    def get_active_branch_name(self) -> str:
        """Returns the name of the current active branch."""
        if self.repo and self.repo.head.is_valid():
            try:
                return self.repo.active_branch.name
            except TypeError:
                return self.repo.head.commit.hexsha[:7]
        return "(no branch)"

    def init_repo_for_new_project(self):
        """Initializes the repository with a first commit."""
        if not self.repo: return
        self._create_gitignore_if_needed()
        if (self.project_path / ".gitignore").exists():
            self.repo.index.add([".gitignore"])
        self.repo.index.commit("Initial commit by Kintsugi AvA")
        print("[GitManager] Git repository initialized for new project.")

    def ensure_initial_commit(self):
        """Ensures that an existing repository has at least one commit."""
        if not self.repo: return
        try:
            _ = self.repo.head.commit
        except (ValueError, GitCommandError):
            print("[GitManager] Loaded repo has no commits. Creating baseline commit.")
            self._create_gitignore_if_needed()
            self.repo.git.add(A=True)
            if self.repo.index.entries:
                self.repo.index.commit("Baseline commit for existing files by Kintsugi AvA")
                print("[GitManager] Created baseline commit for existing files.")

    def begin_modification_session(self) -> str:
        """
        Ensures the repository is ready for a modification session on the current branch.
        This no longer creates a new branch.
        """
        if not self.repo:
            return "Error: No Git repository."
        current_branch_name = self.get_active_branch_name()
        print(f"[GitManager] Beginning modification session on existing branch: {current_branch_name}")
        return current_branch_name

    def write_and_stage_files(self, files: dict[str, str]):
        """Writes files to disk and stages them in Git."""
        paths_to_stage = []
        for relative_path_str, content in files.items():
            full_path = self.project_path / relative_path_str
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding='utf-8')
                paths_to_stage.append(str(full_path))
            except Exception as e:
                print(f"[GitManager] Error writing file {relative_path_str}: {e}")

        if self.repo and paths_to_stage:
            self.stage_files(paths_to_stage)

    def stage_files(self, file_paths: List[str]):
        """Stages a list of files in Git."""
        if not self.repo: return
        try:
            self.repo.index.add(file_paths)
            print(f"[GitManager] Staged {len(file_paths)} files.")
        except GitCommandError as e:
            print(f"[GitManager] Error staging files: {e}")

    def stage_file(self, relative_path_str: str) -> tuple[bool, str]:
        """Stages a single file in Git."""
        if not self.repo: return False, "No active repository."
        abs_path = self.project_path / relative_path_str
        if not abs_path.is_file():
            return False, f"Error: '{relative_path_str}' is not a valid file."
        try:
            self.repo.index.add([str(abs_path)])
            return True, f"File '{relative_path_str}' staged."
        except Exception as e:
            return False, f"Error staging file '{relative_path_str}': {e}"

    def commit_staged_files(self, commit_message: str) -> str:
        """Commits currently staged files."""
        if not self.repo: return "Error: No active Git repository."
        if not self.repo.is_dirty(index=True, working_tree=False, untracked_files=False):
            return "No changes staged for commit."
        try:
            active_branch_name = self.get_active_branch_name()
            self.repo.index.commit(commit_message)
            msg = f"Committed staged changes to branch '{active_branch_name}'."
            return msg
        except GitCommandError as e:
            if "nothing to commit" in str(e).lower() or "no changes added to commit" in str(e).lower():
                return "No changes staged for commit."
            return f"Error committing changes: {e}"

    def get_diff(self) -> str:
        """Gets the git diff for staged changes."""
        if not self.repo: return "No Git repository available."
        try:
            return self.repo.git.diff('--staged')
        except (GitCommandError, ValueError):
            try:
                return self.repo.git.diff('--cached')
            except (GitCommandError, ValueError):
                return "Could not retrieve git diff. Repository might be in an empty state."

    def rename_item(self, relative_item_path_str: str, new_name_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.repo: return False, "No active repository.", None
        old_abs_path = self.project_path / relative_item_path_str
        new_abs_path = old_abs_path.parent / new_name_str
        new_relative_path_str = new_abs_path.relative_to(self.project_path).as_posix()
        try:
            self.repo.git.mv(str(old_abs_path), str(new_abs_path))
            return True, f"Renamed to '{new_name_str}'.", new_relative_path_str
        except Exception as e:
            return False, f"Error renaming with Git: {e}", None

    def delete_items(self, relative_item_paths: List[str]) -> tuple[bool, str]:
        if not self.repo: return False, "No active repository."
        errors = []
        for rel_path_str in relative_item_paths:
            abs_path = self.project_path / rel_path_str
            try:
                if abs_path.is_file(): abs_path.unlink()
                elif abs_path.is_dir(): shutil.rmtree(abs_path)
            except Exception as e:
                errors.append(f"Error deleting '{rel_path_str}': {e}")
        if relative_item_paths:
            try:
                self.repo.index.remove(relative_item_paths, r=True)
            except GitCommandError as e:
                errors.append(f"Error staging deletions: {e}")
        if errors:
            return False, "\n".join(errors)
        return True, f"Successfully deleted {len(relative_item_paths)} item(s)."

    def create_file(self, relative_parent_dir_str: str, new_filename_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.repo: return False, "No active repository.", None
        parent_abs_path = self.project_path / relative_parent_dir_str
        new_file_abs_path = parent_abs_path / new_filename_str
        new_file_rel_path_str = new_file_abs_path.relative_to(self.project_path).as_posix()
        try:
            new_file_abs_path.touch()
            self.repo.index.add([str(new_file_abs_path)])
            return True, f"File '{new_filename_str}' created.", new_file_rel_path_str
        except Exception as e:
            return False, f"Error creating file: {e}", None

    def create_folder(self, relative_parent_dir_str: str, new_folder_name_str: str) -> tuple[bool, str, Optional[str]]:
        if not self.repo: return False, "No active repository.", None
        parent_abs_path = self.project_path / relative_parent_dir_str
        new_folder_abs_path = parent_abs_path / new_folder_name_str
        new_folder_rel_path_str = new_folder_abs_path.relative_to(self.project_path).as_posix()
        try:
            new_folder_abs_path.mkdir()
            gitkeep_path = new_folder_abs_path / ".gitkeep"
            gitkeep_path.touch()
            self.repo.index.add([str(gitkeep_path)])
            return True, f"Folder '{new_folder_name_str}' created.", new_folder_rel_path_str
        except Exception as e:
            return False, f"Error creating folder: {e}", None

    def move_item(self, relative_item_path_str: str, relative_target_dir_str: str, new_name_str: Optional[str] = None) -> tuple[bool, str, Optional[str]]:
        if not self.repo: return False, "No active repository.", None
        source_abs_path = self.project_path / relative_item_path_str
        target_dir_abs_path = self.project_path / relative_target_dir_str
        final_name = new_name_str if new_name_str else source_abs_path.name
        destination_abs_path = target_dir_abs_path / final_name
        try:
            self.repo.git.mv(str(source_abs_path), str(destination_abs_path))
            new_final_rel_path = destination_abs_path.relative_to(self.project_path).as_posix()
            return True, "Item moved successfully.", new_final_rel_path
        except Exception as e:
            return False, f"Error moving item: {e}", None

    def copy_external_items(self, source_abs_paths: List[str], target_project_rel_dir: str) -> tuple[bool, str, List[Dict[str, str]]]:
        if not self.repo: return False, "No active repository.", []
        target_dir_abs_path = self.project_path / target_project_rel_dir
        target_dir_abs_path.mkdir(parents=True, exist_ok=True)
        copied_infos, paths_to_stage, errors = [], [], []
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
                paths_to_stage.append(str(dest_path))
            except Exception as e:
                errors.append(f"Error copying '{src_path.name}': {e}")
        if paths_to_stage:
            self.stage_files(paths_to_stage)
        if errors:
            return False, "\n".join(errors), copied_infos
        return True, f"Copied {len(copied_infos)} items.", copied_infos

    def _create_gitignore_if_needed(self):
        gitignore_path = self.project_path / ".gitignore"
        default_content = "# Kintsugi AvA Default Ignore\n.venv/\nvenv/\n__pycache__/\n*.py[co]\nrag_db/\n.env\n*.log\n"
        if not gitignore_path.exists():
            gitignore_path.write_text(default_content)