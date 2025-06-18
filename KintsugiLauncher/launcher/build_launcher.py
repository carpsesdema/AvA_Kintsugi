# KintsugiLauncher/build_launcher.py

import subprocess
import shutil
from pathlib import Path

# --- Configuration ---
SPEC_FILE = "../launcher.spec"
APP_NAME = "Kintsugi AvA Launcher"

# Define project paths
project_root = Path(__file__).parent
build_dir = project_root / "build"
dist_dir = project_root / "dist"

def main():
    """Main build process for the launcher."""
    print(f"--- Starting build for {APP_NAME} ---")

    # 1. Clean up old build artifacts
    print("Step 1: Cleaning up old build and distribution directories...")
    try:
        if build_dir.exists():
            shutil.rmtree(build_dir)
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        print(" - Cleanup complete.")
    except Exception as e:
        print(f"  - Warning: Could not completely clean old directories: {e}")

    # 2. Run PyInstaller
    print(f"\nStep 2: Running PyInstaller with spec file: {SPEC_FILE}...")
    command = [
        "pyinstaller",
        SPEC_FILE,
        "--noconfirm"
    ]

    try:
        subprocess.run(command, check=True, capture_output=False, text=True)
        print(" - PyInstaller finished successfully.")

    except FileNotFoundError:
        print("\n[ERROR] PyInstaller is not installed or not in your PATH.")
        print("Please install it by running: pip install pyinstaller")
        return
    except subprocess.CalledProcessError as e:
        print("\n[ERROR] PyInstaller failed to build the launcher.")
        print(f"--- PyInstaller Output ---\n{e.stdout}\n--- PyInstaller Errors ---\n{e.stderr}")
        return

    # 3. Final instructions
    print("\n--- Launcher Build Complete! ---")
    print(f"The standalone launcher has been created in:")
    print(f"{dist_dir.resolve()}")
    print("\nTo use the launcher, you would typically place it one level above")
    print("the main application directory.")
    print("---------------------------------\n")

if __name__ == "__main__":
    main()