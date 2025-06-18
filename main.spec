# main.spec

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

a = Analysis(
    ['src/ava/main.py'],  # Make sure this points to your main entry script
    pathex=['src'],  # Tell PyInstaller to look for imports in the 'src' directory
    binaries=[],
    datas=[('src/ava/assets', 'ava/assets')],  # Correctly bundle the assets folder
    hiddenimports=['PySide6.QtSvg', 'qasync', 'qtawesome'],
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
    # --- THIS IS THE REAL, FINAL FIX ---
    # We change the name of the output .exe file right here.
    name='main',
    # --- END OF FIX ---
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
    icon='src/ava/assets/Ava_Icon.ico' # Corrected path to icon
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main' # The output folder will now also be 'main'
)