# rag_server.py

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

# --- Setup Logging First ---
log_file_path = Path(sys.executable).parent / "rag_server_debug.log" if getattr(sys, 'frozen', False) else Path(
    __file__).parent / "rag_server_debug.log"
rag_logger = logging.getLogger("RAGServer")
rag_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

try:
    # Ensure the log directory exists
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=2, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    rag_logger.addHandler(fh)
except Exception as e:
    # Fallback to console if file logging fails
    print(f"CRITICAL: Failed to set up RAG server file logger at {log_file_path}: {e}", file=sys.stderr)
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    rag_logger = logging.getLogger("RAGServer")  # Re-get logger if basicConfig was used

ch = logging.StreamHandler(sys.stdout)  # Always add stream handler for console visibility
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
rag_logger.addHandler(ch)

rag_logger.info(f"RAG Server logging initialized. Log file: {log_file_path}")
# --- End Logging Setup ---


# --- Import Third-Party Libraries ---
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    import chromadb
    from sentence_transformers import SentenceTransformer
    import uvicorn
except ImportError as e:
    rag_logger.critical(f"Failed to import a critical third-party library: {e}", exc_info=True)
    sys.exit(1)

# --- Configuration ---
PERSIST_DIRECTORY_NAME = "rag_db"
MODEL_NAME = 'all-miniLM-L6-v2'
PROJECT_COLLECTION_NAME = "kintsugi_project_kb"
GLOBAL_COLLECTION_NAME = "kintsugi_global_python_kb"
HOST = "127.0.0.1"
PORT = 8001


# --- Data Models for FastAPI ---
class QueryRequest(BaseModel):
    query_text: str
    n_results: int = 5
    target_collection: Optional[str] = "project"


class QueryResponse(BaseModel):
    context: str
    source_collection: str


