import os
from pathlib import Path
from typing import List


class DirectoryScannerService:
    """
    A service dedicated to scanning directories and finding files
    that are suitable for RAG processing, respecting common ignore patterns.
    """

    def __init__(self):
        # File types we are interested in processing
        self.supported_extensions = {
            '.py', '.js', '.ts', '.html', '.css', '.md', '.txt', '.json',
            '.toml', '.rst', '.java', '.c', '.cpp', '.cs', '.go', '.rb',
        }
        # Directories to completely ignore during scanning
        self.ignore_dirs = {
            '.git', '__pycache__', '.venv', 'venv', 'node_modules',
            'build', 'dist', '.idea', '.vscode', 'rag_db'
        }
        print("[DirectoryScanner] Initialized.")

    def scan(self, directory_path_str: str) -> List[Path]:
        """
        Scans a given directory recursively for supported file types.

        Args:
            directory_path_str: The string path to the directory to scan.

        Returns:
            A list of Path objects for each valid and supported file found.
        """
        directory_path = Path(directory_path_str)
        if not directory_path.is_dir():
            print(f"[DirectoryScanner] Error: Path is not a directory: {directory_path}")
            return []

        print(f"[DirectoryScanner] Starting scan of: {directory_path}")
        found_files = []

        for root, dirs, files in os.walk(directory_path, topdown=True):
            # Modify dirs in-place to prevent os.walk from descending into ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

            for file_name in files:
                if Path(file_name).suffix.lower() in self.supported_extensions:
                    file_path = Path(root) / file_name
                    found_files.append(file_path)

        print(f"[DirectoryScanner] Scan complete. Found {len(found_files)} supported files.")
        return found_files