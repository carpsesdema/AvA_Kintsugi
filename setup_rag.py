# setup_rag.py
import sys
from cx_Freeze import setup, Executable
from pathlib import Path

# This builds ONLY the RAG server into its own executable.
# It's a console application, so no GUI base.

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_AVA_PATH = PROJECT_ROOT / "src" / "ava"

# We use the "include and exclude" strategy here for the difficult packages
build_exe_options = {
    # 1. We tell cx_Freeze to bundle these entire packages.
    "packages": [
        "uvicorn",
        "sentence_transformers",
        "transformers",
        "torch",
        "chromadb",
        "langchain_community",
        "opentelemetry",
        "fastapi",
    ],
    # 2. We ALSO tell cx_Freeze to NOT try to analyze their internal imports.
    # This prevents the RecursionError.
    "excludes": [
        "tkinter",
        "unittest",
        "PySide6",
        "qasync",
        "openai",
        "google",
        "anthropic",
        "git",
        "dotenv",
        "torch.distributions" # Specifically exclude the submodule that causes recursion
    ],
    "path": sys.path + [str(PROJECT_ROOT)],
}

executables = [
    Executable(
        str(SRC_AVA_PATH / "rag_server.py"),
        base=None, # This is a console app, so no Win32GUI
        target_name="rag_server.exe",
    )
]

setup(
    name="AvakinRAGServer",
    version="1.0.1",
    description="Avakin RAG Server",
    options={"build_exe": build_exe_options},
    executables=executables,
)