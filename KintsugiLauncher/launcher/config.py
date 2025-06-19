# KintsugiLauncher/launcher/config.py
import logging
from pathlib import Path

# --- Core Application Details ---
# This is the single source of truth for your application's name and executable.
APP_NAME = "Avakin"
APP_EXECUTABLE_NAME = "main.exe"  # The name of the exe created by your *main app's* build.py

# --- Update Manifest ---
# The URL pointing to your version_manifest.json on GitHub.
# IMPORTANT: Use the "raw" URL.
# Replace 'YOUR_USERNAME' and 'YOUR_REPO' with your actual GitHub details.
MANIFEST_URL = "https://raw.githubusercontent.com/carpsesdema/Avakin/refs/heads/master/version_manifest.json"

# --- Directory Structure ---
# The launcher will assume the main application is installed in a subdirectory
# relative to the launcher's executable. This is a standard and robust pattern.
# For example:
# C:/Avakin/
#  |- Avakin_Launcher.exe  (This launcher)
#  |- main/                      (The directory where the main app lives)
#     |- main.exe
#     |- ... all other app files
# <<< THIS IS THE FIX >>>
# Change this to match the output folder name from your main app's build process.
APP_SUBDIRECTORY_NAME = "main"


# --- Logging Configuration ---
# You can customize logging for the launcher here.
def configure_launcher_logging():
    """Sets up a simple logger for the launcher."""
    log_dir = Path("launcher_logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "launcher.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logging.info("--------------------")
    logging.info("Launcher started.")