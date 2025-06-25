# setup_launcher.py
import sys
from cx_Freeze import setup, Executable
from pathlib import Path

# This builds ONLY the launcher. It has no dependencies other than Python itself.

base = None
if sys.platform == "win32":
    base = "Win32GUI"

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_AVA_PATH = PROJECT_ROOT / "src" / "ava"

build_exe_options = {
    "packages": ["tkinter", "urllib", "json", "zipfile", "threading"],
    "excludes": ["PySide6", "qasync", "torch", "transformers", "sentence_transformers", "uvicorn", "chromadb", "opentelemetry", "langchain_community"],
}

executables = [
    Executable(
        str(SRC_AVA_PATH / "launcher.py"),
        base=base,
        target_name="AvakinLauncher.exe",
        icon=str(SRC_AVA_PATH / "assets" / "Ava_Icon.ico")
    )
]

setup(
    name="AvakinLauncher",
    version="1.0.0",
    description="Avakin Launcher/Updater",
    options={"build_exe": build_exe_options},
    executables=executables,
)