# src/ava/main.py
import sys
import asyncio
import qasync
from pathlib import Path

# --- THIS IS THE FIX: ROBUST PATHING LOGIC FOR BUNDLING AND SOURCE ---
if getattr(sys, 'frozen', False):
    # We are running in a bundled environment (e.g., cx_Freeze, PyInstaller).
    # The `data_files_root` is the directory containing the executable.
    # This is the most reliable approach for both cx_Freeze and Nuitka.
    project_root = Path(sys.executable).parent
else:
    # We are running from source.
    # The root of the repository is 3 levels up from this file:
    # <repo_root>/src/ava/main.py
    repo_root = Path(__file__).resolve().parent.parent.parent

    # We need to add the 'src' directory to the path so that imports
    # like 'from src.ava...' or 'from ava...' work correctly.
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # When running from source, the `data_files_root` for our assets,
    # configs, etc., is the 'src' directory itself, since our other
    # modules will look for them relative to this (e.g., src/ava/assets).
    project_root = src_path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon

from src.ava.core.application import Application
from src.ava.utils.exception_handler import setup_exception_hook


async def main_async_logic(app_instance, root_path: Path):
    """
    The main asynchronous coroutine for the application.
    """
    ava_app = None
    shutdown_future = asyncio.get_event_loop().create_future()
    shutdown_in_progress = False

    async def on_about_to_quit():
        nonlocal shutdown_in_progress
        if shutdown_in_progress: return
        shutdown_in_progress = True
        print("[main] Application is about to quit. Starting graceful shutdown...")
        if ava_app:
            try:
                await ava_app.cancel_all_tasks()
            except Exception as e:
                print(f"[main] Error during shutdown tasks: {e}")
        if not shutdown_future.done(): shutdown_future.set_result(True)
        print("[main] Graceful shutdown complete.")

    app_instance.aboutToQuit.connect(lambda: asyncio.create_task(on_about_to_quit()))

    try:
        # Pass the correctly determined project_root to the Application
        ava_app = Application(project_root=root_path)
        await ava_app.initialize_async()
        ava_app.show()
        print("[main] Application ready and displayed.")
        await shutdown_future
    except Exception as e:
        print(f"[main] CRITICAL ERROR during application startup: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Startup Error", f"Failed to start Avakin.\n\nError: {e}")
        except Exception as msg_e:
            print(f"Could not show error message box: {msg_e}", file=sys.stderr)
    finally:
        print("[main] Main async logic has finished. Exiting.")
        QTimer.singleShot(100, app_instance.quit)


if __name__ == "__main__":
    setup_exception_hook()
    app = QApplication(sys.argv)

    app.setApplicationName("Kintsugi AvA")
    app.setOrganizationName("Kintsugi AvA")

    # Use the project_root determined at the start to find the icon
    icon_path = project_root / "ava" / "assets" / "Ava_Icon.ico"

    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)
        print(f"[main] Application icon set from: {icon_path}")
    else:
        print(f"[main] WARNING: Application icon not found at {icon_path}")

    # Pass the determined project_root to the main async logic
    qasync.run(main_async_logic(app, project_root))
    print("[main] Application has exited cleanly.")