from pathlib import Path
from typing import Optional


class ProjectContextManager:
    """
    Manages project context state and validation for the Code Viewer.
    Single responsibility: Handle project path state and validation.
    """

    def __init__(self):
        self._project_root: Optional[Path] = None
        self._is_valid: bool = False

    @property
    def project_root(self) -> Optional[Path]:
        """Returns the current project root path if valid."""
        return self._project_root if self._is_valid else None

    @property
    def is_valid(self) -> bool:
        """Returns True if the current project context is valid."""
        return self._is_valid and self._project_root is not None

    def set_new_project_context(self, project_path_str: str) -> bool:
        """
        Sets context for a new project being generated.

        Args:
            project_path_str: Path to the new project directory

        Returns:
            True if context was set successfully, False otherwise
        """
        try:
            project_path = Path(project_path_str).resolve()

            if not project_path.exists():
                print(f"[ProjectContext] Error: Project path does not exist: {project_path}")
                self._invalidate()
                return False

            if not project_path.is_dir():
                print(f"[ProjectContext] Error: Project path is not a directory: {project_path}")
                self._invalidate()
                return False

            self._project_root = project_path
            self._is_valid = True
            print(f"[ProjectContext] New project context set: {project_path}")
            return True

        except Exception as e:
            print(f"[ProjectContext] Error setting new project context: {e}")
            self._invalidate()
            return False

    def validate_existing_context(self) -> bool:
        """
        Validates the current project context for modifications.

        Returns:
            True if existing context is valid, False otherwise
        """
        if not self._project_root:
            print("[ProjectContext] Error: No active project context for modifications")
            self._invalidate()
            return False

        if not self._project_root.exists():
            print(f"[ProjectContext] Error: Project path no longer exists: {self._project_root}")
            self._invalidate()
            return False

        self._is_valid = True
        print(f"[ProjectContext] Existing project context validated: {self._project_root}")
        return True

    def get_absolute_path(self, relative_filename: str) -> Optional[Path]:
        """
        Converts a relative filename to an absolute path within the project.

        Args:
            relative_filename: Filename relative to project root

        Returns:
            Absolute Path if valid, None otherwise
        """
        if not self.is_valid:
            return None

        try:
            return self._project_root / relative_filename
        except Exception as e:
            print(f"[ProjectContext] Error resolving path for '{relative_filename}': {e}")
            return None

    def clear_context(self):
        """Clears the current project context."""
        self._invalidate()
        print("[ProjectContext] Context cleared")

    def _invalidate(self):
        """Internal method to invalidate the context."""
        self._project_root = None
        self._is_valid = False