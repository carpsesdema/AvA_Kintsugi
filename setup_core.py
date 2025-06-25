# setup_core.py
import sys
from cx_Freeze import setup, Executable
from pathlib import Path

# This builds the main GUI application WITHOUT ANY of the heavy AI/LLM libraries.
# All complex dependencies are handled by a private venv created by build_dist.py

base = None
if sys.platform == "win32":
    base = "Win32GUI"

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
SRC_AVA_PATH = SRC_PATH / "ava"

include_files = [
    (SRC_AVA_PATH / "assets", "ava/assets"),
    (SRC_AVA_PATH / "config", "ava/config"),
    (SRC_AVA_PATH / "core" / "plugins" / "examples", "ava/core/plugins/examples"),
    # The server scripts that will be launched by the private python env
    (SRC_AVA_PATH / "rag_server.py", "ava/rag_server.py"),
    (SRC_AVA_PATH / "llm_server.py", "ava/llm_server.py"),
]

# Minimal packages for the GUI application
packages_to_include = [
    "asyncio",
    "qasync",
    "aiohttp", # For communicating with the local servers
    "PySide6",
    "packaging",
    "qtawesome",
    "pygments",
    "unidiff",
    "git", # <-- ADDED BACK: ProjectManager needs this for core functionality
]

# Exclude ALL potentially problematic packages from the main build
packages_to_exclude = [
    "tkinter", "unittest", "torch", "transformers", "sentence_transformers",
    "uvicorn", "chromadb", "opentelemetry", "langchain_community", "fastapi",
    "h11", "httptools", "openai", "google", "anthropic", "dotenv"
]

build_exe_options = {
    "packages": packages_to_include,
    "excludes": packages_to_exclude,
    "include_files": include_files,
    "path": sys.path + [str(SRC_PATH)],
    "zip_include_packages": ["*"],
    "zip_exclude_packages": ["qtawesome"],
}

executables = [
    Executable(
        "src/ava/main.py",
        base=base,
        target_name="Avakin.exe",
        icon=str(SRC_AVA_PATH / "assets" / "Ava_Icon.ico")
    )
]

setup(
    name="Avakin",
    version="1.0.1",
    description="Avakin AI Development Environment",
    options={"build_exe": build_exe_options},
    executables=executables,
)