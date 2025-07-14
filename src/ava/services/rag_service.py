# src/ava/services/rag_service.py
import aiohttp
import asyncio
from pathlib import Path
from typing import List, Dict, Any


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
        """
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3.0)) as session:
                    async with session.get(self.server_url) as response:
                        if response.status == 200:
                            self.is_connected = True
                            return True
            except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
        self.is_connected = False
        return False

    async def set_project_db(self, project_path: str) -> tuple[bool, str]:
        """Tells the RAG server to switch its PROJECT database context."""
        if not await self.check_connection():
            return False, "RAG Service is not running or is unreachable."
        payload = {"project_path": project_path}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20.0)) as session:
                async with session.post(f"{self.server_url}/set_collection", json=payload) as response:
                    if response.status == 200:
                        return True, "RAG project context switched."
                    error_detail = await response.text()
                    return False, f"Server error on context switch (status {response.status}): {error_detail}"
        except Exception as e:
            return False, f"Failed to switch RAG project context: {e}"

    async def reset_project_db(self) -> tuple[bool, str]:
        """Tells the RAG server to wipe and recreate the current project's database."""
        if not await self.check_connection():
            return False, "RAG Service is not running or is unreachable."
        print("[RAGService] Asking server to reset project collection...")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20.0)) as session:
                async with session.post(f"{self.server_url}/reset_project_collection") as response:
                    if response.status == 200:
                        return True, "RAG project DB reset successfully."
                    error_detail = await response.text()
                    return False, f"Server error on project DB reset (status {response.status}): {error_detail}"
        except Exception as e:
            return False, f"Failed to reset RAG project DB: {e}"

    async def add(self, chunks: List[Dict[str, Any]], target_collection: str = "project") -> tuple[bool, str]:
        """
        Sends a list of document chunks to the RAG server for ingestion.
        """
        if not await self.check_connection():
            return False, "RAG Service is not running or is unreachable."

        payload = {"documents": chunks, "target_collection": target_collection}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120.0)) as session:
                async with session.post(f"{self.server_url}/add", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return True, result.get("message", "Ingestion successful.")
                    error_detail = await response.text()
                    return False, f"Error from RAG server (status {response.status}): {error_detail}"
        except Exception as e:
            return False, f"An unexpected error occurred during ingestion: {e}"

    async def query(self, query_text: str, n_results: int = 5, target_collection: str = "project") -> str:
        """
        Queries the external RAG server and returns a formatted string of context.
        """
        if not await self.check_connection():
            return f"RAG Service is not running (target: {target_collection})."

        query_payload = {
            "query_text": query_text,
            "n_results": n_results,
            "target_collection": target_collection
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30.0)) as session:
                async with session.post(f"{self.server_url}/query", json=query_payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("context", f"Received empty context from RAG server for '{target_collection}'.")
                    error_detail = await response.text()
                    return f"Error: RAG server returned status {response.status} for '{target_collection}'."
        except Exception as e:
            return f"An unexpected error occurred during query (target: {target_collection}): {e}"