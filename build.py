import subprocess
import shutil
from pathlib import Path

# --- Configuration ---
SPEC_FILE = "main.spec"
# --- THIS IS THE FIX ---
# Change the APP_NAME to 'Avakin'. This will make PyInstaller create 'Avakin.exe',
# which is exactly what your launcher is configured to look for.
APP_NAME = "Avakin"
# --- END OF FIX ---
APP_VERSION = "1.0.0"  # <-- NEW: Version number for the build

# Define project paths
project_root = Path(__file__).parent
build_dir = project_root / "build"
dist_dir = project_root / "dist"

def main():
    """Main build process."""
    print(f"--- Starting build for {APP_NAME} v{APP_VERSION} ---")

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
        if process.stderr:
            print("\n--- PyInstaller Warnings ---\n" + process.stderr + "\n--------------------------\n")
    except FileNotFoundError:
        print("\n[ERROR] PyInstaller is not installed or not in your PATH.")
        print("Please install it by running: pip install pyinstaller")
        return
    except subprocess.CalledProcessError as e:
        print("\n[ERROR] PyInstaller failed to build the application.")
        print(f"--- PyInstaller Output ---\n{e.stdout}\n--- PyInstaller Errors ---\n{e.stderr}")
        return

    # 3. Create version file and ZIP archive
    print("\nStep 3: Packaging final distributable...")
    output_dir = dist_dir / "main" # The folder PyInstaller creates
    if not output_dir.exists():
        print(f"[ERROR] PyInstaller did not create the expected output directory: {output_dir}")
        return

    # 3a. Create version.txt
    try:
        version_file = output_dir / "version.txt"
        version_file.write_text(APP_VERSION)
        print(f" - Created version file: {version_file}")
    except Exception as e:
        print(f"[ERROR] Could not create version.txt: {e}")
        return

    # 3b. Create ZIP archive for distribution
    try:
        archive_name_base = f"{APP_NAME.replace(' ', '_')}_v{APP_VERSION}"
        archive_path = shutil.make_archive(
            base_name=dist_dir / archive_name_base,
            format='zip',
            root_dir=output_dir # This zips the *contents* of the output directory
        )
        print(f" - Successfully created distribution archive: {Path(archive_path).name}")
    except Exception as e:
        print(f"[ERROR] Could not create ZIP archive: {e}")
        return

    # 4. Final instructions
    print("\n--- Build Complete! ---")
    print(f"The distributable archive for your launcher has been created at:")
    print(f"{Path(archive_path).resolve()}")
    print("\nUpload this file to your GitHub Release and update the manifest.")
    print("-----------------------\n")


if __name__ == "__main__":
    main()