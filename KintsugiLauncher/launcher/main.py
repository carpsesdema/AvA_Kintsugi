# launcher/main.py

import sys
from pathlib import Path

# --- This makes it runnable from source and for PyInstaller ---
# Add the parent directory (KintsugiLauncher) to the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
import qasync  # We'll use qasync for a smooth event loop, just like in your main app

from launcher.gui import LauncherWindow
from launcher.updater import Updater
from launcher.config import (
    MANIFEST_URL,
    APP_SUBDIRECTORY_NAME,
    APP_EXECUTABLE_NAME,
    configure_launcher_logging
)


def get_current_version(app_dir: Path) -> str:
    """Reads the version from the version.txt file."""
    version_file = app_dir / "version.txt"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"  # Default version if not found


def main():
    """The main entry point for the launcher."""
    # 1. Configure logging
    configure_launcher_logging()

    # 2. Set up the Qt Application
    app = QApplication(sys.argv)

    # 3. Determine application paths
    if getattr(sys, 'frozen', False):
        # We are running in a bundle (e.g., from PyInstaller)
        launcher_dir = Path(sys.executable).parent
    else:
        # We are running from source
        launcher_dir = Path(__file__).resolve().parent.parent

    app_install_dir = launcher_dir / APP_SUBDIRECTORY_NAME
    app_exe_path = app_install_dir / APP_EXECUTABLE_NAME

    # Ensure the app directory exists
    app_install_dir.mkdir(exist_ok=True)

    # 4. Get current installed version
    current_version = get_current_version(app_install_dir)

    # 5. Initialize the core components
    updater = Updater(
        manifest_url=MANIFEST_URL,
        app_dir=app_install_dir,
        current_version=current_version
    )

    window = LauncherWindow(updater, str(app_exe_path))
    window.show()

    # 6. Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()