# src/ava/core/plugins/plugin_config.py
# Plugin configuration management

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Set
from copy import deepcopy

from src.ava.core.plugins.plugin_system import PluginMetadata


class PluginConfig:
    """
    Manages plugin configuration persistence and validation.
    Single responsibility: Handle plugin configuration storage and retrieval.
    """

    def __init__(self, project_root: Path):
        # --- THIS IS THE FIX ---
        # Use the passed 'project_root' to determine the config directory.
        # This 'project_root' is intelligently set by main.py to be
        # the correct base path whether running from source or bundled.
        config_dir = project_root / "ava" / "config"
        self.config_file = config_dir / "plugins.json"
        # --- END OF FIX ---

        self.config_file.parent.mkdir(exist_ok=True, parents=True)

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
            plugin_name: Name of the plugin

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

    def get_plugin_settings(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get settings for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin settings dictionary (may be empty)
        """
        return self._config_data["plugin_settings"].get(plugin_name, {})

    def update_plugin_settings(self, plugin_name: str, settings: Dict[str, Any]):
        """
        Update settings for a specific plugin.

        Args:
            plugin_name: Name of the plugin
            settings: New settings dictionary
        """
        self._config_data["plugin_settings"][plugin_name] = deepcopy(settings)
        print(f"[PluginConfig] Updated settings for plugin: {plugin_name}")

    def get_enabled_plugins(self) -> Set[str]:
        """
        Get the set of enabled plugin names.

        Returns:
            Set of enabled plugin names
        """
        return set(self._config_data["enabled_plugins"])

    def validate_plugin_settings(self, plugin_name: str, metadata: PluginMetadata) -> Dict[str, Any]:
        """
        Validate and return plugin settings against schema.

        Args:
            plugin_name: Name of the plugin
            metadata: Plugin metadata containing config schema

        Returns:
            Validated settings dictionary with defaults applied
        """
        current_settings = self.get_plugin_settings(plugin_name)
        validated_settings = {}
        type_map = {'bool': bool, 'int': int, 'str': str, 'float': float}

        # Apply schema defaults and validate
        for key, schema_info in metadata.config_schema.items():
            default_value = schema_info.get("default")

            if key in current_settings:
                user_value = current_settings[key]
                expected_type_str = schema_info.get("type")
                expected_type = type_map.get(expected_type_str)

                # If type is valid, use the user's value.
                if expected_type and isinstance(user_value, expected_type):
                    validated_settings[key] = user_value
                else:
                    # If type is invalid, log a warning and use the default.
                    print(f"[PluginConfig] Warning: Invalid type for '{key}' in '{plugin_name}' settings. "
                          f"Expected {expected_type_str}, got {type(user_value).__name__}. "
                          f"Using default value: {default_value}")
                    validated_settings[key] = default_value

            elif "default" in schema_info:
                # If the user hasn't set a value, use the default.
                validated_settings[key] = default_value

        return validated_settings

    def apply_defaults_for_plugin(self, plugin_name: str, metadata: PluginMetadata):
        """
        Apply default settings for a newly discovered plugin.

        Args:
            plugin_name: Name of the plugin
            metadata: Plugin metadata
        """
        if plugin_name not in self._config_data["plugin_settings"]:
            default_settings = {}
            for key, schema_info in metadata.config_schema.items():
                if "default" in schema_info:
                    default_settings[key] = schema_info["default"]

            if default_settings:
                self._config_data["plugin_settings"][plugin_name] = default_settings
                print(f"[PluginConfig] Applied default settings for new plugin: {plugin_name}")

    def enable_plugins_by_default(self, all_metadata: Dict[str, PluginMetadata]):
        """
        Enable plugins that should be enabled by default.

        Args:
            all_metadata: Dictionary of all plugin metadata
        """
        for plugin_name, metadata in all_metadata.items():
            if metadata.enabled_by_default and plugin_name not in self._config_data["enabled_plugins"]:
                self.enable_plugin(plugin_name)