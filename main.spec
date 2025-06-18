# main.spec

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

# <<< FIX: Explicitly define the src_root for robust pathing >>>
# This makes it clear where our source and data files are located.
src_root = Path('./src').resolve()

a = Analysis(
    ['src/ava/main.py'],
    # <<< FIX: Use the resolved src_root for reliability >>>
    pathex=[str(src_root)],
    binaries=[],
    datas=[
        # --- Bundle all necessary non-code files ---
        ('src/ava/assets', 'ava/assets'),
        ('src/ava/rag_server.py', '.'), # Place in root of build for simplicity
        ('src/ava/requirements_rag.txt', '.'),

        # <<< FIX: Correctly include the config and plugins folders >>>
        # The original was missing these, which caused the plugin system to fail.
        ('src/ava/config', 'config'),
        ('src/ava/core/plugins/examples', 'ava/core/plugins/examples'),
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