# kintsugi_ava/main.py
# V4: A more robust shutdown sequence to prevent race conditions.

import sys
import asyncio
import qasync

from PySide6.QtWidgets import QApplication
from core.application import Application
from utils.exception_handler import setup_exception_hook


async def main_async_logic():
    """
    The main asynchronous coroutine for the application.
    This version includes a more robust shutdown mechanism.
    """
    app = QApplication.instance()

    # This will hold our main application logic instance
    ava_app = None

    # Create a Future to signal when it's safe to exit
    shutdown_future = asyncio.get_event_loop().create_future()

    async def on_about_to_quit():
        """
        This function is called right before the app quits.
        It now properly handles task cancellation.
        """
        if ava_app:
            print("[main] Application is about to quit. Cancelling background tasks...")
            # Cancel all running AI tasks
            await ava_app.cancel_all_tasks()

        # Now that tasks are cancelled, signal that it's safe to exit
        if not shutdown_future.done():
            shutdown_future.set_result(True)

    app.aboutToQuit.connect(lambda: asyncio.create_task(on_about_to_quit()))

    try:
        # Create and show the application
        ava_app = Application()
        ava_app.show()

        # Wait here until the shutdown_future is resolved
        await shutdown_future

    finally:
        print("[main] Shutdown sequence complete. Exiting.")


if __name__ == "__main__":
    from pathlib import Path

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

    # Set up global error handling first
    setup_exception_hook()

    # Use qasync.run to manage the lifecycle
    # This will also ensure the loop is properly closed
    qasync.run(main_async_logic())

    print("[main] Application has exited cleanly.")