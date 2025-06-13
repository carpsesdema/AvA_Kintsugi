# kintsugi_ava/main.py
# V3: Now with global error handling.

import sys
import asyncio
import qasync

from PySide6.QtWidgets import QApplication
from core.application import Application
from utils.exception_handler import setup_exception_hook # <-- Import it

# --- Asynchronous Main Logic ---
async def main_async_logic():
    # ... (this async function remains the same)
    app_quit_future = asyncio.get_event_loop().create_future()
    def on_about_to_quit():
        print("[main] Application is about to quit. Resolving quit_future.")
        app_quit_future.set_result(True)
    app = QApplication.instance()
    app.aboutToQuit.connect(on_about_to_quit)
    main_app = Application()
    main_app.show()
    await app_quit_future
    print("[main] Quit_future resolved. Exiting main_async_logic.")

# --- Main Entry Point ---
if __name__ == "__main__":
    from pathlib import Path
    Path("gui").mkdir(exist_ok=True)
    Path("gui/__init__.py").touch()
    Path("core").mkdir(exist_ok=True)
    Path("core/__init__.py").touch()
    Path("utils").mkdir(exist_ok=True) # <-- Add this for our new directory
    Path("utils/__init__.py").touch() # <-- And this

    # --- SETUP THE EXCEPTION HOOK ---
    # This should be one of the first things we do.
    setup_exception_hook()
    # --- END OF SETUP ---

    qasync.run(main_async_logic())
    print("[main] Application has exited cleanly.")