# src/ava/services/rag_service.py
# V6: Refactored to be a lightweight proxy for the in-process RAGManager/Worker.

import asyncio
from typing import List, Dict, Any, Tuple

class RAGService:
    """
    Acts as a thread-safe, async-friendly proxy to the RAGManager.
    This class allows other async services to interact with the RAG system
    without needing to know about Qt Threads or signals.
    """

    def __init__(self, rag_manager):
        self.rag_manager = rag_manager
        print(f"[RAGService] Proxy initialized. Linked to RAGManager.")

    async def check_connection(self) -> bool:
        """
        Checks if the RAG service worker is running. This no longer involves
        a network call, just a check on the manager's state.
        """
        return self.rag_manager.is_service_running()

    async def add(self, chunks: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Asynchronously sends document chunks to the RAG worker for ingestion
        and waits for the result.

        Args:
            chunks: A list of chunk dictionaries.

        Returns:
            A tuple (success: bool, message: str).
        """
        if not self.rag_manager.is_service_running():
            return False, "RAG Service is not running. Please launch it from the sidebar."

        # Create a future to wait for the result from the worker thread
        future = asyncio.get_running_loop().create_future()

        # Define a one-time slot to receive the result and set the future
        def on_add_finished(success: bool, message: str):
            if not future.done():
                future.set_result((success, message))
            # Disconnect self after firing to prevent multiple calls
            try:
                self.rag_manager.add_result_received.disconnect(on_add_finished)
            except (TypeError, RuntimeError): # Already disconnected or object destroyed
                pass

        # Connect the signal to our one-time slot
        self.rag_manager.add_result_received.connect(on_add_finished)

        # Trigger the operation on the worker thread
        self.rag_manager.trigger_add(chunks)

        # Await the result from the future
        return await future

    async def query(self, query_text: str, n_results: int = 5) -> str:
        """
        Asynchronously sends a query to the RAG worker and waits for the result.
        """
        if not self.rag_manager.is_service_running():
            return "RAG Service is not running. Please launch it from the sidebar."

        future = asyncio.get_running_loop().create_future()

        def on_query_finished(context_str: str):
            if not future.done():
                future.set_result(context_str)
            try:
                self.rag_manager.query_result_received.disconnect(on_query_finished)
            except (TypeError, RuntimeError):
                pass

        self.rag_manager.query_result_received.connect(on_query_finished)
        self.rag_manager.trigger_query(query_text, n_results)

        return await future