# src/ava/main.py
# FINAL: This is the definitive entry point.

import sys
import asyncio
import qasync
from pathlib import Path

# --- THIS IS THE CRITICAL PATHING SETUP ---
# It determines the root directory for the app and adds it to sys.path
# This ensures all imports and asset lookups work correctly in both
# source-mode and bundled-mode (PyInstaller).
if getattr(sys, 'frozen', False):
    # We are running in a bundle (e.g., from PyInstaller)
    project_root = Path(sys.executable).parent
    # The _MEIPASS directory is where bundled assets are unpacked.
    # We add it to the path so modules like `ava` can be found.
    sys.path.insert(0, str(Path(sys._MEIPASS)))
else:
    # We are running from source.
    # The project root is two levels up from this file (src/ava/main.py -> src -> project_root)
    project_root = Path(__file__).resolve().parent.parent
    # We add the 'src' directory to the path so we can do `from ava...` imports
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon

# Now that the path is correct, we can import the application
from ava.core.application import Application
from ava.utils.exception_handler import setup_exception_hook


async def main_async_logic(root_path: Path):
    """
    The main asynchronous coroutine for the application.
    """
    app = QApplication.instance()
    ava_app = None
    shutdown_future = asyncio.get_event_loop().create_future()
    shutdown_in_progress = False

    async def on_about_to_quit():
        nonlocal shutdown_in_progress
        if shutdown_in_progress:
            return
        shutdown_in_progress = True
        print("[main] Application is about to quit. Starting graceful shutdown...")
        if ava_app:
            try:
                await ava_app.cancel_all_tasks()
            except Exception as e:
                print(f"[main] Error during shutdown tasks: {e}")
        if not shutdown_future.done():
            shutdown_future.set_result(True)
        print("[main] Graceful shutdown complete.")

    app.aboutToQuit.connect(lambda: asyncio.create_task(on_about_to_quit()))

    try:
        ava_app = Application(project_root=root_path)
        await ava_app.initialize_async()
        ava_app.show()
        print("[main] Application ready and displayed.")
        await shutdown_future
    except Exception as e:
        print(f"[main] CRITICAL ERROR during application startup: {e}")
        import traceback
        traceback.print_exc()
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Startup Error", f"Failed to start Avakin.\n\nError: {e}")
        except:
            pass
    finally:
        print("[main] Main async logic has finished. Exiting.")
        QTimer.singleShot(100, app.quit)


if __name__ == "__main__":
    setup_exception_hook()
    app = QApplication(sys.argv)

    app.setApplicationName("Avakin")
    app.setOrganizationName("Avakin")

    # The asset path is now correctly determined based on run mode
    if getattr(sys, 'frozen', False):
        icon_path = Path(sys._MEIPASS) / "ava" / "assets" / "Ava_Icon.ico"
    else:
        icon_path = project_root / "src" / "ava" / "assets" / "Ava_Icon.ico"

    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)
        print(f"[main] Application icon set from: {icon_path}")
    else:
        print(f"[main] WARNING: Application icon not found at {icon_path}")

    qasync.run(main_async_logic(project_root))
    print("[main] Application has exited cleanly.")