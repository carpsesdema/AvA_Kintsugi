import subprocess
import shutil
from pathlib import Path

# --- Configuration ---
SPEC_FILE = "main.spec"
APP_NAME = "Kintsugi AvA"

# Define project paths
project_root = Path(__file__).parent
build_dir = project_root / "build"
dist_dir = project_root / "dist"

def main():
    """Main build process."""
    print(f"--- Starting build for {APP_NAME} ---")

    # 1. Clean up old build artifacts
    print("Step 1: Cleaning up old build and distribution directories...")
    try:
        if build_dir.exists():
            shutil.rmtree(build_dir)
            print(f" - Removed old build directory: {build_dir}")
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
            print(f" - Removed old distribution directory: {dist_dir}")
        print(" - Cleanup complete.")
    except Exception as e:
        print(f"  - Warning: Could not completely clean old directories: {e}")

    # 2. Run PyInstaller
    print(f"\nStep 2: Running PyInstaller with spec file: {SPEC_FILE}...")
    command = [
        "pyinstaller",
        SPEC_FILE,
        "--noconfirm"  # Automatically overwrite previous build output
    ]

    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        print(" - PyInstaller finished successfully.")
        # print(process.stdout) # Uncomment for detailed PyInstaller output
        if process.stderr:
            print("\n--- PyInstaller Warnings ---")
            print(process.stderr)
            print("--------------------------\n")

    except FileNotFoundError:
        print("\n[ERROR] PyInstaller is not installed or not in your PATH.")
        print("Please install it by running: pip install pyinstaller")
        return
    except subprocess.CalledProcessError as e:
        print("\n[ERROR] PyInstaller failed to build the application.")
        print("--- PyInstaller Output ---")
        print(e.stdout)
        print("--- PyInstaller Errors ---")
        print(e.stderr)
        print("--------------------------")
        return

    # 3. Final instructions
    print("\n--- Build Complete! ---")
    print(f"The standalone application has been created in:")
    print(f"{dist_dir.resolve()}\\main")
    print("\nTo run your application, execute:")
    print(f"{dist_dir.resolve()}\\main\\main.exe")
    print("-----------------------\n")


if __name__ == "__main__":
    main()