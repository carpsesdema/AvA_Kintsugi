# rag_server.py

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chromadb
from sentence_transformers import SentenceTransformer
import uvicorn
import sys
from pathlib import Path

# --- Configuration ---
# Ensure the script can find other project modules if needed later
# This helps if you run it from a different directory
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


# --- Global State (loaded once on startup) ---
app_state = {}

# --- FastAPI App Initialization ---
app = FastAPI(title="Kintsugi AvA RAG Service")


# --- Startup and Shutdown Events ---
@app.on_event("startup")
def startup_event():
    """
    This function runs once when the server starts.
    It's responsible for the slow, one-time loading of the model and DB client.
    """
    print("--- RAG Server Startup ---")

    # 1. Load the SentenceTransformer model
    print(f"Loading embedding model: '{MODEL_NAME}' into memory...")
    try:
        # This is the slow part. It will only happen ONCE when this server starts.
        app_state["embedding_model"] = SentenceTransformer(MODEL_NAME)
        print("Embedding model loaded successfully.")
    except Exception as e:
        print(f"FATAL: Could not load embedding model. Error: {e}", file=sys.stderr)
        # In a real production app, you might want to exit here, but for this
        # we'll let it run so the user can see the error.
        app_state["embedding_model"] = None

    # 2. Connect to the ChromaDB persistent client
    print(f"Connecting to ChromaDB at: '{PERSIST_DIRECTORY}'...")
    try:
        client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)
        # Get or create the collection. This is fast.
        app_state["collection"] = client.get_or_create_collection(name=COLLECTION_NAME)
        print("ChromaDB connection successful.")
    except Exception as e:
        print(f"FATAL: Could not connect to ChromaDB. Error: {e}", file=sys.stderr)
        app_state["collection"] = None

    print(f"--- RAG Server is now ready and listening on http://{HOST}:{PORT} ---")


@app.on_event("shutdown")
def shutdown_event():
    """Function to run on server shutdown for cleanup."""
    print("--- RAG Server Shutdown ---")
    app_state.clear()
    print("Cleaned up resources.")


# --- API Endpoints ---
@app.get("/")
def read_root():
    """A simple root endpoint to check if the server is running."""
    return {"status": "Kintsugi RAG Server is running"}


@app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest) -> QueryResponse:
    """
    Receives a query, embeds it, queries the vector DB, and returns the context.
    """
    if not app_state.get("embedding_model") or not app_state.get("collection"):
        raise HTTPException(status_code=503, detail="RAG service is not initialized or has failed. Check server logs.")

    try:
        embedding_model = app_state["embedding_model"]
        collection = app_state["collection"]

        # 1. Embed the query text
        query_embedding = embedding_model.encode(request.query_text).tolist()

        # 2. Query the ChromaDB collection
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=request.n_results
        )

        # 3. Format the results into a single context string
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


# --- Main entry point to run the server ---
if __name__ == "__main__":
    print("Starting Kintsugi RAG Server...")
    # uvicorn.run is a blocking call that starts the server
    uvicorn.run(app, host=HOST, port=PORT)