# rag_server.py

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Dict, Any

# --- Setup Logging First ---
# This ensures the logger is available for the rest of the script, especially for catching import errors.
log_file_path = Path(sys.executable).parent / "rag_server_debug.log" if getattr(sys, 'frozen', False) else Path(
    __file__).parent / "rag_server_debug.log"
rag_logger = logging.getLogger("RAGServer")
rag_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

try:
    fh = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=2, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    rag_logger.addHandler(fh)
except Exception as e:
    print(f"CRITICAL: Failed to set up RAG server file logger at {log_file_path}: {e}", file=sys.stderr)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
rag_logger.addHandler(ch)

rag_logger.info(f"RAG Server logging initialized. Log file: {log_file_path}")
# --- End Logging Setup ---


# --- Import Third-Party Libraries ---
# Now we can safely log any import errors.
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    import chromadb
    from sentence_transformers import SentenceTransformer
    import uvicorn
    from PIL import Image
except ImportError as e:
    rag_logger.critical(f"Failed to import a critical third-party library: {e}", exc_info=True)
    sys.exit(1)

# --- Configuration ---
PERSIST_DIRECTORY_NAME = "rag_db"
MODEL_NAME = 'all-miniLM-L6-v2'
COLLECTION_NAME = "kintsugi_kb"
HOST = "127.0.0.1"
PORT = 8001


# --- Data Models for FastAPI ---
class QueryRequest(BaseModel):
    query_text: str
    n_results: int = 5


class QueryResponse(BaseModel):
    context: str


class Document(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AddRequest(BaseModel):
    documents: List[Document]


class SetCollectionRequest(BaseModel):
    project_path: str


# --- Global State ---
app_state = {}


# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    rag_logger.info("--- RAG Server Startup (Lifespan) ---")
    rag_logger.info(f"Loading embedding model: '{MODEL_NAME}' into memory...")
    try:
        app_state["embedding_model"] = SentenceTransformer(MODEL_NAME)
        rag_logger.info("Embedding model loaded successfully.")
    except Exception as e:
        rag_logger.error(f"FATAL: Could not load embedding model. Error: {e}", exc_info=True)
        app_state["embedding_model"] = None
    app_state["collection"] = None
    rag_logger.info("--- RAG Server is now ready and listening ---")
    yield
    rag_logger.info("--- RAG Server Shutdown (Lifespan) ---")
    app_state.clear()
    rag_logger.info("Cleaned up resources.")


# --- FastAPI App Initialization ---
rag_app = FastAPI(title="Kintsugi AvA RAG Service", lifespan=lifespan)


# --- API Endpoints ---
@rag_app.post("/set_collection")
def set_collection(request: SetCollectionRequest):
    project_path_str = request.project_path
    if not project_path_str or not Path(project_path_str).is_dir():
        rag_logger.error(f"/set_collection called with invalid path: {project_path_str}")
        raise HTTPException(status_code=400,
                            detail=f"Invalid or non-existent project path provided: {project_path_str}")

    persist_path = Path(project_path_str) / PERSIST_DIRECTORY_NAME
    rag_logger.info(f"Switching RAG context. New DB path: '{persist_path}'")
    try:
        persist_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_path))
        app_state["collection"] = client.get_or_create_collection(name=COLLECTION_NAME)
        rag_logger.info(
            f"ChromaDB connection successful. Active collection is now for project: {Path(project_path_str).name}")
        return {"status": "success", "message": f"Collection set to project: {Path(project_path_str).name}"}
    except Exception as e:
        rag_logger.error(f"FATAL: Could not connect to/create ChromaDB at '{persist_path}'. Error: {e}", exc_info=True)
        app_state["collection"] = None
        raise HTTPException(status_code=500, detail=f"Failed to initialize ChromaDB collection at {persist_path}")


@rag_app.get("/")
def read_root():
    return {"status": "Kintsugi RAG Server is running"}


@rag_app.post("/add")
def add_documents(request: AddRequest):
    if not app_state.get("collection"):
        rag_logger.error("/add endpoint called but no collection is active. Use /set_collection first.")
        raise HTTPException(status_code=503, detail="No active RAG collection. Please set a project context first.")

    embedding_model = app_state.get("embedding_model")
    if not embedding_model:
        raise HTTPException(status_code=503, detail="Embedding model not loaded.")

    collection = app_state["collection"]
    docs = request.documents
    if not docs:
        return {"status": "success", "message": "No documents provided to add."}

    try:
        ids = [doc.id for doc in docs]
        contents = [doc.content for doc in docs]
        metadatas = [doc.metadata for doc in docs]
        embeddings = embedding_model.encode(contents).tolist()
        collection.add(embeddings=embeddings, documents=contents, metadatas=metadatas, ids=ids)
        rag_logger.info(f"Successfully added {len(docs)} chunks to the active collection.")
        return {"status": "success", "message": f"Added {len(docs)} documents."}
    except Exception as e:
        rag_logger.error(f"ERROR during document addition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during document addition: {e}")


@rag_app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest) -> QueryResponse:
    if not app_state.get("collection"):
        rag_logger.error("/query endpoint called but no collection is active.")
        return QueryResponse(
            context="No knowledge base is active for the current project. Please load a project and scan documents.")

    embedding_model = app_state.get("embedding_model")
    if not embedding_model:
        raise HTTPException(status_code=503, detail="Embedding model not loaded.")

    try:
        collection = app_state["collection"]
        query_embedding = embedding_model.encode(request.query_text).tolist()
        results = collection.query(query_embeddings=[query_embedding], n_results=request.n_results)
        documents = results.get('documents', [[]])[0]
        if not documents:
            return QueryResponse(context="No relevant documents found in the knowledge base for this project.")
        context_str = "\n\n".join(
            f"--- Relevant Document Snippet {i + 1} ---\n{doc}" for i, doc in enumerate(documents))
        return QueryResponse(context=context_str.strip())
    except Exception as e:
        rag_logger.error(f"ERROR during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during the query: {e}")


if __name__ == "__main__":
    try:
        rag_logger.info("Starting RAG server directly with Uvicorn...")
        uvicorn.run(rag_app, host=HOST, port=PORT)
    except Exception as e:
        rag_logger.critical(f"Failed to start RAG server: {e}", exc_info=True)
        sys.exit(1)