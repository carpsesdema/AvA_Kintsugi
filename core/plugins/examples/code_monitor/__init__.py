# kintsugi_ava/core/plugins/examples/code_monitor/__init__.py
# Example Code Monitor plugin demonstrating code generation tracking

from typing import Dict, Any
from datetime import datetime
from collections import defaultdict

from core.plugins import PluginBase, PluginMetadata, PluginState


class CodeMonitorPlugin(PluginBase):
    """
    A plugin that monitors and tracks code generation statistics.

    This plugin:
    - Tracks files generated and modified
    - Monitors streaming activity
    - Collects usage statistics
    - Provides periodic reports
    """

    def __init__(self, event_bus, plugin_config: Dict[str, Any]):
        super().__init__(event_bus, plugin_config)

        # Statistics tracking
        self.stats = {
            "sessions": 0,
            "files_generated": 0,
            "total_characters": 0,
            "stream_events": 0,
            "start_time": None,
            "file_types": defaultdict(int),
            "generation_events": []
        }

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata for the code monitor."""
        return PluginMetadata(
            name="code_monitor",
            version="1.0.0",
            description="Monitors and tracks code generation statistics and activity",
            author="Kintsugi AvA Team",
            dependencies=[],
            event_subscriptions=[
                "prepare_for_generation",
                "stream_code_chunk",
                "code_generation_complete",
                "new_session_requested"
            ],
            event_emissions=[
                "plugin_log_message"
            ],
            config_schema={
                "report_frequency": {
                    "type": "int",
                    "default": 5,
                    "description": "Report statistics every N files generated"
                },
                "track_file_types": {
                    "type": "bool",
                    "default": True,
                    "description": "Track statistics by file type"
                },
                "detailed_logging": {
                    "type": "bool",
                    "default": False,
                    "description": "Log detailed generation events"
                }
            },
            enabled_by_default=False  # Opt-in plugin
        )

    async def load(self) -> bool:
        """Load the code monitor plugin."""
        try:
            self.log("info", "Code Monitor plugin loading...")

            # Reset statistics
            self.stats = {
                "sessions": 0,
                "files_generated": 0,
                "total_characters": 0,
                "stream_events": 0,
                "start_time": datetime.now(),
                "file_types": defaultdict(int),
                "generation_events": []
            }

            self.set_state(PluginState.LOADED)
            self.log("success", "Code Monitor plugin loaded")
            return True

        except Exception as e:
            self.log("error", f"Failed to load Code Monitor plugin: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def start(self) -> bool:
        """Start monitoring code generation events."""
        try:
            self.log("info", "Starting Code Monitor plugin...")

            # Subscribe to code generation events
            self.subscribe_to_event("prepare_for_generation", self._on_prepare_generation)
            self.subscribe_to_event("stream_code_chunk", self._on_stream_chunk)
            self.subscribe_to_event("code_generation_complete", self._on_generation_complete)
            self.subscribe_to_event("new_session_requested", self._on_new_session)

            self.set_state(PluginState.STARTED)
            self.log("info", "📊 Code Monitor active - tracking generation statistics")

            return True

        except Exception as e:
            self.log("error", f"Failed to start Code Monitor plugin: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def stop(self) -> bool:
        """Stop monitoring and report final statistics."""
        try:
            self.log("info", "Stopping Code Monitor plugin...")

            # Generate final report
            self._generate_report(final=True)

            self.set_state(PluginState.STOPPED)
            return True

        except Exception as e:
            self.log("error", f"Failed to stop Code Monitor plugin: {e}")
            self.set_state(PluginState.ERROR)
            return False

    async def unload(self) -> bool:
        """Unload the plugin and clear statistics."""
        try:
            self.log("info", "Unloading Code Monitor plugin...")

            # Clear statistics
            self.stats.clear()

            self.set_state(PluginState.UNLOADED)
            self.log("info", "Code Monitor plugin unloaded")
            return True

        except Exception as e:
            self.log("error", f"Failed to unload Code Monitor plugin: {e}")
            self.set_state(PluginState.ERROR)
            return False

    # Event handlers
    def _on_prepare_generation(self, filenames: list, project_path: str = None):
        """Track preparation for code generation."""
        if self.get_config_value("detailed_logging", False):
            self.log("info", f"🔄 Preparing to generate {len(filenames)} files")

        # Track file types if enabled
        if self.get_config_value("track_file_types", True):
            for filename in filenames:
                file_ext = filename.split('.')[-1] if '.' in filename else 'no_extension'
                self.stats["file_types"][file_ext] += 1

        # Record generation event
        self.stats["generation_events"].append({
            "timestamp": datetime.now(),
            "event": "prepare_generation",
            "file_count": len(filenames),
            "project_path": project_path
        })

    def _on_stream_chunk(self, filename: str, chunk: str):
        """Track streaming code chunks."""
        self.stats["stream_events"] += 1
        self.stats["total_characters"] += len(chunk)

        if self.get_config_value("detailed_logging", False) and self.stats["stream_events"] % 100 == 0:
            self.log("info",
                     f"📝 Streamed {self.stats['stream_events']} chunks, {self.stats['total_characters']} characters total")

    def _on_generation_complete(self, files: dict):
        """Track completed code generation."""
        self.stats["files_generated"] += len(files)

        # Log completion
        self.log("info",
                 f"✅ Generated {len(files)} files ({sum(len(content) for content in files.values())} characters)")

        # Record completion event
        self.stats["generation_events"].append({
            "timestamp": datetime.now(),
            "event": "generation_complete",
            "files": list(files.keys()),
            "total_size": sum(len(content) for content in files.values())
        })

        # Check if we should generate a report
        report_frequency = self.get_config_value("report_frequency", 5)
        if self.stats["files_generated"] % report_frequency == 0:
            self._generate_report()

    def _on_new_session(self):
        """Track new session starts."""
        self.stats["sessions"] += 1
        self.log("info", f"🆕 New session #{self.stats['sessions']} started")

    def _generate_report(self, final: bool = False):
        """Generate and log a statistics report."""
        uptime = datetime.now() - self.stats["start_time"] if self.stats["start_time"] else None

        report_type = "Final" if final else "Periodic"

        report = f"""
📊 {report_type} Code Monitor Report:
   Sessions: {self.stats['sessions']}
   Files Generated: {self.stats['files_generated']}
   Total Characters: {self.stats['total_characters']:,}
   Stream Events: {self.stats['stream_events']:,}
   Uptime: {uptime}"""

        if self.get_config_value("track_file_types", True) and self.stats["file_types"]:
            report += "\n   File Types:"
            for ext, count in sorted(self.stats["file_types"].items()):
                report += f"\n     .{ext}: {count}"

        self.log("info", report)

        # Emit as a standalone log message for visibility
        self.emit_event("log_message_received", "CodeMonitor", "info",
                        f"Generated {self.stats['files_generated']} files, {self.stats['total_characters']:,} characters")

    def get_status_info(self) -> Dict[str, Any]:
        """Get plugin status information."""
        return {
            "monitoring_active": self.state == PluginState.STARTED,
            "uptime": str(datetime.now() - self.stats["start_time"]) if self.stats["start_time"] else None,
            **self.stats
        }