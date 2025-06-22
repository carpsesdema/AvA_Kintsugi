import sys
import traceback
import asyncio


def global_exception_hook(exctype, value, tb):
    """
    Catches any uncaught exceptions in the application and logs them to the console.
    All QMessageBox popups have been removed as requested.
    """
    # --- FIX: Ignore asyncio.CancelledError during shutdown ---
    if issubclass(exctype, asyncio.CancelledError):
        print("[ExceptionHandler] Suppressing asyncio.CancelledError during shutdown.")
        return

    # Format the traceback to be readable
    traceback_details = "".join(traceback.format_exception(exctype, value, tb))

    error_message = (
        f"An unexpected error occurred:\n\n"
        f"{str(value)}\n\n"
        f"--- Details ---\n{traceback_details}"
    )

    # Print the error to the console for debugging
    print(error_message, file=sys.stderr)


def setup_exception_hook():
    """Sets the global exception hook."""
    sys.excepthook = global_exception_hook