# kintsugi_ava/utils/exception_handler.py
# A robust, global exception handler for our application.

import sys
import traceback
from PySide6.QtWidgets import QMessageBox


def global_exception_hook(exctype, value, tb):
    """
    Catches any uncaught exceptions in the application, logs them,
    and displays a user-friendly error message.
    """
    # Format the traceback to be readable
    traceback_details = "".join(traceback.format_exception(exctype, value, tb))

    error_message = (
        f"An unexpected error occurred:\n\n"
        f"{str(value)}\n\n"
        f"Please see the details below and consider reporting this issue.\n\n"
        f"--- Details ---\n{traceback_details}"
    )

    # Print the error to the console for debugging
    print(error_message)

    # Show a user-friendly dialog box
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setWindowTitle("Application Error")
    error_box.setText("An unhandled error has occurred.")
    error_box.setInformativeText("The application may need to restart. Please save your work if possible.")
    error_box.setDetailedText(error_message)
    error_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_box.exec()


def setup_exception_hook():
    """Sets the global exception hook."""
    sys.excepthook = global_exception_hook