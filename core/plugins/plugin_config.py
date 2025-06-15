# kintsugi_ava/core/plugins/plugin_config.py
# Plugin configuration management

import json
from pathlib import Path
from typing import Dict, Any, Optional, Set
from copy import deepcopy

from .plugin_system import PluginMetadata


class PluginConfig:
    """
    Manages plugin configuration persistence and validation.
    Single responsibility: Handle plugin configuration storage and retrieval.
    """

    def __init__(self, config_file_path: str = "config/plugins.json"):
        self.config_file = Path(config_file_path)
        self.config_file.parent.mkdir(exist_ok=True)

        # Configuration structure:
        # {
        #   "enabled_plugins": ["plugin1", "plugin2"],
        #   "plugin_settings": {
        #     "plugin1": {"setting1": "value1"},
        #     "plugin2": {"setting2": "value2"}
        #   }
        # }
        self._config_data: Dict[str, Any] = {
            "enabled_plugins": [],
            "plugin_settings": {}
        }

        self._load_config()
        print(f"[PluginConfig] Initialized with config file: {self.config_file}")

    def _load_config(self):
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)

                # Validate and merge loaded data
                if isinstance(loaded_data, dict):
                    if "enabled_plugins" in loaded_data and isinstance(loaded_data["enabled_plugins"], list):
                        self._config_data["enabled_plugins"] = loaded_data["enabled_plugins"]

                    if "plugin_settings" in loaded_data and isinstance(loaded_data["plugin_settings"], dict):
                        self._config_data["plugin_settings"] = loaded_data["plugin_settings"]

                print(f"[PluginConfig] Loaded configuration from {self.config_file}")
            else:
                print(f"[PluginConfig] No existing config file found. Using defaults.")

        except Exception as e:
            print(f"[PluginConfig] Error loading config file: {e}. Using defaults.")

    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=2)
            print(f"[PluginConfig] Saved configuration to {self.config_file}")
        except Exception as e:
            print(f"[PluginConfig] Error saving config file: {e}")

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """
        Check if a plugin is enabled.

        Args:
            plugin_name: Name of the plugin to check

        Returns:
            True if plugin is enabled, False otherwise
        """
        return plugin_name in self._config_data["enabled_plugins"]

    def enable_plugin(self, plugin_name: str):
        """
        Enable a plugin.

        Args:
            plugin_name: Name of the plugin to enable
        """
        if plugin_name not in self._config_data["enabled_plugins"]:
            self._config_data["enabled_plugins"].append(plugin_name)
            print(f"[PluginConfig] Enabled plugin: {plugin_name}")

    def disable_plugin(self, plugin_name: str):
        """
        Disable a plugin.

        Args:
            plugin_name: Name of the plugin to disable
        """
        if plugin_name in self._config_data["enabled_plugins"]:
            self._config_data["enabled_plugins"].remove(plugin_name)
            print(f"[PluginConfig] Disabled plugin: {plugin_name}")

    def get_enabled_plugins(self) -> Set[str]:
        """
        Get set of all enabled plugin names.

        Returns:
            Set of enabled plugin names
        """
        return set(self._config_data["enabled_plugins"])

    def set_enabled_plugins(self, plugin_names: Set[str]):
        """
        Set the complete list of enabled plugins.

        Args:
            plugin_names: Set of plugin names to enable
        """
        self._config_data["enabled_plugins"] = list(plugin_names)
        print(f"[PluginConfig] Set enabled plugins: {plugin_names}")

    def get_plugin_settings(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get settings for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dictionary of plugin settings (empty dict if no settings)
        """
        return deepcopy(self._config_data["plugin_settings"].get(plugin_name, {}))

    def set_plugin_setting(self, plugin_name: str, setting_key: str, value: Any):
        """
        Set a specific setting for a plugin.

        Args:
            plugin_name: Name of the plugin
            setting_key: Setting key to set
            value: Value to set
        """
        if plugin_name not in self._config_data["plugin_settings"]:
            self._config_data["plugin_settings"][plugin_name] = {}

        self._config_data["plugin_settings"][plugin_name][setting_key] = value
        print(f"[PluginConfig] Set {plugin_name}.{setting_key} = {value}")

    def get_plugin_setting(self, plugin_name: str, setting_key: str, default=None) -> Any:
        """
        Get a specific setting for a plugin.

        Args:
            plugin_name: Name of the plugin
            setting_key: Setting key to get
            default: Default value if setting not found

        Returns:
            Setting value or default
        """
        plugin_settings = self._config_data["plugin_settings"].get(plugin_name, {})
        return plugin_settings.get(setting_key, default)

    def set_plugin_settings(self, plugin_name: str, settings: Dict[str, Any]):
        """
        Set all settings for a plugin.

        Args:
            plugin_name: Name of the plugin
            settings: Dictionary of settings to set
        """
        self._config_data["plugin_settings"][plugin_name] = deepcopy(settings)
        print(f"[PluginConfig] Set all settings for {plugin_name}")

    def remove_plugin_settings(self, plugin_name: str):
        """
        Remove all settings for a plugin.

        Args:
            plugin_name: Name of the plugin
        """
        if plugin_name in self._config_data["plugin_settings"]:
            del self._config_data["plugin_settings"][plugin_name]
            print(f"[PluginConfig] Removed all settings for {plugin_name}")

    def validate_plugin_settings(self, plugin_name: str, metadata: PluginMetadata) -> Dict[str, Any]:
        """
        Validate plugin settings against the plugin's schema.

        Args:
            plugin_name: Name of the plugin
            metadata: Plugin metadata containing schema

        Returns:
            Dictionary of validated settings (with defaults applied)
        """
        current_settings = self.get_plugin_settings(plugin_name)
        validated_settings = {}

        # If no schema is defined, return current settings as-is
        if not metadata.config_schema:
            return current_settings

        # Validate each setting in the schema
        for setting_key, schema_info in metadata.config_schema.items():
            if isinstance(schema_info, dict):
                default_value = schema_info.get("default")
                setting_type = schema_info.get("type")

                # Get current value or default
                current_value = current_settings.get(setting_key, default_value)

                # Basic type validation
                if setting_type and current_value is not None:
                    try:
                        if setting_type == "str":
                            validated_settings[setting_key] = str(current_value)
                        elif setting_type == "int":
                            validated_settings[setting_key] = int(current_value)
                        elif setting_type == "float":
                            validated_settings[setting_key] = float(current_value)
                        elif setting_type == "bool":
                            validated_settings[setting_key] = bool(current_value)
                        else:
                            validated_settings[setting_key] = current_value
                    except (ValueError, TypeError):
                        print(f"[PluginConfig] Invalid type for {plugin_name}.{setting_key}, using default")
                        validated_settings[setting_key] = default_value
                else:
                    validated_settings[setting_key] = current_value
            else:
                # Simple schema format - just a default value
                validated_settings[setting_key] = current_settings.get(setting_key, schema_info)

        return validated_settings

    def apply_defaults_for_plugin(self, plugin_name: str, metadata: PluginMetadata):
        """
        Apply default settings for a plugin if they don't exist.

        Args:
            plugin_name: Name of the plugin
            metadata: Plugin metadata containing default settings
        """
        if not metadata.config_schema:
            return

        current_settings = self.get_plugin_settings(plugin_name)
        updated = False

        for setting_key, schema_info in metadata.config_schema.items():
            if setting_key not in current_settings:
                if isinstance(schema_info, dict):
                    default_value = schema_info.get("default")
                else:
                    default_value = schema_info

                if default_value is not None:
                    self.set_plugin_setting(plugin_name, setting_key, default_value)
                    updated = True

        if updated:
            print(f"[PluginConfig] Applied default settings for {plugin_name}")

    def enable_plugins_by_default(self, all_metadata: Dict[str, PluginMetadata]):
        """
        Enable plugins that should be enabled by default.

        Args:
            all_metadata: Dictionary of all plugin metadata
        """
        for plugin_name, metadata in all_metadata.items():
            if metadata.enabled_by_default and not self.is_plugin_enabled(plugin_name):
                self.enable_plugin(plugin_name)
                print(f"[PluginConfig] Auto-enabled plugin: {plugin_name}")

    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current configuration.

        Returns:
            Dictionary containing configuration summary
        """
        return {
            "enabled_plugins_count": len(self._config_data["enabled_plugins"]),
            "enabled_plugins": list(self._config_data["enabled_plugins"]),
            "configured_plugins_count": len(self._config_data["plugin_settings"]),
            "configured_plugins": list(self._config_data["plugin_settings"].keys())
        }