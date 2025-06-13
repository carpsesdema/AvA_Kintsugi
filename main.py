# kintsugi_ava/main.py
# The clean, simple, and robust entry point for our application.

import sys
import asyncio
import qasync  # For running asyncio code within a Qt application

from PySide6.QtWidgets import QApplication
# We will create this MainWindow class in the very next step.
# By importing it, we establish a clean separation of concerns.
from gui.main_window import MainWindow

def main():
    """
    Initializes and runs the Kintsugi-AvA application.
    """
    # 1. Create the core application instance.
    app = QApplication(sys.argv)

    # 2. Set up the asynchronous event loop.
    # This is the foundation for running our AI calls in the background later
    # without freezing the user interface.
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # 3. Create our main window instance.
    # The 'MainWindow' class will be responsible for building the actual GUI.
    # We will pass the event bus to it later. For now, it's simple.
    main_window = MainWindow()
    main_window.show()

    # 4. Run the application's event loop.
    try:
        loop.run_forever()
    finally:
        loop.close()
        sys.exit(0)

# Standard Python entry point guard.
if __name__ == "__main__":
    # Create the necessary folder for our GUI files.
    # This ensures our import `from gui.main_window...` will work.
    from pathlib import Path
    Path("gui").mkdir(exist_ok=True)
    Path("gui/__init__.py").touch() # Makes 'gui' a package
    Path("gui/main_window.py").touch() # Create the file we need next

    main()