# kintsugi_ava/services/rag_service.py
# V2: Manages core RAG ops: chunking, embedding, DB interaction. Uses ChunkingService.

import chromadb
import hashlib
from pathlib import Path
from typing import List

from .chunking_service import ChunkingService

try:
    from sentence_transformers import SentenceTransformer

    SENTRANS_AVAILABLE = True
except ImportError:
    SENTRANS_AVAILABLE = False
    print("[RAGService] Warning: sentence-transformers is not installed. RAG functionality will be disabled.")


class RAGService:
    """
    Manages the core RAG operations: chunking, embedding, and database interaction.
    Its methods are synchronous and potentially blocking; the caller is responsible
    for running them in a separate thread if required.
    """

    def __init__(self, persist_directory: str = "rag_db"):
        if not SENTRANS_AVAILABLE:
            self.is_initialized = False
            return

        self.persist_directory = persist_directory
        Path(self.persist_directory).mkdir(exist_ok=True)
        self.chunking_service = ChunkingService()

        self.client = None
        self.embedding_model = None
        self.collection = None
        self.is_initialized = False
        print("[RAGService] Instantiated. Initialization will be performed on first use.")

    def _initialize(self):
        """
        Performs the heavy, one-time lifting of loading models and connecting to the DB.
        This is a blocking operation.
        """
        if self.is_initialized:
            return

        print("[RAGService] Performing first-time initialization (this may take a moment)...")
        try:
            # Connect to the persistent ChromaDB client
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            # Load the embedding model from HuggingFace
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            # Get or create the main collection for our knowledge base
            self.collection = self.client.get_or_create_collection(name="kintsugi_kb")
            self.is_initialized = True
            print("[RAGService] Initialization complete. Ready to use.")
        except Exception as e:
            print(f"[RAGService] FATAL: Error during initialization: {e}")
            # Ensure we don't proceed in a broken state
            self.is_initialized = False

    def ingest_files(self, file_paths: List[Path]) -> int:
        """
        Reads, chunks, embeds, and ingests a list of files into the vector DB.
        This is a long-running, blocking operation.

        Args:
            file_paths: A list of Path objects to ingest.

        Returns:
            The number of files successfully ingested.
        """
        if not self.is_initialized:
            self._initialize()  # Ensure model is loaded before we start

        if not self.is_initialized or not self.collection or not self.embedding_model:
            print("[RAGService] Cannot ingest: RAG service is not properly initialized.")
            return 0

        processed_count = 0
        for file_path in file_paths:
            try:
                print(f"[RAGService] Processing: {file_path.name}")
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                chunks = self.chunking_service.chunk_document(content, str(file_path))
                if not chunks:
                    continue

                # Prepare data for ChromaDB
                ids = [f"{file_hash}_{chunk['id']}" for chunk in chunks]
                contents = [chunk['content'] for chunk in chunks]
                metadatas = [chunk['metadata'] for chunk in chunks]

                # Generate embeddings for all chunks in the file
                embeddings = self.embedding_model.encode(contents, show_progress_bar=False)

                # Add the processed chunks to the collection
                self.collection.add(
                    ids=ids,
                    documents=contents,
                    metadatas=metadatas,
                    embeddings=embeddings.tolist()  # Ensure it's a list for ChromaDB
                )
                processed_count += 1
            except Exception as e:
                print(f"[RAGService] Failed to ingest file {file_path}. Error: {e}")

        print(f"[RAGService] Ingestion task complete. Processed {processed_count}/{len(file_paths)} files.")
        return processed_count

    def query(self, query_text: str, n_results: int = 5) -> str:
        """
        Queries the knowledge base and returns a formatted string of context.
        This is a blocking operation.
        """
        if not self.is_initialized:
            print("[RAGService] Cannot query: not initialized. Returning empty context.")
            # Don't initialize on query, as it can cause a long delay on first user message.
            # Initialization should be handled by an explicit startup or ingestion task.
            return "RAG Service is not ready."

        if not self.collection or not self.embedding_model:
            return "RAG Service is not ready."

        print(f"[RAGService] Querying for: '{query_text[:50]}...'")

        # Create an embedding for the user's query
        query_embedding = self.embedding_model.encode(query_text).tolist()

        # Query the collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        # Format the results into a clean string for the prompt
        context_str = ""
        documents = results.get('documents', [[]])[0]
        for i, doc in enumerate(documents):
            context_str += f"--- Relevant Document Snippet {i + 1} ---\n"
            context_str += doc
            context_str += "\n\n"

        return context_str.strip() if context_str else "No relevant documents found."