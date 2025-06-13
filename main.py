# kintsugi_ava/main.py
# The clean, simple, and robust entry point for our application.
# V2: Now with a graceful shutdown mechanism.

import sys
import asyncio
import qasync

from PySide6.QtWidgets import QApplication
from core.application import Application

# --- NEW: Asynchronous Main Logic ---
async def main_async_logic():
    """
    This coroutine contains the main asynchronous logic of the application.
    It allows us to await a clean shutdown signal.
    """
    # Create a "Future". This is an object that represents a result that
    # doesn't exist yet. We will wait for this Future to be resolved.
    app_quit_future = asyncio.get_event_loop().create_future()

    # Define the function that will run when the app is about to quit.
    def on_about_to_quit():
        print("[main] Application is about to quit. Resolving quit_future.")
        # When this function is called, it sets the result of our Future.
        app_quit_future.set_result(True)

    # Get the currently running QApplication instance.
    app = QApplication.instance()
    # Connect the application's aboutToQuit signal to our function.
    # Now, when the user closes the window, on_about_to_quit will be called.
    app.aboutToQuit.connect(on_about_to_quit)

    # Create our Application instance as before.
    main_app = Application()
    main_app.show()

    # --- THE KEY CHANGE ---
    # Instead of running the loop forever and hoping it stops,
    # we now explicitly 'await' our Future. This line will pause execution
    # until app_quit_future.set_result() is called.
    await app_quit_future
    print("[main] Quit_future resolved. Exiting main_async_logic.")


# --- Main Entry Point (now much cleaner) ---
if __name__ == "__main__":
    # Create necessary directories first.
    from pathlib import Path
    Path("gui").mkdir(exist_ok=True)
    Path("gui/__init__.py").touch()
    Path("core").mkdir(exist_ok=True)
    Path("core/__init__.py").touch()

    # qasync.run() handles the setup and teardown of the app and event loop.
    # It's a cleaner way to run our async logic.
    qasync.run(main_async_logic())

    # When qasync.run() finishes (because main_async_logic returned),
    # the application will exit cleanly. No need for try/finally or sys.exit.
    print("[main] Application has exited cleanly.")