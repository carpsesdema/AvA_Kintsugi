# KintsugiLauncher/launcher.spec
# -*- mode: python ; coding: utf-8 -*-

# This spec file is optimized for the release of the Avakin Launcher.
# It ensures all assets are bundled and the final executable is a clean, GUI-only application.

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['main.py'],  # The launcher's main entry point
    pathex=['.'], # The root is the KintsugiLauncher directory where this spec resides
    binaries=[],
    datas=[
        # This line ensures your launcher's icon is included in the build.
        ('launcher/assets', 'assets'),
        # This explicitly collects the qtawesome font files, guaranteeing icons will work.
        *collect_data_files('qtawesome'),
    ],
    hiddenimports=[
        # GUI libraries
        'PySide6.QtSvg',
        'PySide6.QtGui',
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'qasync',
        'qtawesome',

        # Networking and utilities
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
    name='Avakin Launcher',  # The name of the final .exe file
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # --- CRITICAL FIX for RELEASE ---
    # This ensures no console window appears behind your GUI.
    console=False,
    # --------------------------------
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # The icon for the executable itself.
    icon='launcher/assets/Launcher_Icon.ico'
)

# This creates the final output folder in 'dist/'
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    # The output folder name must match what build_launcher.py expects.
    name='AvakinLauncher'
)