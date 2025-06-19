# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

# Define the root of our source code for reliable pathing.
src_root = Path('./src').resolve()
project_root = Path('.').resolve()

a = Analysis(
    ['src/ava/main.py'],
    pathex=[str(project_root)],  # Add project root to path for plugins discovery
    binaries=[],
    datas=[
        # --- THIS IS THE FIX: Bundle all necessary non-code files ---
        # We specify ('source_path', 'destination_in_bundle')
        # This ensures that PyInstaller copies these folders into the final .exe package
        # and places them where our code expects to find them.
        ('src/ava/assets', 'ava/assets'),
        ('src/ava/config', 'src/ava/config'),
        ('src/ava/core/plugins/examples', 'ava/core/plugins/examples'),

        # Include the top-level 'plugins' directory if it exists, for custom plugins.
        ('plugins', 'plugins')
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

        # Async and RAG libs
        'aiohttp',
        'asyncio',
        'queue',
        'threading',
        'subprocess',
        'socket',
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
    name='main', # Creates main.exe, as expected by the build script
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name='main' # The output folder will be 'dist/main'
)