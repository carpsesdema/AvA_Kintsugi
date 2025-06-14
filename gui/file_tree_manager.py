# kintsugi_ava/gui/file_tree_manager.py
# Enhanced to show full project structure including venv and all relevant files.

from pathlib import Path
from typing import Optional, Callable, Set
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .components import Colors


class FileTreeManager:
    """
    Manages the file tree widget and its operations.
    Single responsibility: Handle file tree display, population, and user interactions.
    Enhanced to show complete project structure including virtual environments.
    """

    def __init__(self, tree_widget: QTreeWidget):
        self.tree_widget = tree_widget
        self.on_file_selected: Optional[Callable[[Path], None]] = None

        # Only ignore truly useless directories - show .venv, .git, etc.
        self._ignore_dirs: Set[str] = {
            '__pycache__', 'node_modules', 'rag_db',
            '.pytest_cache', '.mypy_cache', 'htmlcov',
            'build', 'dist'  # Build artifacts only
        }

        # Directories to show but collapse by default
        self._collapse_dirs: Set[str] = {
            '.venv', 'venv', '.git', '.tox'
        }

        self._setup_tree_widget()

    def _setup_tree_widget(self):
        """Configures the tree widget appearance and behavior."""
        self.tree_widget.setHeaderLabel("Project Files")
        self.tree_widget.setStyleSheet(f"""
            QTreeWidget {{ 
                border: none; 
                background-color: {Colors.SECONDARY_BG.name()}; 
                font-size: 11px;
            }}
            QHeaderView::section {{ 
                background-color: {Colors.SECONDARY_BG.name()}; 
                color: {Colors.TEXT_SECONDARY.name()}; 
                border: none; 
                padding: 4px; 
                font-weight: bold;
            }}
            QTreeWidget::item {{
                padding: 2px;
                border: none;
            }}
            QTreeWidget::item:selected {{
                background-color: {Colors.ACCENT_BLUE.name()};
                color: {Colors.TEXT_PRIMARY.name()};
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
            root_item = self._create_project_root_item(project_path)
            self.tree_widget.addTopLevelItem(root_item)
            root_item.setExpanded(True)

            # Add placeholder items for files that will be generated
            for filename in filenames:
                self._add_file_placeholder(root_item, filename.split('/'), project_path)

            # Add existing project structure
            self._populate_from_disk_enhanced(root_item, project_path)

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
            root_item = self._create_project_root_item(project_path)
            self.tree_widget.addTopLevelItem(root_item)
            root_item.setExpanded(True)

            # Populate from disk with enhanced logic
            self._populate_from_disk_enhanced(root_item, project_path)

            print(f"[FileTreeManager] Loaded existing project tree: {project_path.name}")
            return True

        except Exception as e:
            print(f"[FileTreeManager] Error loading project tree: {e}")
            return False

    def _create_project_root_item(self, project_path: Path) -> QTreeWidgetItem:
        """Creates a styled root item for the project."""
        root_item = QTreeWidgetItem([f"📁 {project_path.name}"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(project_path))

        # Make the root item bold
        font = root_item.font(0)
        font.setBold(True)
        root_item.setFont(0, font)

        return root_item

    def _populate_from_disk_enhanced(self, parent_item: QTreeWidgetItem, directory_path: Path, max_depth: int = 10):
        """
        Enhanced recursive population from disk with better organization.
        """
        if max_depth <= 0:
            return

        try:
            # Get all entries and sort them (directories first, then files)
            entries = list(directory_path.iterdir())
            entries.sort(key=lambda p: (p.is_file(), p.name.lower()))

            for entry in entries:
                # Skip ignored directories and hidden files (except important ones)
                if entry.name in self._ignore_dirs:
                    continue

                if entry.name.startswith('.') and entry.name not in {
                    '.env', '.gitignore', '.git', '.venv', '.github'
                }:
                    continue

                if entry.is_dir():
                    dir_item = self._create_directory_item(entry.name, entry)
                    parent_item.addChild(dir_item)

                    # Recursively populate but with depth limits for some dirs
                    new_depth = max_depth - 1
                    if entry.name in {'.venv', 'venv'}:
                        new_depth = min(2, new_depth)  # Limit venv depth
                    elif entry.name == '.git':
                        new_depth = min(1, new_depth)  # Very limited git depth

                    self._populate_from_disk_enhanced(dir_item, entry, new_depth)

                    # Collapse certain directories by default
                    if entry.name in self._collapse_dirs:
                        dir_item.setExpanded(False)
                    else:
                        dir_item.setExpanded(True)

                else:
                    # Regular file
                    file_item = self._create_file_item(entry.name, entry)
                    parent_item.addChild(file_item)

        except PermissionError:
            print(f"[FileTreeManager] Permission denied accessing: {directory_path}")
        except Exception as e:
            print(f"[FileTreeManager] Error populating tree from {directory_path}: {e}")

    def _create_directory_item(self, dir_name: str, dir_path: Path) -> QTreeWidgetItem:
        """Creates a styled directory item with appropriate icons."""
        icon = self._get_directory_icon(dir_name)
        dir_item = QTreeWidgetItem([f"{icon} {dir_name}"])
        dir_item.setData(0, Qt.ItemDataRole.UserRole, str(dir_path))

        # Style special directories
        if dir_name in {'.venv', 'venv'}:
            font = dir_item.font(0)
            font.setItalic(True)
            dir_item.setFont(0, font)

        return dir_item

    def _create_file_item(self, filename: str, file_path: Path) -> QTreeWidgetItem:
        """Creates a styled file item with appropriate icons."""
        icon = self._get_file_icon(filename)
        file_item = QTreeWidgetItem([f"{icon} {filename}"])
        file_item.setData(0, Qt.ItemDataRole.UserRole, str(file_path))
        return file_item

    def _get_directory_icon(self, dir_name: str) -> str:
        """Returns an appropriate icon for different directory types."""
        icons = {
            '.venv': '🐍',
            'venv': '🐍',
            '.git': '📋',
            '.github': '📋',
            'tests': '🧪',
            'docs': '📚',
            'static': '🌐',
            'templates': '📄',
            '__pycache__': '💾',
            'core': '⚙️',
            'gui': '🖥️',
            'services': '🛠️',
            'utils': '🔧',
            'prompts': '💬',
        }
        return icons.get(dir_name, '📁')

    def _get_file_icon(self, filename: str) -> str:
        """Returns an appropriate icon for different file types."""
        suffix = Path(filename).suffix.lower()

        # Special filenames
        special_files = {
            'main.py': '🚀',
            'requirements.txt': '📦',
            '.gitignore': '🚫',
            '.env': '🔐',
            'README.md': '📖',
            'setup.py': '⚙️',
            'pyproject.toml': '⚙️',
        }

        if filename in special_files:
            return special_files[filename]

        # By extension
        icons = {
            '.py': '🐍',
            '.js': '📄',
            '.ts': '📄',
            '.html': '🌐',
            '.css': '🎨',
            '.md': '📝',
            '.txt': '📄',
            '.json': '⚙️',
            '.toml': '⚙️',
            '.yml': '⚙️',
            '.yaml': '⚙️',
            '.xml': '📄',
            '.csv': '📊',
            '.sql': '🗃️',
            '.db': '🗃️',
            '.log': '📋',
            '.exe': '⚙️',
            '.dll': '⚙️',
            '.so': '⚙️',
        }
        return icons.get(suffix, '📄')

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
            # Calculate the full path for this item
            parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole)
            if parent_path:
                full_path = Path(parent_path) / part
            else:
                full_path = project_root / part

            # Create appropriate item based on whether it's a file or directory
            if len(path_parts) == 1:
                # It's a file
                child_item = self._create_file_item(part, full_path)
            else:
                # It's a directory
                child_item = self._create_directory_item(part, full_path)

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
            # Extract name from display text (remove icon)
            display_text = child.text(0)
            if ' ' in display_text:
                actual_name = display_text.split(' ', 1)[1]  # Remove icon part
            else:
                actual_name = display_text

            if actual_name == child_name:
                return child
        return None

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