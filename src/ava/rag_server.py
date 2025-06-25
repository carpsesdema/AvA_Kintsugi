# rag_server.py

import os
import sys
import logging  # NEW: Import logging
from logging.handlers import RotatingFileHandler  # NEW: For log rotation
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import chromadb
from sentence_transformers import SentenceTransformer
import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager

# --- Early Diagnostic Import for Pillow ---
try:
    from PIL import Image

    print("[RAGServer Pre-Check] Pillow (PIL.Image) imported successfully.")
except ImportError as e:
    print(f"[RAGServer Pre-Check] ERROR: Could not import Pillow (PIL.Image). Error: {e}", file=sys.stderr)
    # Log to file if logger is set up, otherwise print to stderr
    if 'rag_logger' in globals():
        rag_logger.error(f"FATAL: Could not import Pillow (PIL.Image). Error: {e}", exc_info=True)
    sys.exit(1)

# --- NEW: Setup Detailed File Logging for RAG Server ---
log_file_path = Path(sys.executable).parent / "rag_server_debug.log" if getattr(sys, 'frozen', False) else Path(
    __file__).parent / "rag_server_debug.log"
rag_logger = logging.getLogger("RAGServer")
rag_logger.setLevel(logging.DEBUG)  # Capture all levels of detail
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# File Handler
try:
    fh = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=2, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    rag_logger.addHandler(fh)
except Exception as e:
    print(f"CRITICAL: Failed to set up RAG server file logger at {log_file_path}: {e}", file=sys.stderr)

# Console Handler (for development, might be less visible in bundled app)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)  # Be less verbose on console by default
ch.setFormatter(formatter)
rag_logger.addHandler(ch)

rag_logger.info(f"RAG Server logging initialized. Log file: {log_file_path}")
# --- END NEW LOGGING SETUP ---


# --- Configuration ---
PERSIST_DIRECTORY = "rag_db"
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


# --- Global State (loaded once on startup) ---
app_state = {}


# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events using the modern
    FastAPI lifespan protocol.
    """
    # --- Startup Logic ---
    rag_logger.info("--- RAG Server Startup (Lifespan) ---")
    rag_logger.info(f"Loading embedding model: '{MODEL_NAME}' into memory...")
    try:
        app_state["embedding_model"] = SentenceTransformer(MODEL_NAME)
        rag_logger.info("Embedding model loaded successfully.")
    except Exception as e:
        rag_logger.error(f"FATAL: Could not load embedding model. Error: {e}", exc_info=True)
        app_state["embedding_model"] = None

    # Determine persist directory path. When bundled, CWD is the dist root.
    # When run from source, CWD is project root (AvA_Kintsugi).
    # We want rag_db to be in the same dir as the exe when bundled,
    # or in the project root when run from source.
    # ServiceManager sets CWD to dist root for bundled, or repo root for source.
    # So, relative path "rag_db" should work.
    persist_path = Path(PERSIST_DIRECTORY).resolve()
    rag_logger.info(f"Attempting to connect to ChromaDB at: '{persist_path}' (resolved from '{PERSIST_DIRECTORY}')")
    try:
        # Ensure the directory exists or can be created by ChromaDB
        persist_path.parent.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_path))
        app_state["collection"] = client.get_or_create_collection(name=COLLECTION_NAME)
        rag_logger.info(f"ChromaDB connection successful to '{persist_path}'.")
    except Exception as e:
        rag_logger.error(f"FATAL: Could not connect to/create ChromaDB at '{persist_path}'. Error: {e}", exc_info=True)
        app_state["collection"] = None

    rag_logger.info(f"--- RAG Server is now ready and listening on http://{HOST}:{PORT} ---")

    yield  # The application runs here

    # --- Shutdown Logic ---
    rag_logger.info("--- RAG Server Shutdown (Lifespan) ---")
    app_state.clear()
    rag_logger.info("Cleaned up resources.")


# --- FastAPI App Initialization (with the new lifespan handler) ---
rag_app = FastAPI(title="Kintsugi AvA RAG Service", lifespan=lifespan)


# --- API Endpoints ---
@rag_app.get("/")
def read_root():
    return {"status": "Kintsugi RAG Server is running"}


@rag_app.post("/add")
def add_documents(request: AddRequest):
    if not app_state.get("embedding_model") or not app_state.get("collection"):
        rag_logger.error("/add endpoint called but service is not initialized.")
        raise HTTPException(status_code=503, detail="RAG service is not initialized or has failed.")

    embedding_model = app_state["embedding_model"]
    collection = app_state["collection"]
    docs = request.documents

    if not docs:
        rag_logger.info("/add received no documents.")
        return {"status": "success", "message": "No documents provided to add."}

    rag_logger.info(f"Received request to add {len(docs)} document chunks.")

    try:
        # Prepare data for ChromaDB
        ids = [doc.id for doc in docs]
        contents = [doc.content for doc in docs]
        metadatas = [doc.metadata for doc in docs]

        # Embed all contents in a batch for efficiency
        rag_logger.debug("Embedding document chunks...")
        embeddings = embedding_model.encode(contents).tolist()
        rag_logger.debug("Embedding complete.")

        # Add to the collection
        collection.add(
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
            ids=ids
        )
        rag_logger.info(f"Successfully added {len(docs)} chunks to the collection '{COLLECTION_NAME}'.")
        return {"status": "success", "message": f"Added {len(docs)} documents."}

    except Exception as e:
        rag_logger.error(f"ERROR during document addition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during document addition: {e}")


@rag_app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest) -> QueryResponse:
    if not app_state.get("embedding_model") or not app_state.get("collection"):
        rag_logger.error("/query endpoint called but service is not initialized.")
        raise HTTPException(status_code=503, detail="RAG service is not initialized or has failed. Check server logs.")

    try:
        rag_logger.info(f"Received query: '{request.query_text[:50]}...', n_results={request.n_results}")
        embedding_model = app_state["embedding_model"]
        collection = app_state["collection"]
        query_embedding = embedding_model.encode(request.query_text).tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=request.n_results
        )
        documents = results.get('documents', [[]])[0]
        if not documents:
            rag_logger.info(f"Query for '{request.query_text[:50]}...' yielded no relevant documents.")
            return QueryResponse(context="No relevant documents found in the knowledge base.")

        context_str = ""
        for i, doc in enumerate(documents):
            context_str += f"--- Relevant Document Snippet {i + 1} ---\n"
            context_str += doc
            context_str += "\n\n"

        rag_logger.info(f"Returning {len(documents)} snippets for query '{request.query_text[:50]}...'.")
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