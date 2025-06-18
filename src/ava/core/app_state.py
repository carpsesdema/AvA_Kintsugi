# kintsugi_ava/core/app_state.py
# NEW FILE: Defines the possible states of the application workflow.
# Single Responsibility: To provide a clear, type-safe enumeration of application states.

from enum import Enum, auto


class AppState(Enum):
    """
    Represents the primary workflow state of the application.
    """
    BOOTSTRAP = auto()  # No project is loaded. The next user prompt will create a new project.
    MODIFY = auto()     # A project is active. The next user prompt will modify the existing project.