# src/ava/core/project_manager.py
import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
import traceback  # For detailed error logging

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
        if not GIT_AVAILABLE:
            # This will be an issue if not handled, but let's not crash the constructor
            print("[ProjectManager] WARNING: GitPython not installed. Git features will be disabled.")

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
        """
        Tries to find a suitable Python executable for creating virtual environments.
        It prioritizes system Python installations over potentially bundled executables.
        """
        print("[ProjectManager] Attempting to find a base Python executable for venv creation...")
        candidates = []

        # 1. Check common system Python paths (more robust for finding non-bundled Python)
        if sys.platform == "win32":
            # Look in common install locations, PATH might not always be reliable
            # for finding the "base" Python when run from a venv or bundle.
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
            local_app_data = os.environ.get("LOCALAPPDATA", "")

            # Python versions from python.org installer (user)
            if local_app_data:
                python_user_dir = Path(local_app_data) / "Programs" / "Python"
                if python_user_dir.exists():
                    for version_dir in sorted(python_user_dir.iterdir(), reverse=True):  # Prefer newer
                        if version_dir.is_dir() and (version_dir / "python.exe").exists():
                            candidates.append(str(version_dir / "python.exe"))

            # Python versions from python.org installer (system)
            python_system_dirs = [Path(program_files) / "Python39", Path(program_files) / "Python310",
                                  Path(program_files) / "Python311", Path(program_files) / "Python312",
                                  # Add more as needed
                                  Path(program_files_x86) / "Python39", Path(program_files_x86) / "Python310",
                                  Path(program_files_x86) / "Python311", Path(program_files_x86) / "Python312"
                                  ]  # Common system-wide install paths
            for p_dir in python_system_dirs:
                if p_dir.exists() and (p_dir / "python.exe").exists():
                    candidates.append(str(p_dir / "python.exe"))
        else:  # Linux/macOS
            common_paths = ["/usr/bin/python3", "/usr/local/bin/python3", "/opt/homebrew/bin/python3"]
            for p_path in common_paths:
                if Path(p_path).exists():
                    candidates.append(p_path)

        # 2. Check sys.base_prefix (if different from sys.prefix, indicates we are in a venv)
        if sys.prefix != sys.base_prefix:
            if sys.platform == "win32":
                candidates.append(str(Path(sys.base_prefix) / "python.exe"))
                candidates.append(str(Path(sys.base_prefix) / "Scripts" / "python.exe"))
            else:
                candidates.append(str(Path(sys.base_prefix) / "bin" / "python"))
                candidates.append(str(Path(sys.base_prefix) / "bin" / "python3"))

        # 3. Check sys.executable itself (but be wary if it's the bundled app)
        # We want to avoid using the bundled Avakin.exe to create a venv if possible.
        if not getattr(sys, 'frozen', False) or not sys.executable.lower().endswith("avakin.exe"):
            candidates.append(sys.executable)

        # 4. Fallback to checking PATH
        for cmd in ["python3", "python"]:
            path_found = shutil.which(cmd)
            if path_found:
                candidates.append(path_found)

        print(f"[ProjectManager] Candidate Python executables for venv: {candidates}")

        # Validate candidates
        for candidate_path_str in candidates:
            candidate = Path(candidate_path_str)
            if candidate.exists() and candidate.is_file() and os.access(candidate, os.X_OK):
                # Crucially, ensure it's not our own bundled executable if we are frozen
                if getattr(sys, 'frozen', False) and candidate.resolve() == Path(sys.executable).resolve():
                    print(f"[ProjectManager] Skipping candidate '{candidate}' as it's the bundled app itself.")
                    continue

                print(f"[ProjectManager] Validating candidate: {candidate}")
                if self._validate_python_executable(str(candidate)):
                    print(f"[ProjectManager] Using Python executable for venv: {candidate}")
                    return str(candidate)

        error_msg = "Could not find a suitable standalone Python executable to create virtual environments. Please ensure Python is installed and in your PATH."
        print(f"[ProjectManager] ERROR: {error_msg}")
        raise RuntimeError(error_msg)

    def _validate_python_executable(self, python_path: str) -> bool:
        try:
            # Check version
            result_version = subprocess.run([python_path, "--version"], capture_output=True, text=True, timeout=5,
                                            check=False)
            if result_version.returncode != 0:
                print(
                    f"[ProjectManager] Validation fail (version): {python_path} - RC: {result_version.returncode}, Err: {result_version.stderr}")
                return False
            print(f"[ProjectManager] Validation (version): {python_path} -> {result_version.stdout.strip()}")

            # Check if it can run the venv module
            result_venv = subprocess.run([python_path, "-m", "venv", "--help"], capture_output=True, text=True,
                                         timeout=10, check=False)
            if result_venv.returncode == 0:
                print(f"[ProjectManager] Validation success (venv): {python_path}")
                return True
            else:
                print(
                    f"[ProjectManager] Validation fail (venv): {python_path} - RC: {result_venv.returncode}, Err: {result_venv.stderr}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError) as e:
            print(f"[ProjectManager] Validation exception for {python_path}: {e}")
            return False

    def new_project(self, project_name: str = "New_Project") -> str | None:
        timestamp = datetime.now().strftime("%Ym%d_%H%M%S")
        dir_name = f"{''.join(c for c in project_name if c.isalnum())}_{timestamp}"
        project_path = self.workspace_root / dir_name

        print(f"[ProjectManager] Attempting to create new project at: {project_path}")
        project_path.mkdir(parents=True, exist_ok=True)  # Ensure parent dirs exist

        try:
            self.active_project_path = project_path
            self.is_existing_project = False
            self.active_dev_branch = None

            if GIT_AVAILABLE:
                self.repo = git.Repo.init(self.active_project_path)
                self._create_gitignore_if_needed()
                if (self.active_project_path / ".gitignore").exists():
                    self.repo.index.add([".gitignore"])
                self.repo.index.commit("Initial commit by Kintsugi AvA")
                print(f"[ProjectManager] Git repository initialized for new project.")
            else:
                self.repo = None
                print(f"[ProjectManager] GitPython not available. Skipping Git initialization.")

            self._create_virtual_environment()  # This is the critical call

            print(f"[ProjectManager] Successfully created new project at: {self.active_project_path}")
            return str(self.active_project_path)
        except (git.GitCommandError if GIT_AVAILABLE else RuntimeError, subprocess.CalledProcessError,
                FileNotFoundError, RuntimeError) as e:
            print(f"[ProjectManager] CRITICAL ERROR during new project creation: {e}\n{traceback.format_exc()}")
            if self.active_project_path and self.active_project_path.exists():  # Clean up partially created project
                shutil.rmtree(self.active_project_path, ignore_errors=True)
            self.active_project_path = None
            self.repo = None
            return None
        except Exception as e:  # Catch-all for unexpected errors
            print(f"[ProjectManager] UNEXPECTED ERROR during new project creation: {e}\n{traceback.format_exc()}")
            if self.active_project_path and self.active_project_path.exists():  # Clean up
                shutil.rmtree(self.active_project_path, ignore_errors=True)
            self.active_project_path = None
            self.repo = None
            return None

    def load_project(self, path: str) -> str | None:
        project_path = Path(path).resolve()
        if not project_path.is_dir():
            print(f"[ProjectManager] Load failed: {path} is not a directory.")
            return None

        print(f"[ProjectManager] Loading project from: {project_path}")
        self.active_project_path = project_path
        self.is_existing_project = True
        self.active_dev_branch = None

        if GIT_AVAILABLE:
            try:
                self.repo = git.Repo(self.active_project_path)
                print(f"[ProjectManager] Loaded existing Git repository.")
            except InvalidGitRepositoryError:
                print(
                    f"[ProjectManager] No Git repository found at {self.active_project_path}. Initializing a new one.")
                self.repo = git.Repo.init(self.active_project_path)
            except GitCommandError as e:
                print(f"[ProjectManager] Git error on project load: {e}")
                self.repo = None  # Proceed without Git features if repo is corrupted or inaccessible
                # Do not return None here, allow loading project even if Git fails
        else:
            self.repo = None
            print(f"[ProjectManager] GitPython not available. Project loaded without Git features.")

        if self.repo:  # Only try to interact with repo if it was successfully loaded/initialized
            try:
                _ = self.repo.head.commit  # Check if there's at least one commit
            except (ValueError, GitCommandError):  # Handles empty repo or repo with no commits
                print("[ProjectManager] Loaded repo has no commits. Creating initial baseline commit.")
                self._create_gitignore_if_needed()
                if (self.active_project_path / ".gitignore").exists():
                    self.repo.git.add(A=True)  # Stage .gitignore and any other existing files
                if self.repo.index.entries:  # Check if there's anything to commit
                    self.repo.index.commit("Baseline commit for existing files by Kintsugi AvA")
                    print("[ProjectManager] Created baseline commit for existing files.")
                else:
                    print("[ProjectManager] Repo is empty, no baseline commit needed yet.")

        print(f"[ProjectManager] Project loaded: {self.active_project_path}")
        return str(self.active_project_path)

    def begin_modification_session(self) -> str | None:
        if not self.repo:
            print("[ProjectManager] Cannot begin modification session: No Git repository.")
            return None
        dev_branch_name = f"dev_{datetime.now().strftime('%Ym%d_%H%M%S')}"
        try:
            self.active_dev_branch = self.repo.create_head(dev_branch_name)
            self.active_dev_branch.checkout()
            print(f"[ProjectManager] Created and checked out new development branch: {dev_branch_name}")
            return dev_branch_name
        except GitCommandError as e:
            print(f"[ProjectManager] Error creating development branch: {e}")
            return f"Error creating branch: {e}"  # Return error message

    def write_and_stage_files(self, files: dict[str, str]):
        if not self.active_project_path:
            print("[ProjectManager] Error: No active project path to write files.")
            return

        paths_to_stage = []
        for relative_path_str, content in files.items():
            full_path = self.active_project_path / relative_path_str
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding='utf-8')
                paths_to_stage.append(str(full_path))
                print(f"[ProjectManager] Wrote file: {full_path}")
            except Exception as e:
                print(f"[ProjectManager] Error writing file {relative_path_str}: {e}")

        if self.repo and paths_to_stage:
            try:
                self.repo.index.add(paths_to_stage)
                print(f"[ProjectManager] Staged {len(paths_to_stage)} files.")
            except GitCommandError as e:
                print(f"[ProjectManager] Error staging files: {e}")
        elif not self.repo and paths_to_stage:
            print(f"[ProjectManager] {len(paths_to_stage)} files written. Git staging skipped (no repo).")

    def save_and_commit_files(self, files: dict[str, str], commit_message: str):
        self.write_and_stage_files(files)
        if self.repo:  # Only commit if repo exists
            self.commit_staged_files(commit_message)

    def read_file(self, relative_path: str) -> str | None:
        if not self.active_project_path:
            print("[ProjectManager] Cannot read file: No active project path.")
            return None
        full_path = self.active_project_path / relative_path
        if not full_path.exists():
            print(f"[ProjectManager] File not found for reading: {full_path}")
            return None
        try:
            return full_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"[ProjectManager] Error reading file {full_path}: {e}")
            return None

    def get_project_files(self) -> dict[str, str]:
        if not self.active_project_path:
            print("[ProjectManager] Cannot get project files: No active project path.")
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
                # Check if any part of the path is in ignore_dirs
                if any(part in ignore_dirs for part in item.relative_to(self.active_project_path).parts):
                    continue
                if item.is_file():
                    if item.suffix.lower() not in allowed_extensions:
                        # print(f"[ProjectManager] Skipping file with unallowed extension: {item.name}")
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
            if not self.repo.head.is_valid():  # Check if HEAD is valid (e.g., repo might be empty)
                # If no valid HEAD, diff against cached (staged) changes
                return self.repo.git.diff('--cached')
            # Diff working directory against HEAD
            return self.repo.git.diff('HEAD')
        except (GitCommandError, ValueError) as e:
            print(f"[ProjectManager] Warning: Could not get git diff (might be a new repo or other issue): {e}")
            # Attempt to diff staged changes if HEAD diff fails
            try:
                return self.repo.git.diff('--cached')
            except Exception as e_cached:
                print(f"[ProjectManager] Warning: Could not get cached git diff either: {e_cached}")
                return "Could not retrieve git diff. Repository might be in an empty or unusual state."
        except Exception as e:  # Catch-all for other unexpected errors
            print(f"[ProjectManager] An unexpected error occurred while getting git diff: {e}")
            return "An unexpected error occurred while getting the git diff."

    def _create_gitignore_if_needed(self):
        if not self.repo:  # Check if repo object exists
            print("[ProjectManager] Cannot create .gitignore: No Git repository.")
            return
        gitignore_path = Path(self.repo.working_dir) / ".gitignore"
        default_ignore_content = "# Kintsugi AvA Default Ignore\n.venv/\nvenv/\n__pycache__/\n*.py[co]\nrag_db/\n.env\n*.log\n"
        if not gitignore_path.exists():
            gitignore_path.write_text(default_ignore_content)
            print(f"[ProjectManager] Created default .gitignore file at {gitignore_path}")
        else:  # Ensure essential lines are present
            current_content = gitignore_path.read_text()
            missing_lines = []
            for line in default_ignore_content.splitlines():
                if line.strip() and line.strip() not in current_content:
                    missing_lines.append(line)
            if missing_lines:
                with gitignore_path.open("a") as f:
                    f.write("\n# Added by Kintsugi AvA\n")
                    f.write("\n".join(missing_lines) + "\n")
                print(f"[ProjectManager] Appended essential Kintsugi AvA ignores to existing .gitignore")

    def _create_virtual_environment(self):
        if not self.active_project_path:
            print("[ProjectManager] Cannot create venv: No active project path.")
            return
        venv_path = self.active_project_path / ".venv"
        print(f"[ProjectManager] Attempting to create virtual environment at: {venv_path}")
        try:
            base_python = self._get_base_python_executable()  # This now raises RuntimeError if no suitable python is found
            print(f"[ProjectManager] Creating virtual environment using: {base_python}")

            # --- MODIFICATION: Add startupinfo for Windows ---
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            # --- END MODIFICATION ---

            # Using subprocess.run to create the venv
            result = subprocess.run(
                [base_python, "-m", "venv", str(venv_path)],
                check=True, capture_output=True, text=True, timeout=180,  # Increased timeout
                startupinfo=startupinfo  # MODIFIED: Pass startupinfo
            )
            print(f"[ProjectManager] Virtual environment creation stdout: {result.stdout}")
            if result.stderr:
                print(f"[ProjectManager] Virtual environment creation stderr: {result.stderr}")

            print(f"[ProjectManager] Virtual environment created successfully in {venv_path}.")

            # Verify venv creation
            expected_python = self.venv_python_path
            if not expected_python or not expected_python.exists():
                error_msg = f"Virtual environment creation appeared to succeed, but Python executable not found at expected location: {expected_python}. This can happen if the base Python used ('{base_python}') is incompatible or has issues with venv creation."
                print(f"[ProjectManager] ERROR: {error_msg}")
                raise RuntimeError(error_msg)
            print(f"[ProjectManager] Verified venv Python at: {expected_python}")

        except subprocess.TimeoutExpired:
            error_msg = "Virtual environment creation timed out after 3 minutes."
            print(f"[ProjectManager] ERROR: {error_msg}")
            raise RuntimeError(error_msg)
        except subprocess.CalledProcessError as e:
            error_details = f"Command: {' '.join(e.cmd)}\nReturn code: {e.returncode}\nStdout: {e.stdout}\nStderr: {e.stderr}"
            print(f"[ProjectManager] ERROR: Virtual environment creation failed.\n{error_details}")
            raise RuntimeError(f"Virtual environment creation failed: {e.stderr or e.stdout or 'Unknown error'}")
        except RuntimeError as e:  # Catch RuntimeError from _get_base_python_executable or verification
            print(f"[ProjectManager] ERROR: Critical issue during venv setup: {e}")
            raise  # Re-raise to be caught by new_project
        except Exception as e:  # Catch any other unexpected errors
            print(f"[ProjectManager] ERROR: Unexpected error during venv creation: {e}\n{traceback.format_exc()}")
            raise RuntimeError(f"Unexpected error during venv creation: {e}")

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

    def commit_staged_files(self, commit_message: str) -> str:
        if not self.repo:
            return "Error: No active Git repository."
        if not self.repo.is_dirty(index=True, working_tree=False, untracked_files=False):
            return "No changes staged for commit."
        try:
            self.repo.index.commit(commit_message)
            msg = f"Committed staged changes to branch '{self.repo.active_branch.name}'."
            print(f"[ProjectManager] {msg}")
            return msg
        except GitCommandError as e:
            if "nothing to commit" in str(e).lower() or "no changes added to commit" in str(e).lower():
                return "No changes staged for commit."
            err_msg = f"Error committing changes: {e}"
            print(f"[ProjectManager] {err_msg}")
            return err_msg