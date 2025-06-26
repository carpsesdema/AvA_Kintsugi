import aiohttp
import asyncio
from pathlib import Path


class RAGService:
    """
    Acts as a client for the external RAG FastAPI server.
    This class is now lightweight and does not load any models,
    ensuring the main application starts instantly.
    """

    def __init__(self, server_url: str = "http://127.0.0.1:8001"):
        self.server_url = server_url
        self.is_connected = False
        print(f"[RAGService] Client initialized. Will connect to RAG server at {self.server_url}")

    async def check_connection(self) -> bool:
        """
        Performs a quick check to see if the RAG server is running and responding.
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
                async with session.get(self.server_url) as response:
                    self.is_connected = response.status == 200
                    return self.is_connected
        except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
            self.is_connected = False
            return False
        except Exception as e:
            print(f"[RAGService] Unexpected error checking connection: {e}")
            self.is_connected = False
            return False

    async def set_project_db(self, project_path: str) -> tuple[bool, str]:
        """Tells the RAG server to switch its database context to the specified project."""
        if not await self.check_connection():
            return False, "RAG Service is not running or is unreachable."

        print(f"[RAGService] Asking server to switch context to: {project_path}")
        payload = {"project_path": project_path}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.server_url}/set_collection", json=payload, timeout=20) as response:
                    if response.status == 200:
                        return True, "RAG context switched successfully."
                    else:
                        error_detail = await response.text()
                        return False, f"Server error on context switch: {error_detail}"
        except Exception as e:
            return False, f"Failed to switch RAG context: {e}"

    async def add(self, chunks: list) -> tuple[bool, str]:
        """
        Sends a list of document chunks to the RAG server for ingestion.
        """
        if not await self.check_connection():
            return False, "RAG Service is not running or is unreachable."

        print(f"[RAGService] Sending {len(chunks)} chunks to RAG server for ingestion...")
        payload = {"documents": chunks}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.server_url}/add", json=payload, timeout=120) as response:
                    if response.status == 200:
                        result = await response.json()
                        message = result.get("message", "Ingestion successful.")
                        print(f"[RAGService] {message}")
                        return True, message
                    else:
                        error_detail = await response.text()
                        message = f"Error: RAG server returned status {response.status}. Details: {error_detail}"
                        print(f"[RAGService] {message}")
                        return False, message
        except Exception as e:
            message = f"An unexpected error occurred during ingestion: {e}"
            print(f"[RAGService] {message}")
            return False, message

    async def query(self, query_text: str, n_results: int = 5) -> str:
        """
        Queries the external RAG server and returns a formatted string of context.
        """
        if not await self.check_connection():
            return "RAG Service is not running or is unreachable."

        print(f"[RAGService] Sending query to RAG server: '{query_text[:50]}...'")
        query_payload = {"query_text": query_text, "n_results": n_results}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.server_url}/query", json=query_payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("context", "Received empty context from RAG server.")
                    else:
                        error_detail = await response.text()
                        print(f"[RAGService] Error from RAG server (status {response.status}): {error_detail}")
                        return f"Error: RAG server returned status {response.status}."
        except aiohttp.ClientConnectorError:
            self.is_connected = False
            return "Connection Error: Could not connect to the RAG server."
        except Exception as e:
            print(f"[RAGService] An unexpected error occurred during query: {e}")
            return f"An unexpected error occurred: {e}"