# KintsugiLauncher/launcher.spec
# -*- mode: python ; coding: utf-8 -*-

# This spec file is built to match the project structure where the 'assets'
# folder is located inside the 'launcher' sub-directory.

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['main.py'],  # Entry point is main.py in the root. Correct.
    pathex=['.'], # Search path is the root directory. Correct.
    binaries=[],
    datas=[
        # Source: 'launcher/assets' (relative to this spec file).
        # Destination: 'assets' (the top-level folder inside the build).
        # This is what your gui.py code expects. This is correct.
        ('launcher/assets', 'assets'),

        # This ensures qtawesome icons are always included. Correct.
        *collect_data_files('qtawesome'),
    ],
    hiddenimports=[
        'PySide6.QtSvg',
        'PySide6.QtGui',
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'qasync',
        'qtawesome',
        'requests',
        'packaging',
        'packaging.version'
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
    name='Avakin Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # This creates a windowed app with no console. Correct.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # The path to the icon, relative to this spec file. Correct.
    icon='launcher/assets/Launcher_Icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AvakinLauncher'
)