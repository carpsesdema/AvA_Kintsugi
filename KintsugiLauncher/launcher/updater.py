# launcher/updater.py
import json
import logging
import requests
import zipfile
import shutil
import subprocess
from pathlib import Path
from packaging.version import parse as parse_version

logger = logging.getLogger(__name__)


class Updater:
    """Handles the application update logic."""

    def __init__(self, manifest_url: str, app_dir: Path, current_version: str):
        self.manifest_url = manifest_url
        self.app_dir = app_dir
        self.current_version = current_version
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AvakinLauncher/1.0'})

    def check_for_updates(self) -> (bool, dict | None):
        """Checks for updates by fetching and parsing the version manifest."""
        logger.info(f"Checking for updates from {self.manifest_url}...")
        try:
            response = self.session.get(self.manifest_url, timeout=10)
            response.raise_for_status()
            manifest = response.json()
            latest_version_str = manifest.get("latest_version")
            if not latest_version_str:
                logger.error("Manifest is missing 'latest_version' field.")
                return False, None
            logger.info(f"Current version: {self.current_version}, Latest version: {latest_version_str}")
            if parse_version(latest_version_str) > parse_version(self.current_version):
                logger.info("Update available!")
                return True, manifest
            else:
                logger.info("Application is up-to-date.")
                return False, None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch manifest: {e}")
            return False, None
        except Exception as e:
            logger.error(f"An unexpected error occurred during update check: {e}")
            return False, None

    def download_update(self, url: str, progress_callback=None) -> Path | None:
        """Downloads the update package."""
        logger.info(f"Downloading update from {url}...")
        try:
            download_path = self.app_dir.parent / "update.zip"
            with self.session.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                bytes_downloaded = 0
                with open(download_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(bytes_downloaded, total_size)
            logger.info(f"Update downloaded successfully to {download_path}")
            return download_path
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download update: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during download: {e}")
            return None

    # --- THIS IS THE NEW, BULLETPROOF apply_update METHOD ---
    def apply_update(self, zip_path: Path) -> bool:
        """
        Applies the update by extracting the zip file over the application directory.
        This version is more robust and handles potential errors gracefully.
        """
        logger.info(f"Applying update from {zip_path} to {self.app_dir}...")
        backup_dir = self.app_dir.with_name(f"{self.app_dir.name}_backup")

        # 1. Back up the existing application directory if it exists.
        if self.app_dir.exists():
            logger.info(f"Backing up current version to {backup_dir}...")
            try:
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                shutil.move(str(self.app_dir), str(backup_dir))
            except Exception as e:
                logger.error(f"Failed to back up existing application: {e}")
                return False

        # 2. Extract the new version.
        try:
            self.app_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.app_dir)
            logger.info(f"Update extracted successfully to {self.app_dir}")
        except Exception as e:
            logger.error(f"Failed to extract update zip: {e}")
            # --- Rollback on failure ---
            logger.info("Attempting to restore from backup...")
            if self.app_dir.exists():
                shutil.rmtree(self.app_dir)
            if backup_dir.exists():
                try:
                    shutil.move(str(backup_dir), str(self.app_dir))
                    logger.info("Backup restored successfully.")
                except Exception as restore_e:
                    logger.error(f"FATAL: Could not restore backup: {restore_e}")
            return False

        # 3. Clean up temporary files on success.
        try:
            zip_path.unlink()
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            logger.info("Cleaned up temporary update files and backup.")
        except Exception as e:
            logger.warning(f"Could not clean up all temporary files: {e}")

        return True

    @staticmethod
    def launch_application(app_path: Path):
        """Launches the main application executable."""
        if not app_path.exists():
            logger.error(f"Cannot launch application: Executable not found at {app_path}")
            return
        working_dir = app_path.parent
        logger.info(f"Launching application: {app_path}")
        logger.info(f"Setting working directory to: {working_dir}")
        try:
            subprocess.Popen([str(app_path)], cwd=working_dir)
        except Exception as e:
            logger.error(f"Failed to launch application: {e}")