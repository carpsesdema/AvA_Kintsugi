# kintsugi_ava/gui/enhanced_sidebar.py
# The full sidebar component of our application, built to match the blueprint.
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
import qtawesome as qta # The icon library

from .components import Colors, Typography, ModernButton

class EnhancedSidebar(QWidget):
    """
    The complete sidebar view. It holds all the necessary control panels
    for the application, mirroring our target design.
    """
    def __init__(self):
        super().__init__()
        self.setFixedWidth(300) # Give it a fixed width
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Colors.SECONDARY_BG)
        self.setPalette(palette)

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # --- Instantiate and Add Panels ---
        main_layout.addWidget(self._create_project_panel())
        main_layout.addWidget(self._create_model_panel())
        main_layout.addWidget(self._create_knowledge_panel())
        main_layout.addWidget(self._create_actions_panel())

        # Add a stretch to push everything to the top
        main_layout.addStretch()

    def _create_styled_panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """A helper factory to create our standard styled panels."""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.PRIMARY_BG.name()};
                border-radius: 8px;
            }}
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 8, 12, 12)
        panel_layout.setSpacing(8)

        header = QLabel(title)
        header.setFont(Typography.heading_small())
        header.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; padding: 5px 0px;")
        panel_layout.addWidget(header)

        return panel, panel_layout

    def _create_project_panel(self) -> QFrame:
        """Creates the Project Management panel."""
        panel, layout = self._create_styled_panel("Project Management")

        new_project_btn = ModernButton("New Project", "primary")
        new_project_btn.setIcon(qta.icon("fa5s.plus-circle", color=Colors.TEXT_PRIMARY.name()))

        load_project_btn = ModernButton("Load Project", "secondary")
        load_project_btn.setIcon(qta.icon("fa5s.folder-open", color=Colors.TEXT_PRIMARY.name()))

        # Placeholder for project name display
        self.project_name_label = QLabel("Project: (none)")
        self.project_name_label.setFont(Typography.body())
        self.project_name_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY.name()}; padding-top: 5px;")

        layout.addWidget(new_project_btn)
        layout.addWidget(load_project_btn)
        layout.addWidget(self.project_name_label)
        return panel

    def _create_model_panel(self) -> QFrame:
        """Creates the AI Model Configuration panel."""
        panel, layout = self._create_styled_panel("AI Model Configuration")
        # For now, just a placeholder button. We'll add the status list later.
        config_btn = ModernButton("Configure Models", "secondary")
        config_btn.setIcon(qta.icon("fa5s.cogs", color=Colors.TEXT_PRIMARY.name()))
        layout.addWidget(config_btn)
        return panel

    def _create_knowledge_panel(self) -> QFrame:
        """Creates the Knowledge Base (RAG) panel."""
        panel, layout = self._create_styled_panel("Knowledge Base (RAG)")
        scan_btn = ModernButton("Scan Directory", "secondary")
        scan_btn.setIcon(qta.icon("fa5s.search", color=Colors.TEXT_PRIMARY.name()))
        add_files_btn = ModernButton("Add Project Files", "secondary")
        add_files_btn.setIcon(qta.icon("fa5s.file-medical", color=Colors.TEXT_PRIMARY.name()))
        layout.addWidget(scan_btn)
        layout.addWidget(add_files_btn)
        return panel

    def _create_actions_panel(self) -> QFrame:
        """Creates the Chat Actions panel."""
        panel, layout = self._create_styled_panel("Chat Actions")

        # Session Actions
        layout.addWidget(self._create_action_header("SESSION"))
        layout.addWidget(ModernButton("New Session", "secondary"))

        # Tools Actions
        layout.addWidget(self._create_action_header("TOOLS"))
        layout.addWidget(ModernButton("View LLM Log", "secondary"))
        layout.addWidget(ModernButton("Workflow Monitor", "secondary"))
        layout.addWidget(ModernButton("Open Code Viewer", "secondary"))
        return panel

    def _create_action_header(self, text: str) -> QLabel:
        """Helper to create small headers for action groups."""
        header = QLabel(text)
        header.setFont(Typography.get_font(9, QFont.Weight.Bold))
        header.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY.name()};
            margin-top: 8px;
            margin-bottom: 2px;
            border: none;
            background: transparent;
        """)
        return header