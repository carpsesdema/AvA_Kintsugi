# build.py
import subprocess
import shutil
import platform
import argparse
import os
from pathlib import Path

# --- Project Structure ---
PROJECT_ROOT = Path(__file__).parent.resolve()
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
SRC_DIR = PROJECT_ROOT / "src"
LAUNCHER_DIR = PROJECT_ROOT / "KintsugiLauncher"

# --- Nuitka Build Configuration ---
# We use --standalone to create a folder with all dependencies.
# This is more reliable than --onefile for complex apps with many assets.

LAUNCHER_BUILD_CONFIG = {
    "script_path": LAUNCHER_DIR / "main.py",
    "output_dir_name": "AvakinLauncher",
    "icon_path": LAUNCHER_DIR / "launcher" / "assets" / "Launcher_Icon.ico",
    "plugins": ["pyside6"],
    "data_dirs": {
        LAUNCHER_DIR / "launcher" / "assets": "assets"
    },
    "packages": [],
    # --- THIS IS THE FIX ---
    # We need to tell Nuitka where to find the 'launcher' package during
    # the build, just like you did for the 'ava' package in the main app!
    "add_to_pythonpath": [
        LAUNCHER_DIR
    ],
    # --- END OF FIX ---
}

MAIN_APP_BUILD_CONFIG = {
    "script_path": SRC_DIR / "ava" / "main.py",
    "output_dir_name": "Avakin",
    "icon_path": SRC_DIR / "ava" / "assets" / "Ava_Icon.ico",
    "plugins": ["pyside6"],
    "disable_plugins": ["transformers"],
    "data_dirs": {
        SRC_DIR / "ava" / "assets": "ava/assets",
        SRC_DIR / "ava" / "config": "ava/config",
        SRC_DIR / "ava" / "core" / "plugins" / "examples": "ava/core/plugins/examples",
    },
    "packages": [
        "ava",
        "qtawesome",
        "pygments.styles",
        "transformers",
        "sentence_transformers",
        "torch", # Explicitly include torch
    ],
    "add_to_pythonpath": [
        SRC_DIR
    ],
    # --- THIS IS THE ROBUST FIX ---
    # We are telling Nuitka to avoid looking inside these specific,
    # problematic modules within the transformers library. This prevents
    # the relative import assertion error.
    "nofollow_imports": [
        "transformers.models"
    ],
    # --- END OF FIX ---
}


def run_command(command, cwd, env=None):
    """Runs a command and prints its output in real-time."""
    print(f"\n🚀 Running command: {' '.join(command)}")
    print(f"   In directory: {cwd}\n")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        rc = process.poll()
        if rc != 0:
            print(f"\n❌ Command failed with return code: {rc}")
            return False
        print(f"\n✅ Command finished successfully.")
        return True
    except Exception as e:
        print(f"\n❌ An exception occurred: {e}")
        return False


def build_with_nuitka(config: dict):
    """Constructs and runs the Nuitka command based on a config dictionary."""
    output_path = DIST_DIR / config["output_dir_name"]

    command = [
        "python",
        "-m",
        "nuitka",
        "--standalone",
        f"--output-dir={output_path}",
        str(config["script_path"]),
    ]

    env = None
    if config.get("add_to_pythonpath"):
        env = os.environ.copy()
        paths_to_add = [str(p.resolve()) for p in config["add_to_pythonpath"]]
        current_pythonpath = env.get("PYTHONPATH", "")

        new_pythonpath_parts = paths_to_add
        if current_pythonpath:
            new_pythonpath_parts.append(current_pythonpath)

        env["PYTHONPATH"] = os.pathsep.join(new_pythonpath_parts)
        print(f"   Modified PYTHONPATH for build: {env['PYTHONPATH']}")

    # Add plugins
    for plugin in config.get("plugins", []):
        command.append(f"--enable-plugin={plugin}")

    for plugin in config.get("disable_plugins", []):
        command.append(f"--disable-plugin={plugin}")

    # Add data directories
    for src, dest in config.get("data_dirs", {}).items():
        if src.exists():
            command.append(f"--include-data-dir={src}={dest}")
        else:
            print(f"   Skipping non-existent data directory: {src}")

    # Add packages
    for package in config.get("packages", []):
        command.append(f"--include-package={package}")

    # --- THIS IS THE FIX ---
    # Add the command to not follow imports into problematic modules.
    for module_to_skip in config.get("nofollow_imports", []):
        command.append(f"--nofollow-import-to={module_to_skip}")
    # --- END OF FIX ---

    # Add Windows-specific options
    if platform.system() == "Windows":
        command.append("--windows-console-mode=disable")
        if config.get("icon_path") and config["icon_path"].exists():
            command.append(f'--windows-icon-from-ico={config["icon_path"]}')

    return run_command(command, cwd=PROJECT_ROOT, env=env)


def clean():
    """Removes previous build and distribution artifacts."""
    print("--- Cleaning up old artifacts ---")
    if BUILD_DIR.exists():
        print(f"Removing build directory: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        print(f"Removing dist directory: {DIST_DIR}")
        shutil.rmtree(DIST_DIR)
    print("Cleanup complete.")


def main():
    parser = argparse.ArgumentParser(description="Avakin Build System using Nuitka")
    parser.add_argument("--launcher", action="store_true", help="Build only the launcher.")
    parser.add_argument("--main", action="store_true", help="Build only the main application.")
    parser.add_argument("--all", action="store_true", help="Build both the launcher and the main application.")
    parser.add_argument("--clean", action="store_true", help="Clean up previous build artifacts before building.")
    args = parser.parse_args()

    if not any([args.launcher, args.main, args.all]):
        parser.print_help()
        return

    if args.clean:
        clean()

    if args.launcher or args.all:
        print("\n--- Building Avakin Launcher ---")
        if not build_with_nuitka(LAUNCHER_BUILD_CONFIG):
            print("\n❌ Launcher build failed.")
            return

    if args.main or args.all:
        print("\n--- Building Main Avakin Application ---")
        if not build_with_nuitka(MAIN_APP_BUILD_CONFIG):
            print("\n❌ Main application build failed.")
            return

    print("\n🎉🎉🎉 Build process completed! 🎉🎉🎉")
    print(f"Your compiled application(s) can be found in: {DIST_DIR.resolve()}")


if __name__ == "__main__":
    main()