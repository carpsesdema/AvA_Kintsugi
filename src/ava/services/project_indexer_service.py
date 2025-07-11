# src/ava/services/project_indexer_service.py
import ast
from pathlib import Path
from typing import Dict

from src.ava.utils.code_summarizer import CodeSummarizer


class ProjectIndexerService:
    """
    Scans a Python project directory and builds an index of structural summaries
    for each file, including imports, classes, and function signatures.
    """

    def __init__(self):
        self.index: Dict[str, str] = {}
        print("[ProjectIndexer] Initialized.")

    def build_index(self, project_root: Path) -> Dict[str, str]:
        """
        Scans all Python files in a project root and builds a summary index.

        Args:
            project_root: The root path of the project to scan.

        Returns:
            A dictionary mapping relative file paths to their structural summaries.
        """
        self.index = {}
        if not project_root.is_dir():
            return {}

        print(f"[ProjectIndexer] Starting project summary scan: {project_root}")
        for py_file in project_root.rglob("*.py"):
            if ".venv" in py_file.parts or "venv" in py_file.parts:
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                if content.strip():  # Only process non-empty files
                    relative_path_str = str(py_file.relative_to(project_root).as_posix())
                    summarizer = CodeSummarizer(content)
                    summary = summarizer.summarize()
                    self.index[relative_path_str] = summary
            except Exception as e:
                print(f"[ProjectIndexer] Warning: Could not parse {py_file.name}: {e}")

        print(f"[ProjectIndexer] Scan complete. Summarized {len(self.index)} files.")
        return self.index.copy()

    def get_summary_from_content(self, content: str) -> str:
        """
        Generates a structural summary from a string of Python code.

        Args:
            content: The Python source code as a string.

        Returns:
            The structural summary.
        """
        if not content.strip():
            return ""
        try:
            summarizer = CodeSummarizer(content)
            return summarizer.summarize()
        except Exception as e:
            print(f"[ProjectIndexer] Warning: Could not summarize content: {e}")
            return f"# Error: Could not summarize code. {e}"
