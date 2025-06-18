# launcher/gui.py

import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QProgressBar, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QIcon, QPalette

# Assuming we have a similar components file for the launcher
# We'll need to create this later!
from .components import Colors, Typography

from .updater import Updater

logger = logging.getLogger(__name__)


class UpdateWorker(QThread):
    """
    A dedicated QThread to run the update check and download process
    without freezing the main UI thread.
    """
    # Signals to communicate with the main UI thread
    status_changed = Signal(str)
    progress_updated = Signal(int)
    update_info_ready = Signal(str)
    update_complete = Signal(bool, str)  # success, new_version
    no_update_found = Signal()
    launch_ready = Signal()

    def __init__(self, updater: Updater):
        super().__init__()
        self.updater = updater

    def run(self):
        """The main logic executed in the new thread."""
        self.status_changed.emit("Checking for updates...")

        update_available, manifest = self.updater.check_for_updates()

        if not update_available:
            self.no_update_found.emit()
            self.launch_ready.emit()
            return

        if manifest:
            notes = manifest.get("release_notes", "No release notes available.")
            self.update_info_ready.emit(f"Update to v{manifest['latest_version']} found!\n\nRelease Notes:\n{notes}")

            self.status_changed.emit("Downloading update...")
            download_url = manifest.get("download_url")

            def progress_hook(bytes_downloaded, total_bytes):
                percentage = int((bytes_downloaded / total_bytes) * 100)
                self.progress_updated.emit(percentage)

            download_path = self.updater.download_update(download_url, progress_hook)

            if download_path:
                self.status_changed.emit("Applying update...")
                self.progress_updated.emit(100)  # Show completion

                success = self.updater.apply_update(download_path)
                if success:
                    self.update_complete.emit(True, manifest['latest_version'])
                    self.launch_ready.emit()
                else:
                    self.status_changed.emit("Failed to apply update. Please check logs.")
                    self.update_complete.emit(False, "")
            else:
                self.status_changed.emit("Failed to download update. Please check logs.")
                self.update_complete.emit(False, "")


class LauncherWindow(QMainWindow):
    """The main window for the application launcher."""

    def __init__(self, updater: Updater, app_exe_path: str):
        super().__init__()
        self.updater = updater
        self.app_exe_path = app_exe_path

        self.setWindowTitle("Kintsugi AvA Launcher")
        self.setFixedSize(450, 300)

        # --- Window Setup ---
        self.setup_window_style()
        self.setup_ui()

        # --- Worker Thread ---
        self.worker = UpdateWorker(self.updater)
        self.setup_worker_connections()
        self.worker.start()

    def setup_window_style(self):
        """Set up the window's appearance."""
        # --- FIX: We will need an icon for the launcher too ---
        # try:
        #     with resources.files('launcher.assets').joinpath('Launcher_Icon.ico') as icon_path:
        #         self.setWindowIcon(QIcon(str(icon_path)))
        # except Exception as e:
        #     logger.warning(f"Could not load launcher window icon: {e}")

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, Colors.PRIMARY_BG)
        self.setPalette(palette)

    def setup_ui(self):
        """Create and arrange the UI widgets."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title Label
        title_label = QLabel("Kintsugi AvA")
        title_label.setFont(Typography.heading(24))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")

        # Status Label
        self.status_label = QLabel("Initializing...")
        self.status_label.setFont(Typography.body(14))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 4px;
                background-color: {Colors.SECONDARY_BG.name()};
            }}
            QProgressBar::chunk {{
                background-color: {Colors.ACCENT_BLUE.name()};
                border-radius: 3px;
            }}
        """)
        self.progress_bar.hide()  # Hidden until a download starts

        # Release Notes / Info Box
        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.SECONDARY_BG.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY.name()};
                font-size: 12px;
                padding: 10px;
            }}
        """)
        self.info_box.hide()  # Hidden until update info is ready

        layout.addStretch()
        layout.addWidget(title_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.info_box)
        layout.addStretch()

    def setup_worker_connections(self):
        """Connect signals from the worker thread to UI slots."""
        self.worker.status_changed.connect(self.on_status_changed)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.update_info_ready.connect(self.on_update_info_ready)
        self.worker.update_complete.connect(self.on_update_complete)
        self.worker.no_update_found.connect(self.on_no_update_found)
        self.worker.launch_ready.connect(self.on_launch_ready)

    @Slot(str)
    def on_status_changed(self, status: str):
        self.status_label.setText(status)
        logger.info(f"Launcher Status: {status}")

    @Slot(int)
    def on_progress_updated(self, percentage: int):
        self.progress_bar.show()
        self.progress_bar.setValue(percentage)

    @Slot(str)
    def on_update_info_ready(self, info: str):
        self.info_box.setText(info)
        self.info_box.show()

    @Slot(bool, str)
    def on_update_complete(self, success: bool, new_version: str):
        if success:
            # We need to save the new version number locally
            try:
                version_file = self.updater.app_dir / "version.txt"
                version_file.write_text(new_version)
                logger.info(f"Updated local version file to {new_version}")
            except Exception as e:
                logger.error(f"Could not write new version to file: {e}")
        else:
            self.status_label.setText("Update failed. Please restart the launcher.")
            self.progress_bar.hide()

    @Slot()
    def on_no_update_found(self):
        self.status_label.setText("Your application is up to date!")

    @Slot()
    def on_launch_ready(self):
        self.status_label.setText("Launching application...")
        self.updater.launch_application(self.app_exe_path)
        # Close the launcher a moment after launching the app
        QTimer.singleShot(1000, self.close)