class Document(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AddRequest(BaseModel):
    documents: List[Document]
    target_collection: Optional[str] = "project"


class SetCollectionRequest(BaseModel):
    project_path: str


# --- Global State ---
app_state = {
    "embedding_model": None,
    "project_collection": None,
    "global_collection": None,
    "chroma_client_project": None,
    "chroma_client_global": None
}


# --- Lifespan Event Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    rag_logger.info("--- RAG Server Startup (Lifespan) ---")
    rag_logger.info(f"Loading embedding model: '{MODEL_NAME}' into memory...")
    try:
        app_state["embedding_model"] = SentenceTransformer(MODEL_NAME)
        rag_logger.info("Embedding model loaded successfully.")
    except Exception as e:
        rag_logger.critical(f"FATAL: Could not load embedding model. Error: {e}", exc_info=True)
        sys.exit("RAG Server: Embedding model failed to load.")

    global_db_path_str = os.getenv("GLOBAL_RAG_DB_PATH")
    if global_db_path_str:
        global_db_path = Path(global_db_path_str)
        if not global_db_path.exists():
            global_db_path.mkdir(parents=True, exist_ok=True)
        if global_db_path.is_dir():
            try:
                app_state["chroma_client_global"] = chromadb.PersistentClient(path=str(global_db_path))
                app_state["global_collection"] = app_state["chroma_client_global"].get_or_create_collection(
                    name=GLOBAL_COLLECTION_NAME)
                rag_logger.info(f"Successfully loaded/created GLOBAL knowledge base from: {global_db_path}")
            except Exception as e:
                rag_logger.error(f"Failed to load/create GLOBAL knowledge base from {global_db_path}: {e}",
                                 exc_info=True)
        else:
            rag_logger.warning(
                f"GLOBAL_RAG_DB_PATH '{global_db_path_str}' is not a valid directory. Global KB not loaded.")
    else:
        rag_logger.info("GLOBAL_RAG_DB_PATH environment variable not set.")

    app_state["project_collection"] = None
    app_state["chroma_client_project"] = None
    rag_logger.info("--- RAG Server is now ready and listening ---")
    yield
    rag_logger.info("--- RAG Server Shutdown (Lifespan) ---")
    app_state.clear()


# --- FastAPI App Initialization ---
rag_app = FastAPI(title="Kintsugi AvA RAG Service", lifespan=lifespan)


# --- API Endpoints ---
@rag_app.post("/set_collection")
def set_project_collection(request: SetCollectionRequest):
    project_path_str = request.project_path
    if not project_path_str:
        raise HTTPException(status_code=400, detail="Project path cannot be empty.")
    project_root_path = Path(project_path_str)
    if not project_root_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Invalid project path: {project_path_str}")

    project_db_persist_path = project_root_path / PERSIST_DIRECTORY_NAME
    rag_logger.info(f"Setting PROJECT RAG context. DB path: '{project_db_persist_path}'")
    try:
        project_db_persist_path.mkdir(parents=True, exist_ok=True)
        app_state["chroma_client_project"] = chromadb.PersistentClient(path=str(project_db_persist_path))
        app_state["project_collection"] = app_state["chroma_client_project"].get_or_create_collection(
            name=PROJECT_COLLECTION_NAME)
        return {"status": "success", "message": f"Project collection set to: {project_root_path.name}"}
    except Exception as e:
        rag_logger.error(f"FATAL: Could not connect/create PROJECT ChromaDB: {e}", exc_info=True)
        app_state["project_collection"] = None
        app_state["chroma_client_project"] = None
        raise HTTPException(status_code=500, detail=f"Failed to initialize PROJECT ChromaDB: {e}")


@rag_app.post("/reset_project_collection")
def reset_project_collection():
    """Deletes and recreates the project-specific collection to ensure a clean state."""
    client = app_state.get("chroma_client_project")
    if not client:
        rag_logger.warning("/reset_project_collection called but no project client is active.")
        # This is not a failure, just means there's nothing to reset.
        return {"status": "success", "message": "No active project collection to reset."}

    try:
        rag_logger.info(f"Resetting project collection: '{PROJECT_COLLECTION_NAME}'")
        client.delete_collection(name=PROJECT_COLLECTION_NAME)
        app_state["project_collection"] = client.create_collection(name=PROJECT_COLLECTION_NAME)
        rag_logger.info(f"Project collection '{PROJECT_COLLECTION_NAME}' has been successfully reset.")
        return {"status": "success", "message": "Project collection has been reset."}
    except ValueError:
        # This happens if the collection didn't exist in the first place, which is fine.
        rag_logger.info(f"Collection '{PROJECT_COLLECTION_NAME}' did not exist, creating new one.")
        app_state["project_collection"] = client.get_or_create_collection(name=PROJECT_COLLECTION_NAME)
        return {"status": "success", "message": "Project collection did not exist and has been created."}
    except Exception as e:
        rag_logger.error(f"Error resetting project collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@rag_app.get("/")
def read_root():
    status_project = "Active" if app_state.get("project_collection") else "Inactive"
    status_global = "Active" if app_state.get("global_collection") else "Inactive"
    return {
        "status": "RAG Server is running",
        "project_collection_status": status_project,
        "global_collection_status": status_global,
        "embedding_model_status": "Loaded" if app_state.get("embedding_model") else "Not Loaded"
    }


@rag_app.post("/add")
def add_documents(request: AddRequest):
    embedding_model = app_state.get("embedding_model")
    if not embedding_model:
        raise HTTPException(status_code=503, detail="Embedding model not loaded.")

    collection_to_use = None
    collection_name_log = request.target_collection or "project"

    if request.target_collection == "global":
        collection_to_use = app_state.get("global_collection")
        if not collection_to_use:
            raise HTTPException(status_code=503, detail="Global RAG collection is not active.")
    else:  # Default to project
        collection_to_use = app_state.get("project_collection")
        if not collection_to_use:
            raise HTTPException(status_code=503, detail="No active PROJECT RAG collection.")

    docs = request.documents
    if not docs:
        return {"status": "success", "message": "No documents provided."}

    try:
        ids = [doc.id for doc in docs]
        contents = [doc.content for doc in docs]
        metadatas = [doc.metadata for doc in docs]
        embeddings = embedding_model.encode(contents, show_progress_bar=False).tolist()

        collection_to_use.add(embeddings=embeddings, documents=contents, metadatas=metadatas, ids=ids)
        return {"status": "success", "message": f"Added {len(docs)} documents to '{collection_name_log}'."}
    except Exception as e:
        rag_logger.error(f"ERROR during document addition to '{collection_name_log}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@rag_app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest) -> QueryResponse:
    embedding_model = app_state.get("embedding_model")
    if not embedding_model:
        raise HTTPException(status_code=503, detail="Embedding model not loaded.")

    collection_to_query = None
    collection_name_for_log = request.target_collection or "project"

    if request.target_collection == "global":
        collection_to_query = app_state.get("global_collection")
        if not collection_to_query:
            return QueryResponse(context="Global knowledge base is not active.", source_collection="global")
    else:  # Default to project
        collection_to_query = app_state.get("project_collection")
        if not collection_to_query:
            return QueryResponse(context="No knowledge base is active for the current project.",
                                 source_collection="project")

    try:
        query_embedding = embedding_model.encode(request.query_text).tolist()
        results = collection_to_query.query(
            query_embeddings=[query_embedding],
            n_results=request.n_results,
            include=['documents', 'metadatas']
        )
        documents = results.get('documents', [[]])[0]
        metadatas_list = results.get('metadatas', [[]])[0] if results.get('metadatas') else [{} for _ in documents]

        if not documents:
            return QueryResponse(context=f"No relevant documents found in {collection_name_for_log} knowledge base.",
                                 source_collection=collection_name_for_log)

        context_parts = []
        for i, doc_content in enumerate(documents):
            source_file = "Unknown Source"
            if i < len(metadatas_list) and metadatas_list[i] is not None and 'source' in metadatas_list[i]:
                source_file = metadatas_list[i]['source']
            context_parts.append(f"--- Relevant Snippet from {source_file} ---\n{doc_content}")

        return QueryResponse(context="\n\n".join(context_parts).strip(), source_collection=collection_name_for_log)
    except Exception as e:
        rag_logger.error(f"ERROR during query of '{collection_name_for_log}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    if not os.getenv("GLOBAL_RAG_DB_PATH"):
        rag_logger.warning("GLOBAL_RAG_DB_PATH not set. Global KB will be limited.")
    try:
        uvicorn.run("rag_server:rag_app", host=HOST, port=PORT, reload=False)
    except Exception as e:
        rag_logger.critical(f"Failed to start RAG server: {e}", exc_info=True)
        sys.exit(1)