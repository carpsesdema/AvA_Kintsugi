import subprocess
import shutil
from pathlib import Path

# --- Configuration ---
SPEC_FILE = "launcher.spec"
APP_NAME = "Kintsugi AvA Launcher"

# --- Project Paths ---
# Since this script is in the root, the project_root is its parent directory
project_root = Path(__file__).parent.resolve()
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
    spec_path = project_root / SPEC_FILE # Path to the spec file in the root
    print(f"\nStep 2: Running PyInstaller with spec file: {spec_path}...")
    # --- THIS IS THE FIX ---
    # We remove the --hidden-import from the command line because
    # the launcher.spec file is now handling all the configuration.
    command = [
        "pyinstaller",
        str(spec_path),
        "--noconfirm"
    ]
    # --- END OF FIX ---
    try:
        # Run from the project root directory for correct path context
        subprocess.run(command, check=True, capture_output=False, text=True, cwd=project_root)
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
    output_folder = dist_dir / 'KintsugiLauncher'
    print("\n--- Launcher Build Complete! ---")
    print(f"The standalone launcher has been created in:")
    print(f"{output_folder.resolve()}")
    print("\nTo test, copy this 'KintsugiLauncher' folder to a clean directory")
    print("(like C:\\app_testing\\) and run the .exe from there.")
    print("----------------------------------\n")


if __name__ == "__main__":
    main()