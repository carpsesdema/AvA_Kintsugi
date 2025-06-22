# src/ava/gui/plugin_management_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QAbstractItemView, QHeaderView, QTableWidgetItem
)
from PySide6.QtGui import QFont

from src.ava.core.plugins.plugin_manager import PluginManager
from src.ava.core.event_bus import EventBus
from src.ava.gui.components import Colors, Typography, ModernButton


class PluginManagementDialog(QDialog):
    """
    A dialog for managing the application's plugins.
    """

    def __init__(self, plugin_manager: PluginManager, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.event_bus = event_bus

        self.setWindowTitle("Plugin Management")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(f"background-color: {Colors.SECONDARY_BG.name()}; color: {Colors.TEXT_PRIMARY.name()};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        title = QLabel("Available Plugins")
        title.setFont(Typography.get_font(16, QFont.Weight.Bold))
        main_layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Version", "Status", "Description"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.PRIMARY_BG.name()};
                border: 1px solid {Colors.BORDER_DEFAULT.name()};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background-color: {Colors.ELEVATED_BG.name()};
                padding: 5px;
                border: none;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT.name()};
            }}
        """)
        main_layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        self.enable_btn = ModernButton("Enable", "primary")
        self.disable_btn = ModernButton("Disable", "secondary")
        self.reload_btn = ModernButton("Reload", "secondary")

        self.enable_btn.clicked.connect(self.on_enable_plugin)
        self.disable_btn.clicked.connect(self.on_disable_plugin)
        self.reload_btn.clicked.connect(self.on_reload_plugin)

        button_layout.addWidget(self.enable_btn)
        button_layout.addWidget(self.disable_btn)
        button_layout.addWidget(self.reload_btn)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.populate_plugin_table()
        self.event_bus.subscribe("plugin_state_changed", lambda name, old, new: self.populate_plugin_table())

    def _create_table_item(self, text: str) -> QTableWidgetItem:
        """Helper to create a styled QTableWidgetItem."""
        item = QTableWidgetItem(text)
        item.setFont(Typography.body())
        return item

    def populate_plugin_table(self):
        """Fills the table with the status of all discovered plugins."""
        if not self.plugin_manager:
            return

        all_plugins_info = self.plugin_manager.get_all_plugins_info()
        self.table.setRowCount(len(all_plugins_info))

        for row, status_info in enumerate(all_plugins_info):
            # Name
            name = status_info.get("name", "N/A")
            self.table.setItem(row, 0, self._create_table_item(name))

            # Version
            version = status_info.get("version", "N/A")
            self.table.setItem(row, 1, self._create_table_item(version))

            # Status
            state = status_info.get("state", "unloaded").upper()
            state_item = self._create_table_item(state)
            if state == "STARTED":
                state_item.setForeground(Colors.ACCENT_GREEN)
            elif state == "ERROR":
                state_item.setForeground(Colors.ACCENT_RED)
            self.table.setItem(row, 2, state_item)

            # Description
            description = status_info.get("description", "No description available.")
            self.table.setItem(row, 3, self._create_table_item(description))

    def get_selected_plugin_name(self) -> str | None:
        """Gets the name of the currently selected plugin in the table."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return None
        return self.table.item(selected_items[0].row(), 0).text()

    def on_enable_plugin(self):
        plugin_name = self.get_selected_plugin_name()
        if plugin_name:
            self.event_bus.emit("plugin_enable_requested", plugin_name)

    def on_disable_plugin(self):
        plugin_name = self.get_selected_plugin_name()
        if plugin_name:
            self.event_bus.emit("plugin_disable_requested", plugin_name)

    def on_reload_plugin(self):
        plugin_name = self.get_selected_plugin_name()
        if plugin_name:
            self.event_bus.emit("plugin_reload_requested", plugin_name)

    def exec(self):
        """Overridden to refresh the table every time it's opened."""
        self.populate_plugin_table()
        super().exec()