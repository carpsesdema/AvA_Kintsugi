# KintsugiLauncher/launcher.spec

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

# --- Main Application Entry Point ---
main_script = 'main.py'

# --- Application Name (used for the .exe) ---
app_name = 'Kintsugi_AvA_Launcher'


a = Analysis(
    [main_script],
    pathex=[],
    binaries=[],
    datas=[('launcher', 'launcher')],
    # --- THIS IS THE CRITICAL FIX ---
    # We explicitly add 'packaging.version' because PyInstaller isn't finding it automatically.
    hiddenimports=['qasync', 'requests', 'packaging', 'packaging.version'],
    # --- END OF FIX ---
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
    name=app_name,
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
    icon='../src/ava/assets/Ava_Icon.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KintsugiLauncher',
)