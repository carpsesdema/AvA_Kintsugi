# build_dist.py
import os
import sys
import subprocess
import shutil
from pathlib import Path

# --- Configuration ---
DIST_DIR_NAME = "Avakin_Dist"
CORE_SETUP_SCRIPT = "setup_core.py"
REQUIREMENTS_FILE = "src/ava/requirements.txt"
RAG_REQUIREMENTS_FILE = "src/ava/requirements_rag.txt"

# --- Main Build Logic ---
def run_command(command):
    """Runs a command and checks for errors."""
    print(f"--- Running: {' '.join(command)} ---")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: Command failed with code {result.returncode}")
        print("--- STDOUT ---")
        print(result.stdout)
        print("--- STDERR ---")
        print(result.stderr)
        sys.exit(1)
    print("--- Success ---")
    return result

def main():
    project_root = Path(__file__).parent.resolve()
    dist_path = project_root / DIST_DIR_NAME

    # 1. Clean up previous distribution
    if dist_path.exists():
        print(f"Removing old distribution directory: {dist_path}")
        shutil.rmtree(dist_path)

    # 2. Build the core Avakin.exe using cx_Freeze
    run_command([sys.executable, CORE_SETUP_SCRIPT, "build"])

    # 3. Find the build output directory
    build_output_dir = next((d for d in (project_root / "build").iterdir() if d.is_dir() and d.name.startswith("exe.")), None)
    if not build_output_dir:
        print("ERROR: Could not find cx_Freeze build output directory.")
        sys.exit(1)

    # 4. Move the built application to our final distribution folder
    print(f"Moving build output to {dist_path}")
    shutil.move(str(build_output_dir), str(dist_path))
    shutil.rmtree(project_root / "build") # Clean up empty build folder

    # 5. Create the private Python virtual environment inside the distribution
    private_venv_path = dist_path / ".venv"
    run_command([sys.executable, "-m", "venv", str(private_venv_path)])

    # 6. Install RAG dependencies into the private venv
    private_pip_exe = str(private_venv_path / "Scripts" / "pip.exe")
    rag_reqs = str(project_root / RAG_REQUIREMENTS_FILE)
    run_command([private_pip_exe, "install", "-r", rag_reqs, "--no-cache-dir"])

    print("\n\n==============================================")
    print(" BUILD COMPLETE!")
    print(f" Portable distribution created at: {dist_path}")
    print(" You can now zip this folder and distribute it.")
    print("==============================================")


if __name__ == "__main__":
    main()