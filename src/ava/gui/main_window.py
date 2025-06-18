# src/ava/gui/main_window.py
# The main window class. Its single responsibility is to hold and lay out
# the primary UI components like the sidebar and the chat interface.

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout
from PySide6.QtGui import QIcon
from importlib import resources

from .enhanced_sidebar import EnhancedSidebar
from .chat_interface import ChatInterface
from ava.core.event_bus import EventBus


class MainWindow(QMainWindow):
    """
    The main application window. It acts as a container for the primary
    UI components. It adheres to SRP by only managing the main window's
    layout and existence. It knows nothing about AI or business logic.
    """

    def __init__(self, event_bus: EventBus):
        """
        The __init__ method now accepts the event_bus, which it will pass
        down to its child components that need to communicate.
        """
        super().__init__()

        # --- Basic Window Configuration ---
        self.setWindowTitle("Kintsugi AvA - The Unbreakable Foundation")
        self.setGeometry(100, 100, 1200, 800)  # x, y, width, height

        # --- THIS IS THE FIX: Set the Window Icon ---
        try:
            # Correctly locate the icon within the 'ava' package's 'assets' sub-folder
            # This method is robust and works even when the app is packaged.
            with resources.files('ava.assets').joinpath('Ava_Icon.ico') as icon_path:
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            print(f"[MainWindow] Could not load window icon: {e}")
        # --- END OF FIX ---

        # --- Main Layout ---
        # A central widget is required for a QMainWindow.
        # We use a simple QWidget with a horizontal layout (QHBoxLayout).
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # No padding around the edges
        main_layout.setSpacing(0)  # No space between sidebar and chat

        # --- Instantiate UI Components ---
        # We create instances of our sidebar and chat interface, passing the
        # event bus to them so they can communicate with the rest of the app.
        self.sidebar = EnhancedSidebar(event_bus)
        self.chat_interface = ChatInterface(event_bus)

        # --- Add Components to the Layout ---
        # We add the sidebar and the chat interface to our horizontal layout.
        # The numbers (1, 3) are stretch factors. This tells the layout
        # to give the chat interface 3 times as much horizontal space
        # as the sidebar.
        main_layout.addWidget(self.sidebar, 1)
        main_layout.addWidget(self.chat_interface, 3)