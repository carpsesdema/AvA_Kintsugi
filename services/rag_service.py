# kintsugi_ava/services/rag_service.py
# V4: Refactored to be a thin client for the external RAG server.

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

        Returns:
            bool: True if the server is connected, False otherwise.
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
                async with session.get(self.server_url) as response:
                    if response.status == 200:
                        self.is_connected = True
                        return True
        except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
            # These errors are expected if the server isn't running
            pass
        except Exception as e:
            print(f"[RAGService] Unexpected error checking connection: {e}")

        self.is_connected = False
        return False

    async def query(self, query_text: str, n_results: int = 5) -> str:
        """
        Queries the external RAG server and returns a formatted string of context.
        This is a fast, non-blocking network operation.
        """
        if not self.is_connected:
            # Quick check before sending, in case connection was lost.
            if not await self.check_connection():
                return "RAG Service is not running or is unreachable. Please launch it from the sidebar."

        print(f"[RAGService] Sending query to RAG server: '{query_text[:50]}...'")

        query_payload = {
            "query_text": query_text,
            "n_results": n_results
        }

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
            self.is_connected = False  # Mark as not connected
            return "Connection Error: Could not connect to the RAG server."
        except Exception as e:
            print(f"[RAGService] An unexpected error occurred during query: {e}")
            return f"An unexpected error occurred: {e}"