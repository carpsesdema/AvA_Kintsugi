# gui/integrated_terminal.py
# The new home for the multi-tab terminal, embedded in the Code Viewer.
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QHBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Signal
import qtawesome as qta

from .components import Colors, Typography, ModernButton
from .terminal_widget import TerminalWidget
from core.project_manager import ProjectManager


class IntegratedTerminal(QWidget):
    """
    A multi-tab terminal manager embedded within the Code Viewer.
    """
    command_entered = Signal(str, int)  # command, session_id

    def __init__(self, event_bus, project_manager: ProjectManager):
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.sessions = {}
        self.next_session_id = 0

        self.setObjectName("integrated_terminal")
        self.setup_ui()
        self._connect_events()

    def setup_ui(self):
        self.setStyleSheet(
            f"#integrated_terminal {{ background-color: {Colors.PRIMARY_BG.name()}; border-top: 1px solid {Colors.BORDER_DEFAULT.name()}; }}")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(5)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        # Custom "new tab" button
        new_tab_btn = QPushButton()
        new_tab_btn.setIcon(qta.icon("fa5s.plus", color=Colors.TEXT_PRIMARY))
        new_tab_btn.setFixedSize(28, 28)
        self.tab_widget.setCornerWidget(new_tab_btn, Qt.Corner.TopRightCorner)
        new_tab_btn.clicked.connect(self.create_new_terminal_tab)

        main_layout.addWidget(self.tab_widget)
        self._add_initial_tab()

    def _add_initial_tab(self):
        # The main, non-closable terminal
        self.create_new_terminal_tab(closable=False)

    def create_new_terminal_tab(self, closable=True):
        session_id = self.next_session_id
        self.next_session_id += 1

        terminal = TerminalWidget(session_id, self.project_manager)
        terminal.command_entered.connect(self.command_entered.emit)

        self.sessions[session_id] = terminal
        index = self.tab_widget.addTab(terminal, f"Terminal {session_id + 1}")
        self.tab_widget.setCurrentIndex(index)
        self.tab_widget.setTabVisible(index, True)

        if not closable:
            self.tab_widget.tabBar().setTabButton(index, self.tab_widget.tabBar().ButtonPosition.RightSide, None)

    def _close_tab(self, index: int):
        widget = self.tab_widget.widget(index)
        if widget and isinstance(widget, TerminalWidget):
            session_id = widget.session_id
            if session_id in self.sessions:
                del self.sessions[session_id]
            self.tab_widget.removeTab(index)
            widget.deleteLater()

    def _connect_events(self):
        self.event_bus.subscribe("terminal_output_received", self._route_output)
        self.event_bus.subscribe("terminal_error_received", self._route_error)
        self.event_bus.subscribe("terminal_success_received", self._route_success)
        self.event_bus.subscribe("terminal_command_finished", self._route_command_finished)

    def _route_output(self, text, session_id):
        if session_id in self.sessions:
            self.sessions[session_id].append_output(text)

    def _route_error(self, text, session_id):
        if session_id in self.sessions:
            self.sessions[session_id].append_error_output(text)

    def _route_success(self, text, session_id):
        if session_id in self.sessions:
            self.sessions[session_id].append_success_output(text)

    def _route_command_finished(self, session_id):
        if session_id in self.sessions:
            self.sessions[session_id].mark_command_finished()

    def set_project_manager(self, project_manager: ProjectManager):
        self.project_manager = project_manager
        for session in self.sessions.values():
            session.set_project_manager(project_manager)