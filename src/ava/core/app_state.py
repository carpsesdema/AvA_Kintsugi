from enum import Enum, auto


class AppState(Enum):
    """
    Represents the primary workflow state of the application.
    """
    BOOTSTRAP = auto()  # No project is loaded. The next user prompt will create a new project.
    MODIFY = auto()     # A project is active. The next user prompt will modify the existing project.