# setup_core.py
import sys
from cx_Freeze import setup, Executable
from pathlib import Path

# This builds the main GUI application WITHOUT the heavy RAG libraries.

base = None
if sys.platform == "win32":
    base = "Win32GUI"

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_AVA_PATH = PROJECT_ROOT / "src" / "ava"

include_files = [
    (SRC_AVA_PATH / "assets", "ava/assets"),
    (SRC_AVA_PATH / "config", "ava/config"),
    (SRC_AVA_PATH / "core" / "plugins" / "examples", "ava/core/plugins/examples"),
    (SRC_AVA_PATH / "rag_server.py", "ava/rag_server.py"),
]

build_exe_options = {
    "packages": [
        "asyncio",
        "qasync",
        "aiohttp",
        "openai",
        "google.generativeai",
        "anthropic",
        "PIL",
        "git",
        "dotenv",
        "PySide6",
        "packaging",
        "idna",
        "charset_normalizer",
    ],
    "excludes": ["tkinter", "unittest", "torch", "transformers", "sentence_transformers", "uvicorn", "chromadb", "opentelemetry", "langchain_community"],
    "include_files": include_files,
    "path": sys.path + [str(PROJECT_ROOT)],
}

executables = [
    Executable(
        str(SRC_AVA_PATH / "main.py"),
        base=base,
        target_name="Avakin.exe",
        icon=str(SRC_AVA_PATH / "assets" / "Ava_Icon.ico")
    )
]

setup(
    name="AvakinCore",
    version="1.0.1",
    description="Avakin AI Development Environment",
    options={"build_exe": build_exe_options},
    executables=executables,
)