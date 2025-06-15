# kintsugi_ava/main.py
# V6: Updated to handle async plugin initialization

import sys
import asyncio
import qasync

from PySide6.QtWidgets import QApplication

# --- Import the main Application class that orchestrates everything ---
from core.application import Application
# --- END IMPORT ---

from utils.exception_handler import setup_exception_hook


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
    from pathlib import Path

    # Ensure package directories exist (for running from root)
    Path("gui").mkdir(exist_ok=True)
    Path("gui/__init__.py").touch()
    Path("core").mkdir(exist_ok=True)
    Path("core/__init__.py").touch()
    Path("utils").mkdir(exist_ok=True)
    Path("utils/__init__.py").touch()
    Path("services").mkdir(exist_ok=True)
    Path("services/__init__.py").touch()
    Path("prompts").mkdir(exist_ok=True)
    Path("prompts/__init__.py").touch()

    # Ensure plugin directories exist
    Path("plugins").mkdir(exist_ok=True)
    Path("plugins/__init__.py").touch()
    Path("core/plugins/examples").mkdir(exist_ok=True, parents=True)
    Path("core/plugins/examples/__init__.py").touch()

    # Set up global error handling first
    setup_exception_hook()

    # Initialize the QApplication. This is necessary before any widgets are created.
    app = QApplication(sys.argv)

    # Use qasync.run to manage the lifecycle of the asyncio event loop
    # and integrate it with Qt's event loop.
    qasync.run(main_async_logic())

    print("[main] Application has exited cleanly.")