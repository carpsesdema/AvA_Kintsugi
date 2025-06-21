# src/ava/services/rag_worker.py
# NEW FILE

from PySide6.QtCore import QObject, Signal, Slot
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path

# --- Configuration ---
MODEL_NAME = 'all-miniLM-L6-v2'
PERSIST_DIRECTORY = "rag_db"
COLLECTION_NAME = "kintsugi_kb"

class RAGWorker(QObject):
    """
    The worker that performs all heavy RAG operations on a background thread.
    """
    # Signals to communicate results and status back to the main thread
    initialized = Signal(bool, str)  # success, message
    query_finished = Signal(str)     # context_string
    add_finished = Signal(bool, str) # success, message
    log_message = Signal(str, str)   # type, message

    def __init__(self):
        super().__init__()
        self.embedding_model = None
        self.collection = None

    @Slot()
    def initialize(self):
        """
        Loads the embedding model and connects to the database.
        This is the slow part that runs in the background.
        """
        try:
            self.log_message.emit("info", f"Loading embedding model: '{MODEL_NAME}'...")
            self.embedding_model = SentenceTransformer(MODEL_NAME)
            self.log_message.emit("success", "Embedding model loaded.")

            self.log_message.emit("info", f"Connecting to ChromaDB at: '{PERSIST_DIRECTORY}'...")
            # Use CWD for the database path to be consistent with bundled app behavior
            db_path = Path.cwd() / PERSIST_DIRECTORY
            client = chromadb.PersistentClient(path=str(db_path))
            self.collection = client.get_or_create_collection(name=COLLECTION_NAME)
            self.log_message.emit("success", "ChromaDB connection successful.")

            self.initialized.emit(True, "RAG service is ready.")
        except Exception as e:
            error_msg = f"Failed to initialize RAG worker: {e}"
            self.log_message.emit("error", error_msg)
            self.initialized.emit(False, error_msg)

    @Slot(str, int)
    def perform_query(self, query_text: str, n_results: int):
        if not self.embedding_model or not self.collection:
            self.log_message.emit("error", "Query failed: RAG worker not initialized.")
            self.query_finished.emit("Error: RAG service is not ready.")
            return

        try:
            query_embedding = self.embedding_model.encode(query_text).tolist()
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            documents = results.get('documents', [[]])[0]

            if not documents:
                self.query_finished.emit("No relevant documents found in the knowledge base.")
                return

            context_str = ""
            for i, doc in enumerate(documents):
                context_str += f"--- Relevant Document Snippet {i + 1} ---\n"
                context_str += doc
                context_str += "\n\n"

            self.query_finished.emit(context_str.strip())
        except Exception as e:
            error_msg = f"An unexpected error occurred during query: {e}"
            self.log_message.emit("error", error_msg)
            self.query_finished.emit(f"Error: {error_msg}")

    @Slot(list)
    def perform_add(self, chunks: list):
        if not self.embedding_model or not self.collection:
            self.log_message.emit("error", "Add failed: RAG worker not initialized.")
            self.add_finished.emit(False, "Error: RAG service is not ready.")
            return

        if not chunks:
            self.add_finished.emit(True, "No documents provided to add.")
            return

        try:
            ids = [chunk['id'] for chunk in chunks]
            contents = [chunk['content'] for chunk in chunks]
            metadatas = [chunk['metadata'] for chunk in chunks]

            self.log_message.emit("info", f"Embedding {len(contents)} chunks...")
            embeddings = self.embedding_model.encode(contents).tolist()

            self.collection.add(
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas,
                ids=ids
            )
            message = f"Successfully added {len(chunks)} documents."
            self.log_message.emit("success", message)
            self.add_finished.emit(True, message)
        except Exception as e:
            error_msg = f"An unexpected error occurred during document addition: {e}"
            self.log_message.emit("error", error_msg)
            self.add_finished.emit(False, error_msg)
            self.add_finished.emit(False, error_msg)