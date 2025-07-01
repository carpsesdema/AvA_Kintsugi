# src/ava/core/plugins/examples/godot/godot_game_dev.py
from src.ava.core.plugins.plugin_system import PluginBase, PluginMetadata
from src.ava.prompts.godot import GODOT_ARCHITECT_PROMPT

class GodotGameDevPlugin(PluginBase):
    """
    A plugin that enables Avakin to generate Godot game projects.
    It intercepts build requests when the project type is set to 'Godot'
    and uses specialized prompts for Godot's architecture and GDScript.
    """
    def __init__(self, event_bus, plugin_config):
        super().__init__(event_bus, plugin_config)
        self.service_manager = None
        self.task_manager = None
        self.workflow_manager = None
        self.active_project_type = "Python"

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Godot Game Dev",
            version="1.0.2",
            description="Enables Avakin to generate Godot game files (GDScript, scenes).",
            author="Avakin",
            enabled_by_default=True
        )

    async def load(self) -> bool:
        self.log("info", f"{self.metadata.name} loaded.")
        return True

    async def start(self) -> bool:
        self.emit_event("plugin_requesting_managers", self.receive_managers)
        self.subscribe_to_event("user_build_request_intercepted", self.handle_user_request_override)
        self.subscribe_to_event("project_type_changed", self.on_project_type_changed)
        self.log("info", f"{self.metadata.name} started. Select 'Godot' from the dropdown to generate a game.")
        self.set_state(self.state.STARTED)
        return True

    def receive_managers(self, service_manager, task_manager, workflow_manager):
        self.service_manager = service_manager
        self.task_manager = task_manager
        self.workflow_manager = workflow_manager
        self.log("info", "Successfully received core manager instances.")

    def on_project_type_changed(self, new_type: str):
        self.log("info", f"Project type changed to: {new_type}")
        self.active_project_type = new_type

    async def stop(self) -> bool:
        self.log("info", f"{self.metadata.name} stopped.")
        self.set_state(self.state.STOPPED)
        return True

    async def unload(self) -> bool:
        return True

    async def handle_user_request_override(self, prompt: str):
        """
        This method intercepts the user's request and, if the project type is 'Godot',
        it takes over the build process from the default WorkflowManager.
        """
        if self.active_project_type != "Godot":
            return  # Do nothing if not in Godot mode

        self.log("info", "Godot project type is active. Intercepting build process.")

        # Signal to the WorkflowManager that a plugin is handling this build
        if self.workflow_manager:
            self.emit_event("plugin_build_override_activated")

        if not self.service_manager or not self.task_manager:
            self.log("error", "Cannot start Godot build: Core managers not available.")
            return

        architect_service = self.service_manager.get_architect_service()
        if not architect_service:
            self.log("error", "ArchitectService not found.")
            return

        # Use the Architect service with our custom Godot prompt
        build_coroutine = architect_service.generate_or_modify(
            prompt=prompt,
            existing_files=None,  # For now, we only support new Godot projects
            custom_prompts={
                "architect": GODOT_ARCHITECT_PROMPT
            }
        )
        self.task_manager.start_ai_workflow_task(build_coroutine)