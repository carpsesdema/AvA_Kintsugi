# release_helper.py
import sys
import re
import json
import webbrowser
import subprocess
import shutil
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR_NAME = "Avakin_Dist"
FINAL_BUILDS_DIR_NAME = "final_builds"
SETUP_CORE_FILE = PROJECT_ROOT / "setup_core.py"
SETUP_LAUNCHER_FILE = PROJECT_ROOT / "setup_launcher.py"
BUILD_DIST_SCRIPT = PROJECT_ROOT / "build_dist.py"
VERSION_TXT_FILE = PROJECT_ROOT / "version.txt"
VERSION_MANIFEST_FILE = PROJECT_ROOT / "version_manifest.json"
GITHUB_REPO_URL = "https://github.com/carpsesdema/AvA_Kintsugi"


def run_command(command):
    """Runs a command, prints its output, and checks for errors."""
    print(f"--- Running: {' '.join(command)} ---")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"--- STDERR ---\n{result.stderr}", file=sys.stderr)
    if result.returncode != 0:
        print(f"❌ ERROR: Command failed with code {result.returncode}")
        sys.exit(1)
    print("--- Success ---\n")


def get_current_version(file_path: Path) -> str:
    """Reads the version from setup_core.py"""
    content = file_path.read_text()
    match = re.search(r"version\s*=\s*[\"'](\d+\.\d+\.\d+)[\"']", content)
    if not match:
        print(f"❌ ERROR: Could not find version string in {file_path}")
        sys.exit(1)
    return match.group(1)


def update_file_version(file_path: Path, new_version: str, is_setup_file: bool = True):
    """Updates the version string in a given file."""
    try:
        content = file_path.read_text()
        if is_setup_file:
            new_content, count = re.subn(
                r"(version\s*=\s*[\"'])(\d+\.\d+\.\d+)([\"'])",
                f"\\1{new_version}\\3",
                content
            )
        else:  # For other text files, assume version is the only content
            new_content, count = (new_version, 1) if content.strip() != new_version else (content, 0)

        if count > 0:
            file_path.write_text(new_content)
            print(f"✅ Updated version in {file_path.name}")
        else:
            print(f"⚠️  Could not find version pattern to update in {file_path.name}")
    except Exception as e:
        print(f"❌ ERROR updating {file_path.name}: {e}")


def main():
    # 1. Version Bumping
    current_version = get_current_version(SETUP_CORE_FILE)
    major, minor, patch = map(int, current_version.split('.'))

    while True:
        bump_type = input(f"Current version is {current_version}. Bump (p)atch, (m)inor, or (j)major? ").lower()
        if bump_type in ['p', 'm', 'j']:
            break
        print("Invalid input. Please enter 'p', 'm', or 'j'.")

    if bump_type == 'p':
        patch += 1
    elif bump_type == 'm':
        minor += 1; patch = 0
    elif bump_type == 'j':
        major += 1; minor = 0; patch = 0
    new_version = f"{major}.{minor}.{patch}"

    print("-" * 30)
    print(f"New version will be: {new_version}")
    if input("Is this correct? (y/n): ").lower() != 'y':
        print("Aborted.")
        sys.exit(0)

    print("\n🚀 Starting release process...")
    update_file_version(SETUP_CORE_FILE, new_version)
    update_file_version(SETUP_LAUNCHER_FILE, new_version)
    update_file_version(VERSION_TXT_FILE, new_version, is_setup_file=False)

    try:
        manifest_data = json.loads(VERSION_MANIFEST_FILE.read_text())
        manifest_data['latest_version'] = new_version
        manifest_data['download_url'] = f"{GITHUB_REPO_URL}/releases/download/v{new_version}/Avakin_v{new_version}.zip"
        VERSION_MANIFEST_FILE.write_text(json.dumps(manifest_data, indent=2))
        print(f"✅ Updated version and URL in {VERSION_MANIFEST_FILE.name}")
    except Exception as e:
        print(f"❌ ERROR updating {VERSION_MANIFEST_FILE.name}: {e}")

    # 2. Build Main Application
    print("\n📦 Building main application...")
    run_command([sys.executable, str(BUILD_DIST_SCRIPT)])

    # 3. Build Launcher
    print("\n📦 Building launcher...")
    run_command([sys.executable, str(SETUP_LAUNCHER_FILE), "build"])

    build_output_dir = next((d for d in (PROJECT_ROOT / "build").iterdir() if d.is_dir() and d.name.startswith("exe.")),
                            None)
    if not build_output_dir:
        print("❌ ERROR: Could not find launcher build output directory.")
        sys.exit(1)

    launcher_exe = build_output_dir / "AvakinLauncher.exe"
    if not launcher_exe.exists():
        print(f"❌ ERROR: {launcher_exe.name} not found in build output.")
        sys.exit(1)

    # 4. Combine and Zip
    print("\n📦 Assembling final release package...")
    dist_path = PROJECT_ROOT / DIST_DIR_NAME
    final_builds_path = PROJECT_ROOT / FINAL_BUILDS_DIR_NAME
    final_builds_path.mkdir(exist_ok=True)

    # Move launcher into the main app dist folder
    shutil.move(str(launcher_exe), str(dist_path / "AvakinLauncher.exe"))
    shutil.rmtree(PROJECT_ROOT / "build")  # Clean up empty build folder

    zip_filename_base = final_builds_path / f"Avakin_v{new_version}"
    shutil.make_archive(str(zip_filename_base), 'zip', dist_path)
    print(f"✅ Successfully created release archive: {zip_filename_base}.zip")

    # 5. Open GitHub Releases Page
    release_url = f"{GITHUB_REPO_URL}/releases/new?tag=v{new_version}&title=Avakin v{new_version}"
    print(f"\n🌍 Opening GitHub release page for tag v{new_version}...")
    webbrowser.open(release_url)

    print("\n" + "=" * 50)
    print("✅  Release helper finished!")
    print("Next Steps:")
    print("  1. Your browser has opened to the 'New release' page on GitHub.")
    print(f"  2. The tag name should be pre-filled with 'v{new_version}'.")
    print(f"  3. Find the zip file in the '{FINAL_BUILDS_DIR_NAME}' folder.")
    print("  4. Drag and drop the zip file onto the release page.")
    print("  5. Write some release notes and click 'Publish release'.")
    print("=" * 50)


if __name__ == "__main__":
    main()