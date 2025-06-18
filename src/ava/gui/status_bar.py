# kintsugi_ava/gui/status_bar.py
# A dedicated, event-driven status bar for the Code Viewer IDE.

from PySide6.QtWidgets import QStatusBar, QLabel
from PySide6.QtCore import Qt
import qtawesome as qta

from .components import Colors, Typography


class StatusBar(QStatusBar):
    """
    An event-driven status bar that displays key information like Git branch
    and RAG service status.
    """

    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setObjectName("StatusBar")
        self.setStyleSheet(f"""
            #StatusBar {{
                background-color: {Colors.SECONDARY_BG.name()};
                color: {Colors.TEXT_SECONDARY.name()};
                border-top: 1px solid {Colors.BORDER_DEFAULT.name()};
                padding: 2px 8px;
            }}
            QLabel {{
                color: {Colors.TEXT_SECONDARY.name()};
                padding: 0 5px;
            }}
        """)
        self.setFont(Typography.body())

        # -- Git Branch --
        self.branch_icon = QLabel()
        self.branch_icon.setPixmap(qta.icon("fa5s.code-branch", color=Colors.TEXT_SECONDARY.name()).pixmap(12, 12))
        self.branch_label = QLabel("(no branch)")
        self.addPermanentWidget(self.branch_icon)
        self.addPermanentWidget(self.branch_label)

        # -- Separator --
        sep1 = QLabel("|")
        self.addPermanentWidget(sep1)

        # -- RAG Status --
        self.rag_icon = QLabel()
        self.rag_icon.setPixmap(qta.icon("fa5s.brain", color=Colors.TEXT_SECONDARY.name()).pixmap(12, 12))
        self.rag_label = QLabel("RAG: Initializing...")
        self.addPermanentWidget(self.rag_icon)
        self.addPermanentWidget(self.rag_label)

        self._connect_events()

    def _connect_events(self):
        self.event_bus.subscribe("branch_updated", self.on_branch_updated)
        self.event_bus.subscribe("log_message_received", self.on_log_message)

    def on_branch_updated(self, branch_name: str):
        """Updates the Git branch display."""
        self.branch_label.setText(branch_name)

    def on_log_message(self, source: str, msg_type: str, content: str):
        """Listens for RAG manager logs to update its status."""
        if source == "RAGManager":
            # Set the label text
            self.rag_label.setText(content)

            # Change icon color based on status
            color = Colors.TEXT_SECONDARY.name()
            if msg_type == "success":
                color = Colors.ACCENT_GREEN.name()
            elif msg_type == "error":
                color = Colors.ACCENT_RED.name()
            elif msg_type == "info":
                if "ingest" in content.lower() or "scan" in content.lower():
                    color = Colors.ACCENT_BLUE.name()

            self.rag_icon.setPixmap(qta.icon("fa5s.brain", color=color).pixmap(12, 12))