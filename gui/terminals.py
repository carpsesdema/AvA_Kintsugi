# kintsugi_ava/gui/terminals.py
# Multi-terminal window with virtual environment integration

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMenuBar, QMenu, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont
import qtawesome as qta

from .terminal_widget import TerminalWidget
from .components import Colors, Typography


class TerminalsWindow(QMainWindow):
    """
    Multi-terminal window that manages multiple terminal sessions
    with proper virtual environment integration.
    """

    terminal_command_entered = Signal(str, int)  # command, session_id

    def __init__(self, event_bus, project_manager=None):
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.terminal_sessions = {}
        self.next_session_id = 0

        self.setWindowTitle("Kintsugi AvA - Terminals")
        self.setGeometry(300, 300, 1000, 700)

        self.setup_ui()
        self.setup_menu_bar()
        self.setup_status_bar()

        # Create the first terminal
        self.create_new_terminal()

    def setup_ui(self):
        """Set up the main UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.setup_header(main_layout)

        # Tab widget for multiple terminals
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_terminal_tab)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                background-color: {Colors.SECONDARY_BG.name()};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background-color: {Colors.ELEVATED_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                padding: 8px 15px;
                margin: 2px;
                border-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {Colors.ACCENT_BLUE.name()};
            }}
            QTabBar::tab:hover {{
                background-color: {Colors.ACCENT_GREEN.name()};
            }}
        """)

        main_layout.addWidget(self.tab_widget, 1)

        # Style the window
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Colors.PRIMARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
            }}
        """)

    def setup_header(self, main_layout):
        """Set up the header with title and controls."""
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel("Terminal Sessions")
        title_label.setFont(Typography.get_font(14, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # New terminal button
        self.new_terminal_btn = QPushButton("New Terminal")
        self.new_terminal_btn.setIcon(qta.icon("fa5s.plus", color=Colors.TEXT_PRIMARY.name()))
        self.new_terminal_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_BLUE.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #4f8cc9;
            }}
        """)
        self.new_terminal_btn.clicked.connect(self.create_new_terminal)
        header_layout.addWidget(self.new_terminal_btn)

        # Clear all terminals button
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setIcon(qta.icon("fa5s.broom", color=Colors.TEXT_PRIMARY.name()))
        self.clear_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SECONDARY_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ELEVATED_BG.name()};
            }}
        """)
        self.clear_all_btn.clicked.connect(self.clear_all_terminals)
        header_layout.addWidget(self.clear_all_btn)

        main_layout.addLayout(header_layout)

    def setup_menu_bar(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # Terminal menu
        terminal_menu = menubar.addMenu("Terminal")

        new_action = QAction("New Terminal", self)
        new_action.setShortcut("Ctrl+T")
        new_action.triggered.connect(self.create_new_terminal)
        terminal_menu.addAction(new_action)

        close_action = QAction("Close Current Terminal", self)
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(self.close_current_terminal)
        terminal_menu.addAction(close_action)

        clear_action = QAction("Clear Current Terminal", self)
        clear_action.setShortcut("Ctrl+L")
        clear_action.triggered.connect(self.clear_current_terminal)
        terminal_menu.addAction(clear_action)

        terminal_menu.addSeparator()

        clear_all_action = QAction("Clear All Terminals", self)
        clear_all_action.triggered.connect(self.clear_all_terminals)
        terminal_menu.addAction(clear_all_action)

        # View menu
        view_menu = menubar.addMenu("View")

        next_tab_action = QAction("Next Terminal", self)
        next_tab_action.setShortcut("Ctrl+Tab")
        next_tab_action.triggered.connect(self.next_terminal)
        view_menu.addAction(next_tab_action)

        prev_tab_action = QAction("Previous Terminal", self)
        prev_tab_action.setShortcut("Ctrl+Shift+Tab")
        prev_tab_action.triggered.connect(self.previous_terminal)
        view_menu.addAction(prev_tab_action)

    def setup_status_bar(self):
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {Colors.SECONDARY_BG.name()};
                color: {Colors.TEXT_SECONDARY.name()};
                border-top: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)
        self.update_status_bar()

    def create_new_terminal(self):
        """Create a new terminal session."""
        session_id = self.next_session_id
        self.next_session_id += 1

        # Create the terminal widget
        terminal_widget = TerminalWidget(self.event_bus, session_id, self.project_manager)

        # Connect signals
        terminal_widget.command_entered.connect(self.handle_terminal_command)

        # Store session info
        self.terminal_sessions[session_id] = {
            "widget": terminal_widget,
            "created_at": self._get_current_time()
        }

        # Add to tab widget
        tab_title = f"Terminal {session_id + 1}"
        self.tab_widget.addTab(terminal_widget, tab_title)
        self.tab_widget.setCurrentWidget(terminal_widget)

        self.update_status_bar()
        print(f"[TerminalsWindow] Created new terminal session {session_id}")

    def close_terminal_tab(self, index):
        """Close a specific terminal tab."""
        if self.tab_widget.count() <= 1:
            QMessageBox.warning(self, "Warning", "Cannot close the last terminal.")
            return

        widget = self.tab_widget.widget(index)
        if isinstance(widget, TerminalWidget):
            session_id = widget.session_id

            # Remove from sessions
            if session_id in self.terminal_sessions:
                del self.terminal_sessions[session_id]

            # Remove tab
            self.tab_widget.removeTab(index)

            # Clean up widget
            widget.deleteLater()

            self.update_status_bar()
            print(f"[TerminalsWindow] Closed terminal session {session_id}")

    def close_current_terminal(self):
        """Close the currently active terminal."""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.close_terminal_tab(current_index)

    def clear_current_terminal(self):
        """Clear the current terminal's output."""
        current_widget = self.tab_widget.currentWidget()
        if isinstance(current_widget, TerminalWidget):
            current_widget.clear_output()

    def clear_all_terminals(self):
        """Clear all terminal outputs."""
        for session_info in self.terminal_sessions.values():
            session_info["widget"].clear_output()

    def next_terminal(self):
        """Switch to the next terminal tab."""
        current_index = self.tab_widget.currentIndex()
        next_index = (current_index + 1) % self.tab_widget.count()
        self.tab_widget.setCurrentIndex(next_index)

    def previous_terminal(self):
        """Switch to the previous terminal tab."""
        current_index = self.tab_widget.currentIndex()
        prev_index = (current_index - 1) % self.tab_widget.count()
        self.tab_widget.setCurrentIndex(prev_index)

    def handle_terminal_command(self, command: str, session_id: int):
        """Handle a command from a terminal session."""
        print(f"[TerminalsWindow] Command from session {session_id}: {command}")

        # Emit the command with session ID for the terminal service
        self.terminal_command_entered.emit(command, session_id)

        # Also emit to event bus for compatibility
        self.event_bus.emit("terminal_command_entered", command)

    def handle_terminal_output(self, text: str, session_id: int = None):
        """Handle terminal output for a specific session."""
        if session_id is not None and session_id in self.terminal_sessions:
            # Route to specific terminal
            terminal_widget = self.terminal_sessions[session_id]["widget"]
            terminal_widget.append_output(text)
        else:
            # Route to current terminal if no session specified
            current_widget = self.tab_widget.currentWidget()
            if isinstance(current_widget, TerminalWidget):
                current_widget.append_output(text)

    def handle_terminal_error(self, text: str, session_id: int = None):
        """Handle terminal error output for a specific session."""
        if session_id is not None and session_id in self.terminal_sessions:
            terminal_widget = self.terminal_sessions[session_id]["widget"]
            terminal_widget.append_error_output(text)
        else:
            current_widget = self.tab_widget.currentWidget()
            if isinstance(current_widget, TerminalWidget):
                current_widget.append_error_output(text)

    def handle_terminal_success(self, text: str, session_id: int = None):
        """Handle terminal success output for a specific session."""
        if session_id is not None and session_id in self.terminal_sessions:
            terminal_widget = self.terminal_sessions[session_id]["widget"]
            terminal_widget.append_success_output(text)
        else:
            current_widget = self.tab_widget.currentWidget()
            if isinstance(current_widget, TerminalWidget):
                current_widget.append_success_output(text)

    def mark_command_finished(self, session_id: int = None):
        """Mark a command as finished for a specific session."""
        if session_id is not None and session_id in self.terminal_sessions:
            terminal_widget = self.terminal_sessions[session_id]["widget"]
            terminal_widget.mark_command_finished()
        else:
            # Mark all as finished if no specific session
            for session_info in self.terminal_sessions.values():
                session_info["widget"].mark_command_finished()

    def update_status_bar(self):
        """Update the status bar with current information."""
        terminal_count = len(self.terminal_sessions)
        current_index = self.tab_widget.currentIndex()

        if terminal_count > 0:
            status_text = f"Terminals: {terminal_count} | Current: {current_index + 1}"
        else:
            status_text = "No terminals"

        # Add project info if available
        if self.project_manager and self.project_manager.active_project_path:
            project_name = self.project_manager.active_project_name
            venv_status = "✓" if self.project_manager.is_venv_active else "✗"
            status_text += f" | Project: {project_name} | venv: {venv_status}"

        self.status_bar.showMessage(status_text)

    def set_project_manager(self, project_manager):
        """Update the project manager for all terminals."""
        self.project_manager = project_manager

        # Update all existing terminals
        for session_info in self.terminal_sessions.values():
            terminal_widget = session_info["widget"]
            terminal_widget.project_manager = project_manager
            terminal_widget.update_venv_status()

        self.update_status_bar()

    def get_active_session_info(self) -> dict:
        """Get information about the currently active session."""
        current_widget = self.tab_widget.currentWidget()
        if isinstance(current_widget, TerminalWidget):
            return current_widget.get_session_info()
        return {}

    def get_all_session_info(self) -> list:
        """Get information about all terminal sessions."""
        return [
            session_info["widget"].get_session_info()
            for session_info in self.terminal_sessions.values()
        ]

    def show(self):
        """Override show to ensure window comes to front."""
        super().show()
        self.activateWindow()
        self.raise_()

    def _get_current_time(self):
        """Get current time as string."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")