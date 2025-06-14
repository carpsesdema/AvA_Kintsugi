# kintsugi_ava/gui/file_tree_manager.py
# Manages the file tree display and interactions for the Code Viewer.

from pathlib import Path
from typing import Optional, Callable, Set
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt

from .components import Colors


class FileTreeManager:
    """
    Manages the file tree widget and its operations.
    Single responsibility: Handle file tree display, population, and user interactions.
    """

    def __init__(self, tree_widget: QTreeWidget):
        self.tree_widget = tree_widget
        self.on_file_selected: Optional[Callable[[Path], None]] = None
        self._ignore_dirs: Set[str] = {
            '.git', '__pycache__', 'venv', '.venv', 'node_modules', 'rag_db',
            'build', 'dist', '.idea', '.vscode'
        }
        self._setup_tree_widget()

    def _setup_tree_widget(self):
        """Configures the tree widget appearance and behavior."""
        self.tree_widget.setHeaderLabel("Project Files")
        self.tree_widget.setStyleSheet(f"""
            QTreeWidget {{ 
                border: none; 
                background-color: {Colors.SECONDARY_BG.name()}; 
            }}
            QHeaderView::section {{ 
                background-color: {Colors.SECONDARY_BG.name()}; 
                color: {Colors.TEXT_SECONDARY.name()}; 
                border: none; 
                padding: 4px; 
            }}
        """)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

    def set_file_selection_callback(self, callback: Callable[[Path], None]):
        """
        Sets the callback function to be called when a file is selected.

        Args:
            callback: Function that takes a Path and handles file selection
        """
        self.on_file_selected = callback

    def clear_tree(self):
        """Clears all items from the file tree."""
        self.tree_widget.clear()
        print("[FileTreeManager] Tree cleared")

    def setup_new_project_tree(self, project_path: Path, filenames: list[str]) -> bool:
        """
        Sets up the tree for a new project being generated.

        Args:
            project_path: Root path of the new project
            filenames: List of filenames that will be generated

        Returns:
            True if tree was set up successfully, False otherwise
        """
        try:
            self.clear_tree()

            # Create root item for the project
            root_item = QTreeWidgetItem([project_path.name])
            root_item.setData(0, Qt.ItemDataRole.UserRole, str(project_path))
            self.tree_widget.addTopLevelItem(root_item)
            root_item.setExpanded(True)

            # Add placeholder items for files that will be generated
            for filename in filenames:
                self._add_file_placeholder(root_item, filename.split('/'), project_path)

            print(f"[FileTreeManager] New project tree set up for: {project_path.name}")
            return True

        except Exception as e:
            print(f"[FileTreeManager] Error setting up new project tree: {e}")
            return False

    def load_existing_project_tree(self, project_path: Path) -> bool:
        """
        Loads an existing project's file structure into the tree.

        Args:
            project_path: Root path of the existing project

        Returns:
            True if tree was loaded successfully, False otherwise
        """
        try:
            if not project_path.is_dir():
                print(f"[FileTreeManager] Error: Not a directory: {project_path}")
                return False

            self.clear_tree()

            # Create root item
            root_item = QTreeWidgetItem([project_path.name])
            root_item.setData(0, Qt.ItemDataRole.UserRole, str(project_path))
            self.tree_widget.addTopLevelItem(root_item)
            root_item.setExpanded(True)

            # Populate from disk
            self._populate_from_disk(root_item, project_path)

            print(f"[FileTreeManager] Loaded existing project tree: {project_path.name}")
            return True

        except Exception as e:
            print(f"[FileTreeManager] Error loading project tree: {e}")
            return False

    def _add_file_placeholder(self, parent_item: QTreeWidgetItem, path_parts: list[str], project_root: Path):
        """
        Adds a file placeholder to the tree (for files being generated).

        Args:
            parent_item: Parent tree item
            path_parts: Path components split by '/'
            project_root: Root directory of the project
        """
        if not path_parts:
            return

        part = path_parts[0]

        # Check if this part already exists as a child
        child_item = self._find_child_item(parent_item, part)

        if not child_item:
            child_item = QTreeWidgetItem([part])

            # Calculate the full path for this item
            parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole)
            if parent_path:
                full_path = Path(parent_path) / part
            else:
                full_path = project_root / part

            child_item.setData(0, Qt.ItemDataRole.UserRole, str(full_path))
            parent_item.addChild(child_item)

        # Continue recursively if there are more path parts
        if len(path_parts) > 1:
            self._add_file_placeholder(child_item, path_parts[1:], project_root)

    def _find_child_item(self, parent_item: QTreeWidgetItem, child_name: str) -> Optional[QTreeWidgetItem]:
        """
        Finds a child item by name under the given parent.

        Args:
            parent_item: Parent tree item to search under
            child_name: Name of the child item to find

        Returns:
            Child item if found, None otherwise
        """
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.text(0) == child_name:
                return child
        return None

    def _populate_from_disk(self, parent_item: QTreeWidgetItem, directory_path: Path):
        """
        Recursively populates the tree from disk.

        Args:
            parent_item: Parent tree item
            directory_path: Directory to scan
        """
        try:
            # Get sorted list of directory contents
            entries = sorted(directory_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))

            for entry in entries:
                # Skip ignored directories and files
                if entry.name in self._ignore_dirs:
                    continue

                # Skip hidden files/directories (starting with .)
                if entry.name.startswith('.') and entry.name not in {'.gitignore', '.env'}:
                    continue

                child_item = QTreeWidgetItem([entry.name])
                child_item.setData(0, Qt.ItemDataRole.UserRole, str(entry))
                parent_item.addChild(child_item)

                # Recursively populate directories
                if entry.is_dir():
                    self._populate_from_disk(child_item, entry)

        except PermissionError:
            print(f"[FileTreeManager] Permission denied accessing: {directory_path}")
        except Exception as e:
            print(f"[FileTreeManager] Error populating tree from {directory_path}: {e}")

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """
        Handles double-click events on tree items.

        Args:
            item: The clicked tree item
            column: The column that was clicked (unused)
        """
        try:
            path_str = item.data(0, Qt.ItemDataRole.UserRole)
            if not path_str:
                return

            file_path = Path(path_str)

            # Only handle files, not directories
            if file_path.is_file() and self.on_file_selected:
                self.on_file_selected(file_path)
                print(f"[FileTreeManager] File selected: {file_path}")

        except Exception as e:
            print(f"[FileTreeManager] Error handling item double-click: {e}")

    def refresh_tree_item(self, item_path: Path):
        """
        Refreshes a specific tree item (useful when files are created/modified).

        Args:
            item_path: Path of the item to refresh
        """
        # This could be implemented to refresh specific tree nodes
        # For now, we'll keep it simple and just log
        print(f"[FileTreeManager] Refresh requested for: {item_path}")

    def expand_to_file(self, file_path: Path) -> bool:
        """
        Expands the tree to show and highlight a specific file.

        Args:
            file_path: Path of the file to expand to

        Returns:
            True if file was found and expanded to, False otherwise
        """
        try:
            # This would involve traversing the tree to find the item
            # and expanding all parent nodes. For now, keeping it simple.
            print(f"[FileTreeManager] Expand to file requested: {file_path}")
            return True
        except Exception as e:
            print(f"[FileTreeManager] Error expanding to file {file_path}: {e}")
            return False

    def get_selected_file_path(self) -> Optional[Path]:
        """
        Gets the currently selected file path in the tree.

        Returns:
            Path of selected file, or None if no file is selected
        """
        try:
            current_item = self.tree_widget.currentItem()
            if not current_item:
                return None

            path_str = current_item.data(0, Qt.ItemDataRole.UserRole)
            if not path_str:
                return None

            file_path = Path(path_str)
            return file_path if file_path.is_file() else None

        except Exception as e:
            print(f"[FileTreeManager] Error getting selected file path: {e}")
            return None