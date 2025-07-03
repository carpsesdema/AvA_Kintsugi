# src/ava/services/lsp_client_service.py
import asyncio
import json
import os
from pathlib import Path
from typing import Optional, Any, Dict, List

from src.ava.core.event_bus import EventBus
from src.ava.core.project_manager import ProjectManager


class LSPClientService:
    """
    Manages the connection and communication with a Language Server Protocol (LSP) server.
    """

    def __init__(self, event_bus: EventBus, project_manager: ProjectManager):
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.host = "127.0.0.1"
        self.port = 8003
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.next_request_id = 1
        self.server_capabilities: Dict[str, Any] = {}
        self._listener_task: Optional[asyncio.Task] = None
        self._is_initialized = False

    async def connect(self) -> bool:
        """Establishes a connection to the LSP server and starts the message listener."""
        self.log("info", f"Attempting to connect to LSP server at {self.host}:{self.port}...")
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            self._listener_task = asyncio.create_task(self._listen_for_messages())
            self.log("success", "Successfully connected to LSP server. Waiting for project to initialize session.")
            # --- CHANGE: We no longer initialize immediately. We wait for an explicit call. ---
            return True
        except ConnectionRefusedError:
            self.log("error", "LSP server connection refused. Is the server running?")
            return False
        except Exception as e:
            self.log("error", f"An unexpected error occurred during LSP connection: {e}")
            return False

    async def _listen_for_messages(self):
        """Continuously listens for and processes messages from the LSP server."""
        try:
            while not self.reader.at_eof():
                line = await self.reader.readline()
                if not line:
                    continue

                header = line.decode('utf-8').strip()
                if header.startswith("Content-Length:"):
                    length = int(header.split(":")[1].strip())
                    await self.reader.read(2)  # Read the '\r\n' separator
                    body = await self.reader.read(length)
                    message = json.loads(body.decode('utf-8'))
                    self._dispatch_message(message)

        except asyncio.CancelledError:
            self.log("info", "LSP message listener task cancelled.")
        except Exception as e:
            self.log("error", f"Error in LSP message listener: {e}")
            self.is_connected = False

    def _dispatch_message(self, message: Dict[str, Any]):
        """Routes incoming messages to the appropriate handler."""
        if "method" in message:
            self._handle_notification(message)
        elif "id" in message:
            # Handle responses to requests (e.g., for completions, definitions)
            pass

    def _handle_notification(self, notification: Dict[str, Any]):
        """Handles server-sent notifications, like diagnostics."""
        method = notification.get("method")
        if method == "textDocument/publishDiagnostics":
            params = notification.get("params", {})
            uri = params.get("uri")
            diagnostics = params.get("diagnostics", [])
            if uri:
                self.event_bus.emit("lsp_diagnostics_received", uri, diagnostics)
                self.log("info", f"Received {len(diagnostics)} diagnostics for {Path(uri).name}")

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        # Not needed for diagnostics, but essential for future features
        pass

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Sends a JSON-RPC notification to the server."""
        if not self.writer:
            return

        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        body = json.dumps(message).encode('utf-8')
        header = f"Content-Length: {len(body)}\r\n\r\n".encode('utf-8')

        self.writer.write(header + body)
        await self.writer.drain()

    async def initialize_session(self) -> bool:
        """Performs the LSP initialization handshake."""
        if not self.project_manager.active_project_path:
            self.log("warning", "Cannot initialize LSP session: No active project.")
            return False

        root_uri = self.project_manager.active_project_path.as_uri()
        self.log("info", f"Initializing LSP session for project: {root_uri}")

        params = {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "capabilities": {
                "textDocument": {
                    "publishDiagnostics": {},
                    "synchronization": {
                        "willSave": True,
                        "didSave": True,
                        "willSaveWaitUntil": False
                    }
                }
            },
            "trace": "off",
            "workspaceFolders": [{"uri": root_uri, "name": self.project_manager.active_project_name}]
        }

        # The 'initialize' request is special and requires a response.
        # For simplicity in this phase, we'll send it as a notification and then send 'initialized'.
        # A more robust implementation would use _send_request and wait for the response.
        await self._send_notification("initialize", params)
        await self._send_notification("initialized", {})
        self._is_initialized = True
        self.log("success", "LSP session initialized.")
        return True

    async def did_open(self, file_path: str, content: str):
        """Notifies the server that a document has been opened."""
        if not self._is_initialized: return
        uri = Path(file_path).as_uri()
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": "python",
                "version": 1,
                "text": content
            }
        }
        await self._send_notification("textDocument/didOpen", params)
        self.log("info", f"LSP: Notified 'didOpen' for {Path(file_path).name}")

    async def did_close(self, file_path: str):
        """Notifies the server that a document has been closed."""
        if not self._is_initialized: return
        uri = Path(file_path).as_uri()
        params = {"textDocument": {"uri": uri}}
        await self._send_notification("textDocument/didClose", params)
        self.log("info", f"LSP: Notified 'didClose' for {Path(file_path).name}")

    async def shutdown(self):
        """Gracefully shuts down the LSP client and connection."""
        if self._listener_task:
            self._listener_task.cancel()
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.log("info", "LSP client shut down.")

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "LSPClientService", level, message)