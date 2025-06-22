# src/ava/gui/main_window.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent

from src.ava.core.event_bus import EventBus
from src.ava.gui.enhanced_sidebar import EnhancedSidebar
from src.ava.gui.chat_interface import ChatInterface


class MainWindow(QWidget):
    """
    Main window of the application, holding the sidebar and chat interface.
    """

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self._closing = False

        # --- Window Properties ---
        self.setWindowTitle("AvaKin")
        self.resize(1400, 900)
        self.setMinimumSize(800, 600)

        # --- Layout ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Components ---
        self.sidebar = EnhancedSidebar(event_bus)
        self.chat_interface = ChatInterface(event_bus)

        # --- Add Components to Layout ---
        # The numbers (1, 3) are stretch factors.
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
            if self.event_bus:
                self.event_bus.emit("application_shutdown")
        except Exception as e:
            print(f"[MainWindow] Error during shutdown event: {e}")

        # Ignore the event initially to allow async cleanup
        event.ignore()

        # Use a timer to close the application after a short delay
        # This gives the async cleanup time to execute
        QTimer.singleShot(500, QApplication.instance().quit)