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
        """
        Initializes the Updater.

        Args:
            manifest_url (str): The URL to the version manifest JSON file.
            app_dir (Path): The directory where the main application is installed.
            current_version (str): The current version of the installed application.
        """
        self.manifest_url = manifest_url
        self.app_dir = app_dir
        self.current_version = current_version
        self.session = requests.Session()
        # Set a user-agent so GitHub doesn't block us!
        self.session.headers.update({'User-Agent': 'KintsugiLauncher/1.0'})

    def check_for_updates(self) -> (bool, dict | None):
        """
        Checks for updates by fetching and parsing the version manifest.

        Returns:
            A tuple (update_available: bool, manifest: dict | None).
            manifest is the fetched manifest if an update is available.
        """
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

            # Using packaging.version.parse for robust version comparison (e.g., handles v1.1.0 vs 1.1.0)
            if parse_version(latest_version_str) > parse_version(self.current_version):
                logger.info("Update available!")
                return True, manifest
            else:
                logger.info("Application is up-to-date.")
                return False, None

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch manifest: {e}")
        except json.JSONDecodeError:
            logger.error("Failed to parse manifest JSON.")
        except Exception as e:
            logger.error(f"An unexpected error occurred during update check: {e}")

        return False, None

    def download_update(self, url: str, progress_callback=None) -> Path | None:
        """
        Downloads the update package.

        Args:
            url (str): The URL to the update zip file.
            progress_callback (callable, optional): A function to call with progress updates.
                                                     It receives (bytes_downloaded, total_bytes).

        Returns:
            The path to the downloaded file, or None on failure.
        """
        logger.info(f"Downloading update from {url}...")
        try:
            download_path = self.app_dir.parent / "update.zip"  # Save it outside the app dir for safety

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
        except Exception as e:
            logger.error(f"An unexpected error occurred during download: {e}")

        return None

    def apply_update(self, zip_path: Path) -> bool:
        """
        Applies the update by extracting the zip file over the application directory.

        Args:
            zip_path (Path): Path to the downloaded update zip file.

        Returns:
            True if the update was applied successfully, False otherwise.
        """
        logger.info(f"Applying update from {zip_path} to {self.app_dir}...")

        # VERY IMPORTANT: Ensure the main app isn't running.
        # This is tricky and often best handled by the launcher UI logic
        # before calling apply_update. For now, we proceed.

        try:
            # For safety, let's backup the old version first
            backup_dir = self.app_dir.parent / f"{self.app_dir.name}_backup_{self.current_version}"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

            shutil.move(str(self.app_dir), str(backup_dir))
            logger.info(f"Old version backed up to {backup_dir}")

            # Extract the new version
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # The zip created by `build.py` might contain a top-level folder (e.g., 'main').
                # We need to handle this to extract correctly.
                # Let's assume the build script zips the *contents* of the dist/main folder.
                self.app_dir.mkdir(parents=True, exist_ok=True)
                zip_ref.extractall(self.app_dir)

            logger.info(f"Update extracted to {self.app_dir}")

            # Clean up the downloaded zip and backup
            zip_path.unlink()
            shutil.rmtree(backup_dir)
            logger.info("Cleaned up temporary update files and backup.")

            return True

        except zipfile.BadZipFile:
            logger.error("Downloaded file is not a valid zip file.")
        except Exception as e:
            logger.error(f"Failed to apply update: {e}")
            # Try to restore the backup if something went wrong
            if not self.app_dir.exists() and backup_dir.exists():
                shutil.move(str(backup_dir), str(self.app_dir))
                logger.info("Restored backup.")

        return False

    @staticmethod
    def launch_application(app_path: Path):
        """
        Launches the main application executable, setting its working directory.

        Args:
            app_path (Path): Path to the application executable.
        """
        if not app_path.exists():
            logger.error(f"Cannot launch application: Executable not found at {app_path}")
            return

        # The working directory should be the directory containing the executable.
        # This is crucial for the application to find its own resources (assets, etc.).
        working_dir = app_path.parent
        logger.info(f"Launching application: {app_path}")
        logger.info(f"Setting working directory to: {working_dir}")
        try:
            subprocess.Popen([str(app_path)], cwd=working_dir)
        except Exception as e:
            logger.error(f"Failed to launch application: {e}")