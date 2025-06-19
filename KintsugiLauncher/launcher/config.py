# KintsugiLauncher/launcher/config.py
import logging
from pathlib import Path

# --- Core Application Details ---
APP_NAME = "Avakin"
APP_EXECUTABLE_NAME = "main.exe"

# --- Update Manifest ---
# The URL pointing to your version_manifest.json on GitHub.
# IMPORTANT: Use the "raw" URL.
# --- THIS IS THE FIX ---
# Your main branch is likely named 'main', not 'master'. This is the correct URL.
MANIFEST_URL = "https://raw.githubusercontent.com/carpsesdema/AvA_Kintsugi/refs/heads/master/version_manifest.json"
# --- END OF FIX ---

# --- Directory Structure ---
APP_SUBDIRECTORY_NAME = "main"

# --- Logging Configuration ---
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