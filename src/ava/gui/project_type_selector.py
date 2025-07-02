# src/ava/gui/project_type_selector.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
import qtawesome as qta

from .components import Colors, Typography


class ProjectTypeSelector(QWidget):
    """
    A custom dropdown widget for selecting the project type (e.g., Python, Godot).
    """
    projectTypeChanged = Signal(str)  # Emits the new project type as a string

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(160)

        # --- State ---
        self.project_types = {
            "Python": "fa5b.python",
            "Godot": "fa5s.gamepad",
            "Unreal C++": "fa5s.cube"
        }
        self._current_type = "Python"

        # --- UI ---
        self.button = QPushButton()
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setMinimumHeight(34)
        self.button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ELEVATED_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 6px;
                padding: 5px 10px;
                text-align: left;
                font-family: "{Typography.body().family()}";
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Colors.SECONDARY_BG.name()};
            }}
            QPushButton::menu-indicator {{
                image: none; /* Hide default indicator */
            }}
        """)

        self.menu = QMenu(self)
        self.menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Colors.ELEVATED_BG.name()};
                color: {Colors.TEXT_PRIMARY.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.ACCENT_BLUE.name()};
            }}
        """)
        self.button.setMenu(self.menu)

        self._populate_menu()
        self.setProjectType("Python")  # Set initial state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.button)

    def _populate_menu(self):
        self.menu.clear()
        for type_name, icon_name in self.project_types.items():
            action = QAction(qta.icon(icon_name), type_name, self)
            action.triggered.connect(lambda checked=False, name=type_name: self.setProjectType(name))
            self.menu.addAction(action)

    def setProjectType(self, project_type: str):
        """Sets the current project type and updates the button's appearance."""
        if project_type not in self.project_types:
            return

        self._current_type = project_type
        icon_name = self.project_types[project_type]

        self.button.setText(f"  {project_type}")
        self.button.setIcon(qta.icon(icon_name, color=Colors.TEXT_PRIMARY))

        self.projectTypeChanged.emit(self._current_type)
        print(f"[ProjectTypeSelector] Project type changed to: {self._current_type}")

    def addProjectType(self, name: str, icon_name: str):
        """Allows other parts of the app (like plugins) to add new project types."""
        if name not in self.project_types:
            self.project_types[name] = icon_name
            self._populate_menu()