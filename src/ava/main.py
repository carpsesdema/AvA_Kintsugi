# src/ava/main.py
# V9: Fixed window closing and plugin discovery in executable

import sys
import asyncio
import qasync
from pathlib import Path

# --- Pathing Setup ---
# This determines the correct project root whether running from source or bundled.
if getattr(sys, 'frozen', False):
    # Running as a bundled executable (PyInstaller)
    project_root = Path(sys.executable).parent
    # The _MEIPASS directory is where bundled assets are unpacked.
    sys.path.insert(0, str(Path(sys._MEIPASS)))
else:
    # Running from source
    project_root = Path(__file__).resolve().parent.parent.parent
    src_path = project_root / 'src'
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# --- Import the main Application class that orchestrates everything ---
from ava.core.application import Application
from ava.utils.exception_handler import setup_exception_hook


async def main_async_logic(root_path: Path):
    """
    The main asynchronous coroutine for the application.
    Now accepts the project root for stable pathing.
    """
    app = QApplication.instance()
    ava_app = None
    shutdown_future = asyncio.get_event_loop().create_future()
    shutdown_in_progress = False

    async def on_about_to_quit():
        """
        This is the single, authoritative handler for shutting down the application.
        It's connected to the Qt 'aboutToQuit' signal for maximum reliability.
        """
        nonlocal shutdown_in_progress
        if shutdown_in_progress:
            return

        shutdown_in_progress = True
        print("[main] Application is about to quit. Starting graceful shutdown...")

        if ava_app:
            try:
                # This one call handles shutting down plugins, services, and tasks.
                await ava_app.cancel_all_tasks()
            except Exception as e:
                print(f"[main] Error during shutdown tasks: {e}")

        # Signal that the async cleanup is complete.
        if not shutdown_future.done():
            shutdown_future.set_result(True)
        print("[main] Graceful shutdown complete.")

    # Connect the Qt signal to our async shutdown handler.
    app.aboutToQuit.connect(lambda: asyncio.create_task(on_about_to_quit()))

    try:
        # Pass the reliable project_root to the Application.
        ava_app = Application(project_root=root_path)

        await ava_app.initialize_async()
        ava_app.show()
        print("[main] Application ready and displayed.")

        # Wait here until on_about_to_quit resolves the future.
        await shutdown_future

    except Exception as e:
        print(f"[main] CRITICAL ERROR during application startup: {e}")
        import traceback
        traceback.print_exc()

        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Startup Error",
                                 f"Failed to start Kintsugi AvA.\n\nError: {e}")
        except:
            pass
    finally:
        print("[main] Main async logic has finished. Exiting.")
        # Force quit after a short delay to ensure everything closes
        QTimer.singleShot(100, app.quit)


if __name__ == "__main__":
    setup_exception_hook()
    app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName("Kintsugi AvA")
    app.setOrganizationName("Kintsugi")

    # Pass the calculated project_root into the main async logic.
    qasync.run(main_async_logic(project_root))

    print("[main] Application has exited cleanly.")