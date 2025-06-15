# kintsugi_ava/gui/enhanced_sidebar.py
# V7: Added plugin management section

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
import qtawesome as qta

from .components import Colors, Typography, ModernButton
from core.event_bus import EventBus


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

        launch_rag_btn = ModernButton("Launch RAG Server", "primary")
        launch_rag_btn.setIcon(qta.icon("fa5s.rocket", color=Colors.TEXT_PRIMARY.name()))
        launch_rag_btn.clicked.connect(lambda: self.event_bus.emit("launch_rag_server_requested"))
        layout.addWidget(launch_rag_btn)

        scan_btn = ModernButton("Scan Directory", "secondary")
        scan_btn.setIcon(qta.icon("fa5s.search", color=Colors.TEXT_PRIMARY.name()))
        scan_btn.clicked.connect(lambda: self.event_bus.emit("scan_directory_requested"))

        add_files_btn = ModernButton("Add Project Files", "secondary")
        add_files_btn.setIcon(qta.icon("fa5s.file-medical", color=Colors.TEXT_PRIMARY.name()))
        add_files_btn.clicked.connect(lambda: self.event_bus.emit("add_active_project_to_rag_requested"))

        layout.addWidget(scan_btn)
        layout.addWidget(add_files_btn)
        return panel

    def _create_plugin_panel(self) -> QFrame:
        """New plugin management panel."""
        panel, layout = self._create_styled_panel("Plugin System")

        # Plugin status display
        self.plugin_status_label = QLabel("Plugins: Loading...")
        self.plugin_status_label.setFont(Typography.body())
        self.plugin_status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; padding: 2px 0px;")
        layout.addWidget(self.plugin_status_label)

        # Plugin action buttons
        plugin_buttons_layout = QHBoxLayout()
        plugin_buttons_layout.setSpacing(4)

        refresh_plugins_btn = QPushButton("Refresh")
        refresh_plugins_btn.setFont(Typography.body())
        refresh_plugins_btn.setMaximumHeight(24)
        refresh_plugins_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ELEVATED_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_BLUE.name()};
            }}
        """)
        refresh_plugins_btn.clicked.connect(lambda: self.event_bus.emit("plugin_status_refresh_requested"))

        manage_plugins_btn = QPushButton("Manage")
        manage_plugins_btn.setFont(Typography.body())
        manage_plugins_btn.setMaximumHeight(24)
        manage_plugins_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ELEVATED_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_BLUE.name()};
            }}
        """)
        manage_plugins_btn.clicked.connect(lambda: self.event_bus.emit("plugin_management_requested"))

        plugin_buttons_layout.addWidget(refresh_plugins_btn)
        plugin_buttons_layout.addWidget(manage_plugins_btn)
        plugin_buttons_layout.addStretch()
        layout.addLayout(plugin_buttons_layout)

        # Subscribe to plugin status updates
        self.event_bus.subscribe("plugin_status_changed", self._update_plugin_status)
        self.event_bus.subscribe("plugin_status_refresh_requested", self._refresh_plugin_status)

        return panel

    def _create_actions_panel(self) -> QFrame:
        panel, layout = self._create_styled_panel("Chat Actions")
        layout.addWidget(self._create_action_header("SESSION"))
        new_session_btn = ModernButton("New Session", "secondary")
        new_session_btn.clicked.connect(lambda: self.event_bus.emit("new_session_requested"))
        layout.addWidget(new_session_btn)
        layout.addWidget(self._create_action_header("TOOLS"))
        log_btn = ModernButton("View LLM Log", "secondary")
        log_btn.setIcon(qta.icon("fa5s.terminal", color=Colors.TEXT_PRIMARY.name()))
        log_btn.clicked.connect(lambda: self.event_bus.emit("show_terminals_requested"))
        layout.addWidget(log_btn)
        monitor_btn = ModernButton("Workflow Monitor", "secondary")
        monitor_btn.setIcon(qta.icon("fa5s.project-diagram", color=Colors.TEXT_PRIMARY.name()))
        monitor_btn.clicked.connect(lambda: self.event_bus.emit("show_workflow_monitor_requested"))
        layout.addWidget(monitor_btn)
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
        """Public method to update the project name label."""
        self.project_name_label.setText(f"Project: {project_name}")

    def _update_plugin_status(self, *args):
        """Update plugin status display when plugins change state."""
        self._refresh_plugin_status()

    def _refresh_plugin_status(self):
        """Refresh the plugin status display."""
        # This would normally get real plugin status from the plugin manager
        # For now, show a placeholder
        self.plugin_status_label.setText("Plugins: Ready (Click Manage)")

        # Emit a request for actual plugin status
        # The event coordinator will handle getting real status from the plugin manager
        self.event_bus.emit("log_message_received", "UI", "info", "Plugin status refresh requested")