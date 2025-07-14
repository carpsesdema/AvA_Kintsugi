# src/ava/services/lsp_client_service.py
import asyncio
import json
import os
import re
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
            return True
        except ConnectionRefusedError:
            self.log("error", "LSP server connection refused. Is the server running?")
            return False
        except Exception as e:
            self.log("error", f"An unexpected error occurred during LSP connection: {e}")
            return False

    async def _listen_for_messages(self):
        """
        Continuously listens for and processes messages from the LSP server
        using a robust buffered approach to handle interleaved messages.
        """
        buffer = b""
        content_length_pattern = re.compile(rb"Content-Length: (\d+)\r\n")

        try:
            while self.reader and not self.reader.at_eof():
                # Read data into the buffer
                data = await self.reader.read(4096)
                if not data:
                    # Connection closed by server
                    self.log("warning", "LSP server closed the connection.")
                    break
                buffer += data

                # Process all complete messages in the buffer
                while True:
                    header_match = content_length_pattern.search(buffer)
                    if not header_match:
                        break  # Need more data to find a header

                    content_length = int(header_match.group(1))
                    header_end_pos = header_match.end()

                    # The full JSON-RPC header is two line breaks
                    message_start_pos = buffer.find(b'\r\n\r\n', header_end_pos)
                    if message_start_pos == -1:
                        break  # Incomplete header

                    json_start_pos = message_start_pos + 4
                    message_end_pos = json_start_pos + content_length

                    if len(buffer) < message_end_pos:
                        break  # Not enough data for the full message body yet

                    # Extract and process the full message
                    message_body_bytes = buffer[json_start_pos:message_end_pos]

                    try:
                        message = json.loads(message_body_bytes.decode('utf-8'))
                        self._dispatch_message(message)
                    except json.JSONDecodeError as e:
                        self.log("error",
                                 f"LSP listener failed to decode JSON body: {e}. Body head: {message_body_bytes[:100]}")

                    # Remove the processed message from the buffer
                    buffer = buffer[message_end_pos:]

        except asyncio.CancelledError:
            self.log("info", "LSP message listener task cancelled.")
        except ConnectionResetError:
            self.log("warning", "LSP connection was reset by the server.")
        except Exception as e:
            self.log("error", f"Critical error in LSP message listener: {e}")
        finally:
            self.log("info", "LSP message listener has stopped.")

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

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        # Not needed for diagnostics, but essential for future features
        pass

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Sends a JSON-RPC notification to the server."""
        if not self.writer or self.writer.is_closing():
            self.log("warning", f"LSP writer closed. Cannot send notification: {method}")
            return

        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        body = json.dumps(message).encode('utf-8')
        header = f"Content-Length: {len(body)}\r\n\r\n".encode('utf-8')

        try:
            self.writer.write(header + body)
            await self.writer.drain()
        except ConnectionResetError:
            self.log("error", "LSP connection reset by peer while sending notification.")
            # Handle reconnection logic if needed

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
        self._is_initialized = False
        if self._listener_task:
            self._listener_task.cancel()
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except ConnectionResetError:
                pass  # The connection may already be gone
        self.log("info", "LSP client shut down.")

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "LSPClientService", level, message)