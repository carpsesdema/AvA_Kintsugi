# src/ava/gui/enhanced_sidebar.py
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
import qtawesome as qta

from src.ava.gui.components import Colors, Typography, ModernButton, StatusIndicatorDot
from src.ava.core.event_bus import EventBus


# REMOVE THE FOLLOWING LINE:
# from src.ava.core.managers.window_manager import WindowManager


class EnhancedSidebar(QWidget):
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self.setFixedWidth(300)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Colors.SECONDARY_BG)
        self.setPalette(palette)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._create_project_panel())
        main_layout.addWidget(self._create_model_panel())
        main_layout.addWidget(self._create_knowledge_panel())
        main_layout.addWidget(self._create_plugin_panel())
        main_layout.addWidget(self._create_actions_panel())
        main_layout.addStretch()

    def _create_styled_panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {Colors.PRIMARY_BG.name()}; border-radius: 8px;")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 8, 12, 12)
        panel_layout.setSpacing(8)
        header = QLabel(title)
        header.setFont(Typography.heading_small())
        header.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; padding: 5px 0px;")
        panel_layout.addWidget(header)
        return panel, panel_layout

    def _create_project_panel(self) -> QFrame:
        panel, layout = self._create_styled_panel("Project Management")
        new_project_btn = ModernButton("New Project", "primary")
        new_project_btn.setIcon(qta.icon("fa5s.plus-circle", color=Colors.TEXT_PRIMARY.name()))
        new_project_btn.clicked.connect(lambda: self.event_bus.emit("new_project_requested"))
        load_project_btn = ModernButton("Load Project", "secondary")
        load_project_btn.setIcon(qta.icon("fa5s.folder-open", color=Colors.TEXT_PRIMARY.name()))
        load_project_btn.clicked.connect(lambda: self.event_bus.emit("load_project_requested"))
        self.project_name_label = QLabel("Project: (none)")
        self.project_name_label.setFont(Typography.body())
        self.project_name_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; padding-top: 5px;")
        layout.addWidget(new_project_btn)
        layout.addWidget(load_project_btn)
        layout.addWidget(self.project_name_label)
        return panel

    def _create_model_panel(self) -> QFrame:
        panel, layout = self._create_styled_panel("AI Model Configuration")
        config_btn = ModernButton("Configure Models", "secondary")
        config_btn.setIcon(qta.icon("fa5s.cogs", color=Colors.TEXT_PRIMARY.name()))
        config_btn.clicked.connect(lambda: self.event_bus.emit("configure_models_requested"))
        layout.addWidget(config_btn)
        return panel

    def _create_knowledge_panel(self) -> QFrame:
        panel, layout = self._create_styled_panel("Knowledge Base (RAG)")

        add_project_files_btn = ModernButton("Add Project Files to RAG", "secondary")
        add_project_files_btn.setIcon(qta.icon("fa5s.folder-plus", color=Colors.TEXT_PRIMARY.name()))
        add_project_files_btn.setToolTip(
            "Scans all source files in the current project and adds them to this project's knowledge base.")
        add_project_files_btn.clicked.connect(lambda: self.event_bus.emit("add_active_project_to_rag_requested"))
        layout.addWidget(add_project_files_btn)

        add_external_file_btn = ModernButton("Add External File to Project", "secondary")
        add_external_file_btn.setIcon(qta.icon("fa5s.file-import", color=Colors.TEXT_PRIMARY.name()))
        add_external_file_btn.setToolTip(
            "Add specific external files (like a GDD) to the current project's knowledge base.")
        add_external_file_btn.clicked.connect(lambda: self.event_bus.emit("add_knowledge_requested"))
        layout.addWidget(add_external_file_btn)

        add_global_docs_btn = ModernButton("Add Global Docs", "secondary")
        add_global_docs_btn.setIcon(qta.icon("fa5s.globe", color=Colors.TEXT_PRIMARY.name()))
        add_global_docs_btn.setToolTip(
            "Add a directory of documents (e.g., code examples) to the global, shared knowledge base.")
        add_global_docs_btn.clicked.connect(lambda: self.event_bus.emit("add_global_knowledge_requested"))
        layout.addWidget(add_global_docs_btn)

        return panel

    def _create_plugin_panel(self) -> QFrame:
        panel, layout = self._create_styled_panel("Plugin System")
        plugin_main_layout = QHBoxLayout()
        plugin_main_layout.setContentsMargins(0, 0, 0, 0)
        plugin_main_layout.setSpacing(8)
        self.plugin_status_dot = StatusIndicatorDot()
        status_label = QLabel("Plugins")
        status_label.setFont(Typography.body())
        status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()};")
        manage_plugins_btn = QPushButton("Manage")
        manage_plugins_btn.setFont(Typography.body())
        manage_plugins_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manage_plugins_btn.setMaximumHeight(28)
        manage_plugins_btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {Colors.ELEVATED_BG.name()}; 
                color: {Colors.TEXT_PRIMARY.name()}; 
                border: 1px solid {Colors.BORDER_DEFAULT.name()}; 
                border-radius: 6px; 
                padding: 4px 12px; 
            }}
            QPushButton:hover {{ 
                background-color: {Colors.ACCENT_BLUE.name()}; 
                border-color: {Colors.ACCENT_BLUE.name()};
            }}
        """)
        manage_plugins_btn.clicked.connect(lambda: self.event_bus.emit("plugin_management_requested"))
        plugin_main_layout.addWidget(self.plugin_status_dot)
        plugin_main_layout.addWidget(status_label)
        plugin_main_layout.addStretch()
        plugin_main_layout.addWidget(manage_plugins_btn)
        layout.addLayout(plugin_main_layout)
        return panel

    def _create_actions_panel(self) -> QFrame:
        panel, layout = self._create_styled_panel("Actions & Tools")
        layout.addWidget(self._create_action_header("SESSION"))

        new_session_btn = ModernButton("New Session", "secondary")
        new_session_btn.setIcon(qta.icon("fa5s.power-off", color=Colors.TEXT_PRIMARY.name()))
        new_session_btn.clicked.connect(lambda: self.event_bus.emit("new_session_requested"))
        layout.addWidget(new_session_btn)

        save_chat_btn = ModernButton("Save Chat", "secondary")
        save_chat_btn.setIcon(qta.icon("fa5s.save", color=Colors.TEXT_PRIMARY.name()))
        save_chat_btn.clicked.connect(lambda: self.event_bus.emit("save_chat_requested"))
        layout.addWidget(save_chat_btn)

        load_chat_btn = ModernButton("Load Chat", "secondary")
        load_chat_btn.setIcon(qta.icon("fa5s.folder-open", color=Colors.TEXT_PRIMARY.name()))
        load_chat_btn.clicked.connect(lambda: self.event_bus.emit("load_chat_requested"))
        layout.addWidget(load_chat_btn)

        layout.addWidget(self._create_action_header("TOOLS"))

        log_btn = ModernButton("View Logs", "secondary")
        log_btn.setIcon(qta.icon("fa5s.file-alt", color=Colors.TEXT_PRIMARY.name()))
        log_btn.clicked.connect(lambda: self.event_bus.emit("show_log_viewer_requested"))
        layout.addWidget(log_btn)

        code_viewer_btn = ModernButton("Open Code Viewer", "secondary")
        code_viewer_btn.setIcon(qta.icon("fa5s.code", color=Colors.TEXT_PRIMARY.name()))
        code_viewer_btn.clicked.connect(lambda: self.event_bus.emit("show_code_viewer_requested"))
        layout.addWidget(code_viewer_btn)

        return panel

    def _create_action_header(self, text: str) -> QLabel:
        header = QLabel(text)
        header.setFont(Typography.get_font(9, QFont.Weight.Bold))
        header.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY.name()}; margin-top: 8px; margin-bottom: 2px; border: none; background: transparent;")
        return header

    def update_project_display(self, project_name: str):
        self.project_name_label.setText(f"Project: {project_name}")

    def update_plugin_status(self, status: str):  # This method is called by EventCoordinator/Application
        self.plugin_status_dot.setStatus(status)