# src/ava/gui/integrated_terminal.py
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QHBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Signal
import qtawesome as qta

from src.ava.gui.components import Colors, Typography, ModernButton
from src.ava.gui.terminal_widget import TerminalWidget
from src.ava.core.project_manager import ProjectManager
from src.ava.core.event_bus import EventBus


class IntegratedTerminal(QWidget):
    """
    A multi-tab terminal manager embedded within the Code Viewer.
    """
    command_entered = Signal(str, int)  # command, session_id

    def __init__(self, event_bus: EventBus, project_manager: ProjectManager):
        super().__init__()
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.sessions = {}
        self.next_session_id = 0

        self.tab_widget: QTabWidget = None
        self.fix_button: ModernButton = None
        self.fixing_label: QLabel = None
        self.run_python_button: ModernButton = None

        self.setObjectName("integrated_terminal")
        self.setup_ui()
        self._connect_events()

    def setup_ui(self):
        self.setStyleSheet(f"""
            #integrated_terminal {{
                background-color: {Colors.PRIMARY_BG.name()};
                border-top: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(5)

        action_bar = self._create_action_bar()
        main_layout.addWidget(action_bar)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)

        new_tab_btn = QPushButton()
        new_tab_btn.setIcon(qta.icon("fa5s.plus", color=Colors.TEXT_PRIMARY))
        new_tab_btn.setFixedSize(28, 28)
        self.tab_widget.setCornerWidget(new_tab_btn, Qt.Corner.TopRightCorner)
        new_tab_btn.clicked.connect(self.create_new_terminal_tab)

        main_layout.addWidget(self.tab_widget)
        self._add_initial_tab()

    def _create_action_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("action_bar")
        bar.setStyleSheet(f"""
            #action_bar {{
                background-color: {Colors.SECONDARY_BG.name()};
                padding: 5px;
                border-radius: 6px;
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(10)

        self.run_python_button = ModernButton("Run Code", "primary")
        self.run_python_button.setIcon(qta.icon("fa5s.play", color=Colors.TEXT_PRIMARY))
        self.run_python_button.clicked.connect(self._on_run_python_clicked)
        layout.addWidget(self.run_python_button)

        install_button = ModernButton("Install Dependencies", "secondary")
        install_button.setIcon(qta.icon("fa5s.download", color=Colors.TEXT_SECONDARY))
        install_button.clicked.connect(self._on_install_clicked)
        layout.addWidget(install_button)

        layout.addStretch()

        self.fixing_label = QLabel("🤖 AI is fixing the code...")
        self.fixing_label.setFont(Typography.body())
        self.fixing_label.setStyleSheet(f"color: {Colors.ACCENT_BLUE.name()};")
        self.fixing_label.hide()
        layout.addWidget(self.fixing_label)

        self.fix_button = ModernButton("Review & Fix Code", "primary")
        self.fix_button.setIcon(qta.icon("fa5s.magic", color=Colors.TEXT_PRIMARY))
        fix_color = Colors.ACCENT_RED.lighter(120).name()
        self.fix_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {fix_color};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()}; border-radius: 6px; padding: 5px 15px;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_RED.name()}; }}
        """)
        self.fix_button.clicked.connect(self._on_fix_clicked)
        self.fix_button.hide()
        layout.addWidget(self.fix_button)

        return bar

    def _get_current_session_id(self) -> int:
        current_widget = self.tab_widget.currentWidget()
        if isinstance(current_widget, TerminalWidget):
            return current_widget.session_id
        return 0

    def _on_run_python_clicked(self):
        session_id = self._get_current_session_id()
        self.command_entered.emit("python main.py", session_id)

    def _on_install_clicked(self):
        session_id = self._get_current_session_id()
        if self.project_manager and self.project_manager.active_project_path:
            req_file = self.project_manager.active_project_path / "requirements.txt"
            if req_file.exists():
                self.command_entered.emit("pip install -r requirements.txt", session_id)
            else:
                self.event_bus.emit("terminal_output_received", "No requirements.txt file found.\n", session_id)
        else:
            self.event_bus.emit("terminal_output_received", "No active project.\n", session_id)

    def _on_fix_clicked(self):
        self.event_bus.emit("review_and_fix_requested")
        self.show_fixing_in_progress()

    def show_fix_button(self):
        if self.fix_button: self.fix_button.show()
        if self.fixing_label: self.fixing_label.hide()

    def hide_fix_button(self):
        if self.fix_button: self.fix_button.hide()

    def show_fixing_in_progress(self):
        self.hide_fix_button()
        if self.fixing_label: self.fixing_label.show()

    def _add_initial_tab(self):
        self.create_new_terminal_tab(closable=False)

    def create_new_terminal_tab(self, closable=True):
        session_id = self.next_session_id
        self.next_session_id += 1
        terminal = TerminalWidget(session_id, self.project_manager, self.event_bus)
        terminal.command_entered.connect(self.command_entered.emit)
        self.sessions[session_id] = terminal
        index = self.tab_widget.addTab(terminal, f"Terminal {session_id + 1}")
        self.tab_widget.setCurrentIndex(index)
        if not closable:
            self.tab_widget.tabBar().setTabButton(index, self.tab_widget.tabBar().ButtonPosition.RightSide, None)

    def _close_tab(self, index: int):
        widget = self.tab_widget.widget(index)
        if isinstance(widget, TerminalWidget):
            session_id_to_close = widget.session_id
            if session_id_to_close in self.sessions:
                del self.sessions[session_id_to_close]
            self.tab_widget.removeTab(index)
            widget.deleteLater()

    def _connect_events(self):
        self.event_bus.subscribe("terminal_output_received", self._route_output)
        self.event_bus.subscribe("terminal_error_received", self._route_error)
        self.event_bus.subscribe("terminal_success_received", self._route_success)
        self.event_bus.subscribe("terminal_command_finished", self._route_command_finished)
        self.event_bus.subscribe("ai_fix_workflow_complete", self._on_ai_fix_complete)

    def _on_ai_fix_complete(self):
        if self.fixing_label:
            self.fixing_label.hide()

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
        if self.fixing_label:
            self.fixing_label.hide()

    def set_project_manager(self, project_manager: ProjectManager):
        self.project_manager = project_manager
        for session in self.sessions.values():
            session.set_project_manager(project_manager)