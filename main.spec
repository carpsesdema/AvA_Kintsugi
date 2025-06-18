# main.spec
# This file tells PyInstaller how to build your application.

import sys
from pathlib import Path

# --- Setup Paths ---
# This ensures PyInstaller knows where to find your source code and data files.
project_root = Path(__file__).parent.resolve()
src_path = project_root / 'src'

# --- The Analysis ---
# This is the core part where PyInstaller analyzes your code to find all dependencies.
a = Analysis(
    # The entry point of your application
    ['src/ava/main.py'],
    # Paths where PyInstaller should look for modules
    pathex=[str(project_root), str(src_path)],
    binaries=[],
    # Bundle data files (like icons, configs, and plugins) into the executable
    datas=[
        (str(project_root / 'src/ava/assets'), 'ava/assets'),
        (str(project_root / 'config'), 'config'),
        (str(project_root / 'plugins'), 'plugins'),
        (str(project_root / 'src/ava/core/plugins/examples'), 'ava/core/plugins/examples')
    ],
    // Hidden imports for dynamically loaded modules that PyInstaller might miss
    hiddenimports=[
        'qasync',
        'qtawesome',
        'PySide6.QtSvg',
        'PySide6.QtOpenGLWidgets',
        'uvicorn',
        'fastapi',
        'anthropic',
        'google.generativeai',
        'openai',
        'chromadb',
        'sentence_transformers',
        'git',
        # Your dynamically loaded plugins!
        'ava.core.plugins.examples.living_design_agent',
        'ava.core.plugins.examples.autonomous_code_reviewer',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# --- Packaging ---
# These sections define how the collected files are bundled together.

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Kintsugi AvA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # Set to False to hide the console window on launch
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Set the application icon
    icon=str(project_root / 'src/ava/assets/Ava_Icon.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)