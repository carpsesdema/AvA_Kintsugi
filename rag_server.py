# rag_server.py

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import chromadb
from sentence_transformers import SentenceTransformer
import uvicorn
import sys
from pathlib import Path

# --- Configuration ---
project_root = Path(__file__).parent
sys.path.append(str(project_root))

MODEL_NAME = 'all-miniLM-L6-v2'
PERSIST_DIRECTORY = "rag_db"
COLLECTION_NAME = "kintsugi_kb"
HOST = "127.0.0.1"
PORT = 8001


# --- Data Models for FastAPI ---
class QueryRequest(BaseModel):
    query_text: str
    n_results: int = 5

class QueryResponse(BaseModel):
    context: str

# --- FIX: Add data models for ingesting new documents ---
class Document(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AddRequest(BaseModel):
    documents: List[Document]
# --- END FIX ---

# --- Global State (loaded once on startup) ---
app_state = {}

# --- FastAPI App Initialization ---
app = FastAPI(title="Kintsugi AvA RAG Service")


# --- Startup and Shutdown Events ---
@app.on_event("startup")
def startup_event():
    print("--- RAG Server Startup ---")
    print(f"Loading embedding model: '{MODEL_NAME}' into memory...")
    try:
        app_state["embedding_model"] = SentenceTransformer(MODEL_NAME)
        print("Embedding model loaded successfully.")
    except Exception as e:
        print(f"FATAL: Could not load embedding model. Error: {e}", file=sys.stderr)
        app_state["embedding_model"] = None

    print(f"Connecting to ChromaDB at: '{PERSIST_DIRECTORY}'...")
    try:
        client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)
        app_state["collection"] = client.get_or_create_collection(name=COLLECTION_NAME)
        print("ChromaDB connection successful.")
    except Exception as e:
        print(f"FATAL: Could not connect to ChromaDB. Error: {e}", file=sys.stderr)
        app_state["collection"] = None

    print(f"--- RAG Server is now ready and listening on http://{HOST}:{PORT} ---")


@app.on_event("shutdown")
def shutdown_event():
    print("--- RAG Server Shutdown ---")
    app_state.clear()
    print("Cleaned up resources.")


# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"status": "Kintsugi RAG Server is running"}


# --- FIX: New endpoint to add documents to the knowledge base ---
@app.post("/add")
def add_documents(request: AddRequest):
    if not app_state.get("embedding_model") or not app_state.get("collection"):
        raise HTTPException(status_code=503, detail="RAG service is not initialized or has failed.")

    embedding_model = app_state["embedding_model"]
    collection = app_state["collection"]
    docs = request.documents

    if not docs:
        return {"status": "success", "message": "No documents provided to add."}

    print(f"Received request to add {len(docs)} document chunks.")

    try:
        # Prepare data for ChromaDB
        ids = [doc.id for doc in docs]
        contents = [doc.content for doc in docs]
        metadatas = [doc.metadata for doc in docs]

        # Embed all contents in a batch for efficiency
        print("Embedding document chunks...")
        embeddings = embedding_model.encode(contents).tolist()
        print("Embedding complete.")

        # Add to the collection
        collection.add(
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Successfully added {len(docs)} chunks to the collection '{COLLECTION_NAME}'.")
        return {"status": "success", "message": f"Added {len(docs)} documents."}

    except Exception as e:
        print(f"ERROR during document addition: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during document addition: {e}")
# --- END FIX ---


@app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest) -> QueryResponse:
    if not app_state.get("embedding_model") or not app_state.get("collection"):
        raise HTTPException(status_code=503, detail="RAG service is not initialized or has failed. Check server logs.")

    try:
        embedding_model = app_state["embedding_model"]
        collection = app_state["collection"]
        query_embedding = embedding_model.encode(request.query_text).tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=request.n_results
        )
        documents = results.get('documents', [[]])[0]
        if not documents:
            return QueryResponse(context="No relevant documents found in the knowledge base.")

        context_str = ""
        for i, doc in enumerate(documents):
            context_str += f"--- Relevant Document Snippet {i + 1} ---\n"
            context_str += doc
            context_str += "\n\n"

        return QueryResponse(context=context_str.strip())

    except Exception as e:
        print(f"ERROR during query: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during the query: {e}")


if __name__ == "__main__":
    print("Starting Kintsugi RAG Server...")
    uvicorn.run(app, host=HOST, port=PORT)