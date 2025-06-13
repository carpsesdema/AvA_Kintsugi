# kintsugi_ava/gui/model_config_dialog.py
# The dialog window for assigning models to AI roles.

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .components import Colors, Typography, ModernButton
from core.llm_client import LLMClient  # We need to talk to the LLMClient


class ModelConfigurationDialog(QDialog):
    """A dialog for configuring which model is used for each AI role."""

    def __init__(self, llm_client: LLMClient, parent=None):
        super().__init__(parent)
        self.llm_client = llm_client

        self.setWindowTitle("Configure AI Models")
        self.setMinimumSize(500, 300)
        self.setStyleSheet(f"background-color: {Colors.SECONDARY_BG.name()};")

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("AI Specialist Configuration")
        title.setFont(Typography.get_font(16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY.name()};")
        main_layout.addWidget(title)

        # We will create a section for each role
        self.role_combos = {}
        # For now, let's just configure the Coder and Chat roles
        roles_to_configure = ["coder", "chat"]

        for role in roles_to_configure:
            layout, combo = self._create_role_selector(role.title())
            main_layout.addLayout(layout)
            self.role_combos[role] = combo

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_button = ModernButton("Cancel", "secondary")
        cancel_button.clicked.connect(self.reject)
        apply_button = ModernButton("Apply", "primary")
        apply_button.clicked.connect(self.apply_changes)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(apply_button)
        main_layout.addLayout(button_layout)

        self._populate_models()

    def _create_role_selector(self, role_name: str) -> tuple[QHBoxLayout, QComboBox]:
        """Factory to create a label and dropdown for a role."""
        layout = QHBoxLayout()
        label = QLabel(f"{role_name}:")
        label.setFont(Typography.body())
        combo = QComboBox()
        combo.setFont(Typography.body())
        layout.addWidget(label)
        layout.addWidget(combo)
        return layout, combo

    def _populate_models(self):
        """Fills the dropdowns with available models from the LLMClient."""
        available_models = self.llm_client.get_available_models()
        current_assignments = self.llm_client.get_role_assignments()

        for role, combo in self.role_combos.items():
            combo.clear()
            current_model_key = current_assignments.get(role)
            current_index = 0

            for i, (key, name) in enumerate(available_models.items()):
                combo.addItem(name, key)  # text, data
                if key == current_model_key:
                    current_index = i

            combo.setCurrentIndex(current_index)

    def apply_changes(self):
        """Saves the selected model assignments back to the LLMClient."""
        new_assignments = {}
        for role, combo in self.role_combos.items():
            new_assignments[role] = combo.currentData()

        self.llm_client.set_role_assignments(new_assignments)
        self.llm_client.save_assignments()
        QMessageBox.information(self, "Success", "Model configuration saved.")
        self.accept()