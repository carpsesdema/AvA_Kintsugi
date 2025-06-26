# src/ava/services/rag_service.py
import aiohttp
import asyncio
from pathlib import Path
from typing import List, Dict, Any # Added List, Dict, Any for type hinting


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

    async def check_connection(self, retries: int = 3, delay: float = 1.0) -> bool:
        """
        Performs a quick check to see if the RAG server is running and responding.
        Includes a retry mechanism for startup robustness.
        """
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3.0)) as session:
                    async with session.get(self.server_url) as response:
                        if response.status == 200:
                            self.is_connected = True
                            if attempt > 0:
                                print(f"[RAGService] Connection successful on attempt {attempt + 1}.")
                            return True
                        else:
                            print(f"[RAGService] Connection attempt {attempt + 1} failed with status: {response.status}")
            except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
                print(f"[RAGService] Connection attempt {attempt + 1} failed (ConnectorError/Timeout).")
                if attempt < retries - 1:
                    print(f"[RAGService] Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    print(f"[RAGService] All connection attempts failed.")
            except Exception as e:
                print(f"[RAGService] Unexpected error checking connection on attempt {attempt + 1}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    print(f"[RAGService] All connection attempts failed due to unexpected error.")
        self.is_connected = False
        return False

    async def set_project_db(self, project_path: str) -> tuple[bool, str]:
        """Tells the RAG server to switch its PROJECT database context."""
        if not await self.check_connection():
            return False, "RAG Service is not running or is unreachable after retries."
        print(f"[RAGService] Asking server to switch PROJECT context to: {project_path}")
        payload = {"project_path": project_path}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20.0)) as session:
                async with session.post(f"{self.server_url}/set_collection", json=payload) as response:
                    if response.status == 200:
                        return True, "RAG project context switched successfully."
                    else:
                        error_detail = await response.text()
                        return False, f"Server error on project context switch (status {response.status}): {error_detail}"
        except Exception as e:
            return False, f"Failed to switch RAG project context: {e}"

    async def add(self, chunks: List[Dict[str, Any]], target_collection: str = "project") -> tuple[bool, str]:
        """
        Sends a list of document chunks to the RAG server for ingestion
        into the specified target_collection ('project' or 'global').
        """
        if not await self.check_connection():
            return False, "RAG Service is not running or is unreachable after retries."

        print(f"[RAGService] Sending {len(chunks)} chunks to RAG server for ingestion into '{target_collection}' collection...")
        payload = {
            "documents": chunks,
            "target_collection": target_collection # Pass the target to the server
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120.0)) as session:
                async with session.post(f"{self.server_url}/add", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        message = result.get("message", f"Ingestion into '{target_collection}' successful.")
                        print(f"[RAGService] {message}")
                        return True, message
                    else:
                        error_detail = await response.text()
                        message = f"Error: RAG server returned status {response.status} for '{target_collection}'. Details: {error_detail}"
                        print(f"[RAGService] {message}")
                        return False, message
        except Exception as e:
            message = f"An unexpected error occurred during ingestion into '{target_collection}': {e}"
            print(f"[RAGService] {message}")
            return False, message

    async def query(self, query_text: str, n_results: int = 5, target_collection: str = "project") -> str:
        """
        Queries the external RAG server from the specified target_collection
        and returns a formatted string of context.
        """
        if not await self.check_connection():
            return f"RAG Service is not running or is unreachable after retries (target: {target_collection})."

        print(f"[RAGService] Sending query to RAG server (target: '{target_collection}'): '{query_text[:50]}...'")
        query_payload = {
            "query_text": query_text,
            "n_results": n_results,
            "target_collection": target_collection # Pass the target to the server
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30.0)) as session:
                async with session.post(f"{self.server_url}/query", json=query_payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("context", f"Received empty context from RAG server for '{target_collection}'.")
                    else:
                        error_detail = await response.text()
                        print(f"[RAGService] Error from RAG server (status {response.status}, target: {target_collection}): {error_detail}")
                        return f"Error: RAG server returned status {response.status} for '{target_collection}'."
        except aiohttp.ClientConnectorError:
            self.is_connected = False
            return f"Connection Error: Could not connect to the RAG server (target: {target_collection})."
        except Exception as e:
            print(f"[RAGService] An unexpected error occurred during query (target: {target_collection}): {e}")
            return f"An unexpected error occurred (target: {target_collection}): {e}"