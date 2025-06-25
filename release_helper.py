# release_helper.py
import sys
import re
import json
import webbrowser
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent
SETUP_CORE_FILE = PROJECT_ROOT / "setup_core.py"
VERSION_TXT_FILE = PROJECT_ROOT / "version.txt"
VERSION_MANIFEST_FILE = PROJECT_ROOT / "version_manifest.json"
GITHUB_REPO_URL = "https://github.com/carpsesdema/AvA_Kintsugi"  # Your repo URL


# --- Helper Functions ---

def get_current_version(file_path: Path) -> str:
    """Reads the version from setup_core.py"""
    print(f"Reading current version from: {file_path}")
    if not file_path.exists():
        print(f"ERROR: {file_path} not found!")
        sys.exit(1)

    content = file_path.read_text()
    match = re.search(r"version\s*=\s*[\"'](\d+\.\d+\.\d+)[\"']", content)
    if not match:
        print(f"ERROR: Could not find version string in {file_path}")
        sys.exit(1)

    version = match.group(1)
    print(f"Current version is: {version}")
    return version


def update_file_version(file_path: Path, new_version: str):
    """Updates the version string in a given file."""
    try:
        content = file_path.read_text()
        new_content = re.sub(
            r"(version\s*=\s*[\"'])(\d+\.\d+\.\d+)([\"'])",
            f"\\1{new_version}\\3",
            content
        )
        if content != new_content:
            file_path.write_text(new_content)
            print(f"✅ Updated version in {file_path.name}")
        else:
            print(f"⚠️  Could not find version pattern to update in {file_path.name}")
    except Exception as e:
        print(f"❌ ERROR updating {file_path.name}: {e}")


# --- Main Script ---

def main():
    current_version = get_current_version(SETUP_CORE_FILE)
    major, minor, patch = map(int, current_version.split('.'))

    # Ask user for version bump type
    while True:
        bump_type = input(f"Current version is {current_version}. Bump (p)atch, (m)inor, or (j)major? ").lower()
        if bump_type in ['p', 'm', 'j']:
            break
        print("Invalid input. Please enter 'p', 'm', or 'j'.")

    if bump_type == 'p':
        patch += 1
    elif bump_type == 'm':
        minor += 1
        patch = 0
    elif bump_type == 'j':
        major += 1
        minor = 0
        patch = 0

    new_version = f"{major}.{minor}.{patch}"

    print("-" * 30)
    print(f"New version will be: {new_version}")
    confirm = input("Is this correct? (y/n): ").lower()
    if confirm != 'y':
        print("Aborted.")
        sys.exit(0)

    print("\n🚀 Starting release process...")

    # 1. Update setup_core.py
    update_file_version(SETUP_CORE_FILE, new_version)

    # 2. Update version.txt
    try:
        VERSION_TXT_FILE.write_text(new_version)
        print(f"✅ Updated version in {VERSION_TXT_FILE.name}")
    except Exception as e:
        print(f"❌ ERROR updating {VERSION_TXT_FILE.name}: {e}")

    # 3. Update version_manifest.json
    try:
        manifest_data = json.loads(VERSION_MANIFEST_FILE.read_text())
        manifest_data['latest_version'] = new_version
        # Assuming the zip file will be named according to the new version
        manifest_data['download_url'] = f"{GITHUB_REPO_URL}/releases/download/v{new_version}/Avakin_v{new_version}.zip"
        VERSION_MANIFEST_FILE.write_text(json.dumps(manifest_data, indent=2))
        print(f"✅ Updated version and URL in {VERSION_MANIFEST_FILE.name}")
    except Exception as e:
        print(f"❌ ERROR updating {VERSION_MANIFEST_FILE.name}: {e}")

    # 4. Open GitHub releases page to create a new release
    release_url = f"{GITHUB_REPO_URL}/releases/new?tag=v{new_version}&title=Avakin v{new_version}"
    print(f"\nOpening GitHub release page for tag v{new_version}...")
    webbrowser.open(release_url)

    print("\n" + "=" * 50)
    print("✅  Release helper finished!")
    print("Next Steps:")
    print("  1. Your browser has opened to the 'New release' page on GitHub.")
    print(f"  2. The tag name should be pre-filled with 'v{new_version}'.")
    print("  3. After your build finishes, find the zip file in your `dist` folder.")
    print("  4. Drag and drop the zip file onto the release page.")
    print("  5. Write some release notes and click 'Publish release'.")
    print("=" * 50)


if __name__ == "__main__":
    main()