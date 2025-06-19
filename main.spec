# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os

block_cipher = None

# Define the root of our source code for reliable pathing.
src_root = Path('./src').resolve()
project_root = Path('.').resolve()

# Collect all plugin directories
plugin_data = []

# Built-in example plugins
builtin_plugins_src = src_root / "ava" / "core" / "plugins" / "examples"
if builtin_plugins_src.exists():
    for plugin_dir in builtin_plugins_src.iterdir():
        if plugin_dir.is_dir() and (plugin_dir / "__init__.py").exists():
            # Include each plugin directory
            plugin_data.append((str(plugin_dir), f"ava/core/plugins/examples/{plugin_dir.name}"))

# Custom plugins directory
custom_plugins_src = project_root / "plugins"
if custom_plugins_src.exists():
    for plugin_dir in custom_plugins_src.iterdir():
        if plugin_dir.is_dir() and (plugin_dir / "__init__.py").exists():
            plugin_data.append((str(plugin_dir), f"plugins/{plugin_dir.name}"))

a = Analysis(
    ['src/ava/main.py'],
    pathex=[str(project_root), str(src_root)],  # Add both paths
    binaries=[],
    datas=[
        # Core application data
        ('src/ava/assets', 'ava/assets'),
        ('src/ava/config', 'ava/config'),

        # Include all discovered plugins
        *plugin_data,
    ],
    hiddenimports=[
        # PySide6 and GUI libs
        'PySide6.QtSvg',
        'PySide6.QtGui',
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'qasync',
        'qtawesome',
        'Pygments',

        # Core libs
        'packaging',
        'packaging.version',
        'importlib.resources',
        'importlib.metadata',

        # Async and RAG libs
        'aiohttp',
        'asyncio',
        'queue',
        'threading',
        'subprocess',
        'socket',

        # Plugin system
        'ava.core.plugins.plugin_system',
        'ava.core.plugins.plugin_base',
        'ava.core.plugins.plugin_registry',
        'ava.core.plugins.plugin_manager',
        'ava.core.plugins.plugin_config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',  # Creates main.exe, as expected by the launcher
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True if you want to see console output for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/ava/assets/Ava_Icon.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main'  # The output folder will be 'dist/main'
)