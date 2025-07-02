# src/ava/core/plugins/examples/unreal/unreal_cpp_dev.py
from src.ava.core.plugins.plugin_system import PluginBase, PluginMetadata

class UnrealCppDevPlugin(PluginBase):
    """
    A simple plugin whose only job is to be discovered by the system,
    allowing "Unreal C++" to be a selectable project type. The core logic
    for handling this project type is now in the WorkflowManager.
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Unreal C++ Dev",
            version="1.1.0",
            description="Enables Avakin to generate Unreal Engine C++ projects.",
            author="Avakin",
            enabled_by_default=True
        )

    async def load(self) -> bool:
        self.log("info", f"{self.metadata.name} loaded.")
        return True

    async def start(self) -> bool:
        self.log("info", f"{self.metadata.name} started. The WorkflowManager will now handle Unreal C++ builds.")
        self.set_state(self.state.STARTED)
        return True

    async def stop(self) -> bool:
        self.log("info", f"{self.metadata.name} stopped.")
        self.set_state(self.state.STOPPED)
        return True

    async def unload(self) -> bool:
        return True