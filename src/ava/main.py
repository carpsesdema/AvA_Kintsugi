# src/ava/main.py
# V7: Centralized path configuration for robust execution and building.

import sys
import asyncio
import qasync
from pathlib import Path

# --- THIS IS THE FIX ---
# The path manipulation logic is now separated for running from source vs. running as a
# bundled executable. This is the key to making the PyInstaller build work.

if getattr(sys, 'frozen', False):
    # This block runs when the application is bundled by PyInstaller.
    # We add the temporary _MEIPASS directory to the path, which is where
    # PyInstaller unpacks bundled assets (like icons).
    meipass_path = Path(sys._MEIPASS)
    sys.path.insert(0, str(meipass_path))
else:
    # This block runs when you run the script directly from your IDE.
    # It adds the 'src' directory to the path so that imports like
    # 'from ava.core...' are found correctly.
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root / 'src'))
# --- END OF FIX ---


from PySide6.QtWidgets import QApplication

# --- Import the main Application class that orchestrates everything ---
# These imports now work correctly in both environments.
from ava.core.application import Application
from ava.utils.exception_handler import setup_exception_hook


async def main_async_logic():
    """
    The main asynchronous coroutine for the application.
    Now includes async plugin initialization.
    """
    # qasync ensures QApplication.instance() exists
    app = QApplication.instance()

    # This will hold our main application logic instance
    ava_app = None

    # Create a Future to signal when it's safe to exit the event loop
    shutdown_future = asyncio.get_event_loop().create_future()

    async def on_about_to_quit():
        """
        This function is called right before the app quits.
        It properly handles task and plugin shutdown.
        """
        if ava_app:
            print("[main] Application is about to quit. Shutting down plugins and tasks...")
            # Cancel all running tasks and shutdown plugins managed by the Application class
            await ava_app.cancel_all_tasks()

        # Now that everything is shut down, signal that it's safe to exit
        if not shutdown_future.done():
            shutdown_future.set_result(True)

    # Connect the signal to our async shutdown handler
    app.aboutToQuit.connect(lambda: asyncio.create_task(on_about_to_quit()))

    try:
        # Create the application instance
        ava_app = Application()

        # Perform async initialization (plugins, etc.)
        print("[main] Starting async initialization...")
        await ava_app.initialize_async()

        # Show the application
        ava_app.show()

        print("[main] Application ready and displayed")

        # Wait here until the shutdown_future is resolved by on_about_to_quit
        await shutdown_future

    except Exception as e:
        print(f"[main] CRITICAL ERROR during application startup: {e}")
        import traceback
        traceback.print_exc()

        # Try to show an error message if possible
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Startup Error",
                                 f"Failed to start Kintsugi AvA.\n\nError: {e}")
        except:
            pass

    finally:
        print("[main] Shutdown sequence complete. Exiting.")


if __name__ == "__main__":
    # Removed the old path manipulation/creation code.
    # It is no longer needed and was causing issues.

    # Set up global error handling first
    setup_exception_hook()

    # Initialize the QApplication. This is necessary before any widgets are created.
    app = QApplication(sys.argv)

    # Use qasync.run to manage the lifecycle of the asyncio event loop
    # and integrate it with Qt's event loop.
    qasync.run(main_async_logic())

    print("[main] Application has exited cleanly.")