import os
from pathlib import Path


class ProjectAnalyzer:
    """
    Analyzes an existing project directory to provide context for modifications.
    Its single responsibility is to read a project's state into a dictionary.
    """

    def __init__(self):
        pass

    def analyze(self, project_path_str: str) -> dict[str, str]:
        """
        Reads all text-based files in a project directory.

        Args:
            project_path_str: The path to the project.

        Returns:
            A dictionary of {relative_filename: file_content}.
        """
        project_path = Path(project_path_str)
        if not project_path.is_dir():
            print(f"[ProjectAnalyzer] Error: Path is not a directory {project_path}")
            return {}

        print(f"[ProjectAnalyzer] Analyzing project at: {project_path}")
        project_files = {}

        # Define files/folders to ignore during analysis
        ignore_list = ['.git', 'venv', '.venv', '__pycache__', 'node_modules', 'build', 'dist', '.idea', '.vscode',
                       'rag_db']

        # Walk through the directory and read files
        for root, dirs, files in os.walk(project_path, topdown=True):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_list]

            for file in files:
                try:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(project_path)

                    # Simple check to avoid trying to read binary files
                    if file_path.suffix.lower() in ['.py', '.js', '.html', '.css', '.md', '.txt', '.json', '.toml',
                                                    '.pyc', '.gitignore', '.env']:
                        project_files[str(relative_path)] = file_path.read_text(encoding='utf-8')
                except Exception:
                    print(f"[ProjectAnalyzer] Warning: Could not read file {file_path}")
                    pass  # Ignore files that can't be read

        print(f"[ProjectAnalyzer] Analysis complete. Found {len(project_files)} readable files.")
        return project_files