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
    # PIL and io are not directly used in this version but kept for potential future image handling in RAG
    # from PIL import Image
    # import io
except ImportError as e:
    rag_logger.critical(f"Failed to import a critical third-party library: {e}", exc_info=True)
    sys.exit(1)

# --- Configuration ---
PERSIST_DIRECTORY_NAME = "rag_db"  # For project-specific DBs within the project folder
MODEL_NAME = 'all-miniLM-L6-v2'  # Embedding model
PROJECT_COLLECTION_NAME = "kintsugi_project_kb"  # Name for project-specific collections
GLOBAL_COLLECTION_NAME = "kintsugi_global_python_kb"  # Name for the global collection
HOST = "127.0.0.1"
PORT = 8001


# --- Data Models for FastAPI ---
class QueryRequest(BaseModel):
    query_text: str
    n_results: int = 5
    target_collection: Optional[str] = "project"  # 'project' or 'global' or 'both' (future)


class QueryResponse(BaseModel):
    context: str
    source_collection: str  # To indicate where the context came from


class Document(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AddRequest(BaseModel):
    documents: List[Document]
    target_collection: Optional[str] = "project"  # To specify where to add: 'project' or 'global'


class SetCollectionRequest(BaseModel):
    project_path: str  # This will now only set the *project-specific* collection


# --- Global State ---
app_state = {
    "embedding_model": None,
    "project_collection": None,
    "global_collection": None,
    "chroma_client_project": None,  # ChromaDB client for the current project's DB
    "chroma_client_global": None  # ChromaDB client for the global DB
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
        # Exit if embedding model fails to load, as server is non-functional
        # Consider raising the exception to let FastAPI handle graceful shutdown if possible
        # For now, direct exit to ensure it doesn't run in a broken state.
        sys.exit("RAG Server: Embedding model failed to load.")

    # Load Global Collection
    global_db_path_str = os.getenv("GLOBAL_RAG_DB_PATH")
    if global_db_path_str:
        global_db_path = Path(global_db_path_str)
        # Important: The path from GLOBAL_RAG_DB_PATH should be the *directory* where ChromaDB stores its files.
        if not global_db_path.exists():
            rag_logger.info(
                f"Global DB path '{global_db_path}' does not exist. Will attempt to create if documents are added to global collection.")
            global_db_path.mkdir(parents=True, exist_ok=True)  # Ensure it exists for PersistentClient

        if global_db_path.is_dir():
            try:
                rag_logger.info(f"Attempting to load/create GLOBAL knowledge base from: {global_db_path}")
                app_state["chroma_client_global"] = chromadb.PersistentClient(path=str(global_db_path))
                # get_or_create_collection is idempotent
                app_state["global_collection"] = app_state["chroma_client_global"].get_or_create_collection(
                    name=GLOBAL_COLLECTION_NAME,
                    # Optionally, specify embedding function if not using default
                    # embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
                )
                rag_logger.info(
                    f"Successfully loaded/created GLOBAL knowledge base. Collection: '{GLOBAL_COLLECTION_NAME}'")
            except Exception as e:
                rag_logger.error(f"Failed to load/create GLOBAL knowledge base from {global_db_path}: {e}",
                                 exc_info=True)
        else:
            rag_logger.warning(
                f"GLOBAL_RAG_DB_PATH '{global_db_path_str}' is not a valid directory. Global KB not loaded.")
    else:
        rag_logger.info(
            "GLOBAL_RAG_DB_PATH environment variable not set. Global knowledge base will not be loaded/created by default.")

    # Project collection will be set via /set_collection
    app_state["project_collection"] = None
    app_state["chroma_client_project"] = None

    rag_logger.info("--- RAG Server is now ready and listening ---")
    yield
    rag_logger.info("--- RAG Server Shutdown (Lifespan) ---")
    # ChromaDB persistent clients manage their own resources. No explicit close needed.
    app_state.clear()
    rag_logger.info("Cleaned up RAG server resources.")


# --- FastAPI App Initialization ---
rag_app = FastAPI(title="Kintsugi AvA RAG Service", lifespan=lifespan)


# --- API Endpoints ---
@rag_app.post("/set_collection")
def set_project_collection(request: SetCollectionRequest):
    project_path_str = request.project_path
    if not project_path_str:
        rag_logger.error("/set_collection called with empty project path.")
        raise HTTPException(status_code=400, detail="Project path cannot be empty.")

    project_root_path = Path(project_path_str)
    if not project_root_path.is_dir():
        rag_logger.error(f"/set_collection called with invalid project path: {project_path_str}")
        raise HTTPException(status_code=400,
                            detail=f"Invalid or non-existent project path provided: {project_path_str}")

    project_db_persist_path = project_root_path / PERSIST_DIRECTORY_NAME
    rag_logger.info(f"Setting PROJECT-SPECIFIC RAG context. DB path: '{project_db_persist_path}'")
    try:
        project_db_persist_path.mkdir(parents=True, exist_ok=True)
        # Each project gets its own client and collection instance
        app_state["chroma_client_project"] = chromadb.PersistentClient(path=str(project_db_persist_path))
        app_state["project_collection"] = app_state["chroma_client_project"].get_or_create_collection(
            name=PROJECT_COLLECTION_NAME
        )
        rag_logger.info(
            f"ChromaDB PROJECT collection set. Active project: {project_root_path.name}, Collection: '{PROJECT_COLLECTION_NAME}'")
        return {"status": "success", "message": f"Project collection set to: {project_root_path.name}"}
    except Exception as e:
        rag_logger.error(f"FATAL: Could not connect/create PROJECT ChromaDB at '{project_db_persist_path}'. Error: {e}",
                         exc_info=True)
        app_state["project_collection"] = None
        app_state["chroma_client_project"] = None
        raise HTTPException(status_code=500,
                            detail=f"Failed to initialize PROJECT ChromaDB collection at {project_db_persist_path}: {e}")


@rag_app.get("/")
def read_root():
    status_project = "Active" if app_state.get("project_collection") else "Inactive - Use /set_collection"
    status_global = "Active" if app_state.get("global_collection") else "Inactive - Set GLOBAL_RAG_DB_PATH & add docs"
    return {
        "status": "Kintsugi RAG Server is running",
        "project_collection_status": status_project,
        "global_collection_status": status_global,
        "embedding_model_status": "Loaded" if app_state.get("embedding_model") else "Not Loaded"
    }


@rag_app.post("/add")
def add_documents(request: AddRequest):
    embedding_model = app_state.get("embedding_model")
    if not embedding_model:
        rag_logger.error("/add called but embedding model not loaded.")
        raise HTTPException(status_code=503, detail="Embedding model not loaded.")

    collection_to_use = None
    collection_name_log = request.target_collection or "default (project)"

    if request.target_collection == "global":
        collection_to_use = app_state.get("global_collection")
        if not collection_to_use:
            rag_logger.error("/add target 'global' but global collection not loaded/initialized.")
            raise HTTPException(status_code=503,
                                detail="Global RAG collection is not active. Ensure GLOBAL_RAG_DB_PATH is set and valid, then try adding documents to it.")
    elif request.target_collection == "project":
        collection_to_use = app_state.get("project_collection")
        if not collection_to_use:
            rag_logger.error("/add target 'project' but project collection not set. Use /set_collection first.")
            raise HTTPException(status_code=503,
                                detail="No active PROJECT RAG collection. Please use /set_collection for a project first.")
    else:
        raise HTTPException(status_code=400,
                            detail=f"Invalid target_collection: '{request.target_collection}'. Must be 'project' or 'global'.")

    docs = request.documents
    if not docs:
        return {"status": "success", "message": "No documents provided to add."}

    try:
        ids = [doc.id for doc in docs]
        contents = [doc.content for doc in docs]
        metadatas = [doc.metadata for doc in docs]

        rag_logger.info(f"Encoding {len(contents)} documents for '{collection_name_log}' collection...")
        embeddings = embedding_model.encode(contents, show_progress_bar=False).tolist()  # Batch encode

        rag_logger.info(f"Adding {len(docs)} documents to '{collection_name_log}' collection in ChromaDB...")
        collection_to_use.add(embeddings=embeddings, documents=contents, metadatas=metadatas, ids=ids)
        rag_logger.info(f"Successfully added {len(docs)} chunks to the '{collection_name_log}' collection.")
        return {"status": "success", "message": f"Added {len(docs)} documents to '{collection_name_log}' collection."}
    except Exception as e:
        rag_logger.error(f"ERROR during document addition to '{collection_name_log}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during document addition: {str(e)}")


@rag_app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest) -> QueryResponse:
    embedding_model = app_state.get("embedding_model")
    if not embedding_model:
        rag_logger.error("/query called but embedding model not loaded.")
        raise HTTPException(status_code=503, detail="Embedding model not loaded.")

    collection_to_query = None
    collection_name_for_log = request.target_collection or "default (project)"

    if request.target_collection == "global":
        collection_to_query = app_state.get("global_collection")
        if not collection_to_query:
            rag_logger.warning("Query targeted 'global' collection, but it's not loaded.")
            return QueryResponse(context="Global knowledge base is not active.", source_collection="global")
    elif request.target_collection == "project":
        collection_to_query = app_state.get("project_collection")
        if not collection_to_query:
            rag_logger.warning("Query targeted 'project' collection, but no project context is set.")
            return QueryResponse(context="No knowledge base is active for the current project.",
                                 source_collection="project")
    else:
        raise HTTPException(status_code=400,
                            detail=f"Invalid target_collection: '{request.target_collection}'. Must be 'project' or 'global'.")

    try:
        query_embedding = embedding_model.encode(request.query_text).tolist()
        results = collection_to_query.query(
            query_embeddings=[query_embedding],
            n_results=request.n_results,
            include=['documents', 'metadatas']  # Ensure metadatas are included
        )

        documents = results.get('documents', [[]])[0]
        metadatas_list = results.get('metadatas', [[]])[0] if results.get('metadatas') else [{} for _ in documents]

        if not documents:
            return QueryResponse(
                context=f"No relevant documents found in the {collection_name_for_log} knowledge base for this query.",
                source_collection=collection_name_for_log
            )

        context_parts = []
        for i, doc_content in enumerate(documents):
            source_file = "Unknown Source"
            # Ensure metadatas_list[i] is not None before accessing
            if i < len(metadatas_list) and metadatas_list[i] is not None and 'source' in metadatas_list[i]:
                source_file = metadatas_list[i]['source']
            context_parts.append(f"--- Relevant Snippet {i + 1} (from: {source_file}) ---\n{doc_content}")

        context_str = "\n\n".join(context_parts)
        rag_logger.info(f"Query to '{collection_name_for_log}' collection returned {len(documents)} results.")
        return QueryResponse(context=context_str.strip(), source_collection=collection_name_for_log)
    except Exception as e:
        rag_logger.error(f"ERROR during query of '{collection_name_for_log}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during the query: {str(e)}")


if __name__ == "__main__":
    # Example for testing: Ensure GLOBAL_RAG_DB_PATH points to a directory.
    # The directory will be created by ChromaDB if it doesn't exist.
    # global_db_test_path = Path(__file__).parent.parent / "test_global_rag_db" # Example path
    # os.environ["GLOBAL_RAG_DB_PATH"] = str(global_db_test_path)
    # rag_logger.info(f"TESTING: GLOBAL_RAG_DB_PATH set to '{os.getenv('GLOBAL_RAG_DB_PATH')}'")

    if not os.getenv("GLOBAL_RAG_DB_PATH"):
        rag_logger.warning("GLOBAL_RAG_DB_PATH environment variable is not set. "
                           "The global knowledge base functionality will be limited unless "
                           "documents are explicitly added to it via API after server start.")

    try:
        rag_logger.info("Starting RAG server directly with Uvicorn...")
        # Ensure the app string is correct for uvicorn when running as a script
        uvicorn.run("rag_server:rag_app", host=HOST, port=PORT, reload=False)
    except SystemExit as se:  # Catch sys.exit from lifespan
        rag_logger.critical(f"RAG Server exited prematurely: {se}")
    except Exception as e:
        rag_logger.critical(f"Failed to start RAG server: {e}", exc_info=True)
        sys.exit(1)