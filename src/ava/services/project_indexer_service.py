# src/ava/services/project_indexer_service.py
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
        return self.index.copy()

    def get_symbols_from_content(self, content: str, module_path: str) -> Dict[str, str]:
        """
        Parses Python code content and returns a dictionary of its top-level symbols.

        Args:
            content: The Python source code as a string.
            module_path: The dot-separated module path (e.g., 'my_app.utils').

        Returns:
            A dictionary mapping symbol names to the provided module_path.
        """
        symbols = {}
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    # A simple way to check for top-level is to check the column offset
                    if hasattr(node, 'col_offset') and node.col_offset == 0:
                        symbols[node.name] = module_path
        except Exception as e:
            print(f"[ProjectIndexer] Warning: Could not parse content for module '{module_path}': {e}")
        return symbols

    def _parse_file(self, file_path: Path, project_root: Path):
        """Parses a single Python file and adds its symbols to the index."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Calculate the Python module path (e.g., 'game_logic.player')
        relative_path = file_path.relative_to(project_root)
        module_path = str(relative_path.with_suffix('')).replace('\\', '/').replace('/', '.')

        new_symbols = self.get_symbols_from_content(content, module_path)
        for symbol, mod_path in new_symbols.items():
            if symbol in self.index:
                print(f"[ProjectIndexer] Warning: Duplicate definition found for '{symbol}'. Overwriting.")
            self.index[symbol] = mod_path