# src/ava/core/venv_manager.py
# NEW FILE

import os
import sys
import subprocess
import shutil
from pathlib import Path
import traceback
from typing import Optional


class VenvManager:
    """
    Manages all virtual environment operations for a single project.
    This includes creation and path discovery.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path

    @property
    def python_path(self) -> Optional[Path]:
        """Returns the path to the Python executable within the venv."""
        venv_dir = self.project_path / ".venv"
        if not venv_dir.is_dir():
            return None
        python_exe = venv_dir / "Scripts" / "python.exe" if sys.platform == "win32" else venv_dir / "bin" / "python"
        return python_exe if python_exe.exists() else None

    @property
    def is_active(self) -> bool:
        """Checks if the virtual environment is correctly set up."""
        return self.python_path is not None

    def get_info(self) -> dict:
        """Gets information about the virtual environment status."""
        if not self.project_path:
            return {"active": False, "reason": "No project"}
        venv_path = self.project_path / ".venv"
        if not venv_path.exists():
            return {"active": False, "reason": "No venv"}
        if not self.python_path:
            return {"active": False, "reason": "No Python"}
        return {"active": True}

    def create_venv(self) -> bool:
        """Creates a new virtual environment for the project."""
        venv_path = self.project_path / ".venv"
        print(f"[VenvManager] Attempting to create virtual environment at: {venv_path}")
        try:
            base_python = self._get_base_python_executable()
            print(f"[VenvManager] Creating virtual environment using: {base_python}")

            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(
                [base_python, "-m", "venv", str(venv_path)],
                check=True, capture_output=True, text=True, timeout=180,
                startupinfo=startupinfo
            )

            if result.stderr and "Error" in result.stderr:
                raise RuntimeError(f"Venv creation failed with error: {result.stderr}")

            print(f"[VenvManager] Virtual environment created successfully.")
            return True
        except (subprocess.CalledProcessError, RuntimeError) as e:
            print(f"[VenvManager] ERROR: Virtual environment creation failed.\n{traceback.format_exc()}")
            return False
        except Exception as e:
            print(f"[VenvManager] ERROR: Unexpected error during venv creation: {e}\n{traceback.format_exc()}")
            return False

    def _get_base_python_executable(self) -> str:
        """Finds a suitable Python executable for creating virtual environments."""
        print("[VenvManager] Attempting to find a base Python executable...")
        # Prioritize system Python over bundled executable
        if sys.prefix != sys.base_prefix:
            base_python = Path(sys.base_prefix) / ("python.exe" if sys.platform == "win32" else "bin/python")
            if self._validate_python_executable(str(base_python)):
                return str(base_python)

        # Check PATH
        for cmd in ["python3", "python"]:
            path_found = shutil.which(cmd)
            if path_found and self._validate_python_executable(path_found):
                # Avoid using the running executable if it's the bundled app itself
                if getattr(sys, 'frozen', False) and Path(path_found).resolve() == Path(sys.executable).resolve():
                    continue
                return path_found

        # Last resort: sys.executable (if not frozen)
        if not getattr(sys, 'frozen', False) and self._validate_python_executable(sys.executable):
            return sys.executable

        raise RuntimeError("Could not find a suitable standalone Python executable for venv creation.")

    def _validate_python_executable(self, python_path: str) -> bool:
        """Validates if a Python executable can create a venv."""
        try:
            result = subprocess.run([python_path, "-m", "venv", "--help"], capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False