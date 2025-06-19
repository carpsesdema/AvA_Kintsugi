# src/ava/gui/main_window.py

import asyncio
from PySide6.QtWidgets import QWidget, QHBoxLayout, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from ava.gui.enhanced_sidebar import EnhancedSidebar
from ava.gui.chat_interface import ChatInterface


class MainWindow(QWidget):
    """
    Main window of the application.
    """

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self._closing = False

        # --- Set Window Properties ---
        # This changes the title of the main window
        self.setWindowTitle("Kintsugi AvA")

        # Set window size and minimum size
        self.resize(1400, 900)
        self.setMinimumSize(800, 600)

        # Apply the theme to the whole application (this includes this widget)

        # --- Create Layout ---
        # We use a horizontal layout (HBox) because we want the sidebar
        # on the left and the chat interface on the right
        main_layout = QHBoxLayout(self)
        # These margins create some padding around the edges of the window
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)  # No space between sidebar and chat

        # --- Create Components ---
        # Initialize the sidebar and chat interface with the event bus
        self.sidebar = EnhancedSidebar(event_bus)
        self.chat_interface = ChatInterface(event_bus)

        # --- Add Components to the Layout ---
        # We add the sidebar and the chat interface to our horizontal layout.
        # The numbers (1, 3) are stretch factors. This tells the layout
        # to give the chat interface 3 times as much horizontal space
        # as the sidebar.
        main_layout.addWidget(self.sidebar, 1)
        main_layout.addWidget(self.chat_interface, 3)

    def closeEvent(self, event: QCloseEvent):
        """
        Handle window close event with proper async cleanup.
        This prevents the annoying error popups when closing the app.
        """
        if self._closing:
            event.accept()
            return

        self._closing = True
        print("[MainWindow] Close event triggered - starting graceful shutdown...")

        try:
            # Emit application shutdown event to trigger cleanup
            if self.event_bus:
                self.event_bus.emit("application_shutdown")
        except Exception as e:
            print(f"[MainWindow] Error during shutdown event: {e}")

        # Ignore the event initially to allow async cleanup
        event.ignore()

        # Use a timer to close the application after a short delay
        # This gives the async cleanup time to execute
        QTimer.singleShot(500, lambda: QApplication.instance().quit())