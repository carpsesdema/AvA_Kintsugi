# kintsugi_ava/main.py
# V3: Now gracefully cancels background tasks on exit.

import sys
import asyncio
import qasync

from PySide6.QtWidgets import QApplication
from core.application import Application
from utils.exception_handler import setup_exception_hook


async def main_async_logic():
    app_quit_future = asyncio.get_event_loop().create_future()
    app = QApplication.instance()

    main_app = Application()  # Application is created here

    def on_about_to_quit():
        print("[main] Application is about to quit.")
        # --- THIS IS THE FIX for the shutdown hang ---
        # Before we stop the loop, we cancel any running AI tasks.
        main_app.cancel_all_tasks()
        app_quit_future.set_result(True)

    app.aboutToQuit.connect(on_about_to_quit)

    main_app.show()
    await app_quit_future
    print("[main] Quit_future resolved. Exiting main_async_logic.")


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

    setup_exception_hook()

    qasync.run(main_async_logic())
    print("[main] Application has exited cleanly.")