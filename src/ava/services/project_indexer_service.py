import ast
from pathlib import Path
from typing import Dict


class ProjectIndexerService:
    """
    Scans a Python project directory and builds an index of all globally
    defined classes and functions.
    """

    def __init__(self):
        self.index: Dict[str, str] = {}
        print("[ProjectIndexer] Initialized.")

    def build_index(self, project_root: Path) -> Dict[str, str]:
        """
        Scans all Python files in a project root and builds the definition index.

        Args:
            project_root: The root path of the project to scan.

        Returns:
            A dictionary mapping definition names to their module paths.
        """
        self.index = {}
        if not project_root.is_dir():
            return {}

        print(f"[ProjectIndexer] Starting scan of project: {project_root}")
        for py_file in project_root.rglob("*.py"):
            # Exclude files in virtual environments
            if ".venv" in py_file.parts or "venv" in py_file.parts:
                continue

            try:
                self._parse_file(py_file, project_root)
            except Exception as e:
                print(f"[ProjectIndexer] Warning: Could not parse {py_file.name}: {e}")

        print(f"[ProjectIndexer] Scan complete. Found {len(self.index)} definitions.")
        return self.index

    def _parse_file(self, file_path: Path, project_root: Path):
        """Parses a single Python file to find class and function definitions."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        # Calculate the Python module path (e.g., 'game_logic.player')
        relative_path = file_path.relative_to(project_root)
        # Ensure consistent path separators (posix style) for module paths
        module_path = str(relative_path.with_suffix('')).replace('\\', '/').replace('/', '.')

        for node in ast.walk(tree):
            # We only care about top-level definitions for this index
            is_top_level = isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))

            # Check if it's at the top level of the module (not nested in another function/class)
            parent_is_module = isinstance(node, ast.AST) and hasattr(node, 'parent') and isinstance(node.parent,
                                                                                                    ast.Module)

            if is_top_level:
                # A simpler way to check for top-level is to check the column offset
                if hasattr(node, 'col_offset') and node.col_offset == 0:
                    definition_name = node.name
                    if definition_name in self.index:
                        # Handle potential name collisions if necessary
                        print(
                            f"[ProjectIndexer] Warning: Duplicate definition found for '{definition_name}'. Overwriting.")
                    self.index[definition_name] = module_path