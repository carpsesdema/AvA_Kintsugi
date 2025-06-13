# kintsugi_ava/services/rag_service.py
# The real RAG service for interacting with the vector database.

import chromadb
from pathlib import Path
from langchain_community.document_loaders import TextLoader
from langchain_community.docstore.document import Document

# This can be slow to import, so we do it here.
try:
    from sentence_transformers import SentenceTransformer

    SENTRANS_AVAILABLE = True
except ImportError:
    SENTRANS_AVAILABLE = False
    print("[RAGService] Warning: sentence-transformers is not installed. RAG functionality will be disabled.")


class RAGService:
    """
    Manages the Retrieval-Augmented Generation (RAG) knowledge base using
    ChromaDB and SentenceTransformers.
    """

    def __init__(self, persist_directory: str = "rag_db"):
        if not SENTRANS_AVAILABLE:
            self.is_initialized = False
            return

        self.persist_directory = persist_directory
        Path(self.persist_directory).mkdir(exist_ok=True)

        # --- Lazy Initialization ---
        # These expensive objects are only created when first needed.
        self.client = None
        self.embedding_model = None
        self.collection = None
        self.is_initialized = False
        print("[RAGService] Instantiated. Initialization will occur on first use.")

    def _initialize(self):
        """
        Performs the heavy lifting of loading models and connecting to the DB.
        This is called automatically on the first query or ingest operation.
        """
        if self.is_initialized:
            return

        print("[RAGService] Performing first-time initialization...")
        try:
            # Connect to the persistent ChromaDB client
            self.client = chromadb.PersistentClient(path=self.persist_directory)

            # Load the embedding model from HuggingFace
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

            # Get or create the main collection for our knowledge base
            self.collection = self.client.get_or_create_collection(
                name="kintsugi_python_kb",
                embedding_function=None  # We will provide embeddings manually
            )

            self.is_initialized = True
            print("[RAGService] Initialization complete. Ready to use.")
        except Exception as e:
            print(f"[RAGService] FATAL: Error during initialization: {e}")
            # Ensure we don't proceed in a broken state
            self.is_initialized = False
            self.client = None
            self.embedding_model = None
            self.collection = None

    def ingest_documents(self, documents: list[Document]):
        """
        Takes a list of LangChain Document objects, creates embeddings,
        and stores them in the vector database.

        Args:
            documents: A list of Document objects, each with page_content and metadata.
        """
        if not self.is_initialized: self._initialize()
        if not self.collection:
            print("[RAGService] Cannot ingest: Collection is not available.")
            return

        # Prepare data for ChromaDB batch insertion
        ids = [f"{doc.metadata.get('source', 'unknown')}_{i}" for i, doc in enumerate(documents)]
        contents = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        print(f"[RAGService] Creating embeddings for {len(contents)} document chunks...")
        embeddings = self.embedding_model.encode(contents, show_progress_bar=True)

        print(f"[RAGService] Ingesting {len(ids)} documents into ChromaDB...")
        self.collection.add(
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[RAGService] Ingestion complete.")

    def query(self, query_text: str, n_results: int = 5) -> str:
        """
        Queries the knowledge base and returns a formatted string of context.
        """
        if not self.is_initialized: self._initialize()
        if not self.collection:
            print("[RAGService] Cannot query: Collection is not available.")
            return "RAG Service is not available."

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