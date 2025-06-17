# kintsugi_ava/core/plugins/examples/autonomous_code_reviewer/__init__.py
# A plugin that provides autonomous code review and fixing capabilities.

from typing import Dict, Any
from core.plugins import PluginBase, PluginMetadata, PluginState


class AutonomousCodeReviewerPlugin(PluginBase):
    """
    An autonomous agent that reviews code, identifies issues, and suggests fixes.
    This plugin can be triggered manually by the user or can perform proactive analysis.
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="autonomous_code_reviewer",
            version="1.0.0",
            description="An autonomous agent that reviews code, identifies issues, and suggests fixes.",
            author="Kintsugi AvA Team",
            dependencies=[],
            event_subscriptions=["fix_highlighted_error_requested", "code_generation_complete"],
            event_emissions=["review_and_fix_from_plugin_requested"],
            config_schema={
                "auto_fix_enabled": {
                    "type": "bool",
                    "default": True,
                    "description": "Enable automatically triggering the fix workflow on user request."
                },
                "proactive_analysis": {
                    "type": "bool",
                    "default": True,
                    "description": "Automatically analyze code after generation."
                },
                "error_monitoring": {
                    "type": "bool",
                    "default": True,
                    "description": "Monitor for runtime errors and offer fixes."
                },
                "security_analysis": {
                    "type": "bool",
                    "default": True,
                    "description": "Perform basic security checks on generated code."
                },
                "performance_analysis": {
                    "type": "bool",
                    "default": False,
                    "description": "Perform basic performance checks on generated code."
                },
                "learning_enabled": {
                    "type": "bool",
                    "default": True,
                    "description": "Allow the agent to learn from previous fixes."
                },
                "auto_commit_fixes": {
                    "type": "bool",
                    "default": False,
                    "description": "Automatically commit fixes to version control."
                },
                "analysis_frequency": {
                    "type": "int",
                    "default": 600,
                    "description": "How often to proactively analyze the project (in seconds)."
                }
            },
            enabled_by_default=True
        )

    async def load(self) -> bool:
        self.log("info", "Autonomous Code Reviewer loading...")
        self.set_state(PluginState.LOADED)
        return True

    async def start(self) -> bool:
        self.log("info", "Autonomous Code Reviewer started and is now monitoring events.")
        self.subscribe_to_event("fix_highlighted_error_requested", self._handle_fix_request)
        self.set_state(PluginState.STARTED)
        return True

    async def stop(self) -> bool:
        self.log("info", "Autonomous Code Reviewer stopped.")
        # In a real implementation, we might want to clean up background tasks here
        self.set_state(PluginState.STOPPED)
        return True

    async def unload(self) -> bool:
        self.log("info", "Autonomous Code Reviewer unloaded.")
        self.unsubscribe_all_events()
        self.set_state(PluginState.UNLOADED)
        return True

    def _handle_fix_request(self, error_report: str):
        """
        Handles a user-initiated request to fix a highlighted error.
        It now sends a default command to re-run for validation.
        """
        if not self.get_config_value("auto_fix_enabled", True):
            self.log("info", "Received fix request, but auto-fix is disabled in plugin config.")
            return

        self.log("info", f"Received highlighted error. Relaying to workflow manager for review and fix.")

        # --- THIS IS THE FIX ---
        # When triggering a fix from the highlight widget, we don't have a specific
        # command that failed. We'll assume 'python main.py' is the default
        # command to re-run for validation after the fix is applied.
        default_command_for_validation = "python main.py"
        self.emit_event("review_and_fix_from_plugin_requested", error_report, default_command_for_validation)
        # --- END OF FIX ---