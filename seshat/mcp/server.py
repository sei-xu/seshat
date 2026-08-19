"""HTTP/SSE server for Seshat MCP tools.

Exposes the 9 core tools via HTTP endpoints with API key authentication.
Supports streaming responses via Server-Sent Events (SSE).
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from seshat.core import VaultClient, ensure_synced
from seshat.core.tools import (
    append_history,
    create_fragment,
    create_project,
    create_reference,
    get_project,
    list_projects,
    list_references,
    search_vault,
    update_project_status,
)

from .schemas import TOOL_SCHEMAS


@dataclass
class ServerConfig:
    """MCP server configuration."""

    vault_root: str | Path
    api_key: str | None = None
    host: str = "127.0.0.1"
    port: int = 8000
    git_remote_url: str | None = None  # Optional git remote for sync


class ToolCallError(Exception):
    """Error executing a tool call."""


class MCPServer:
    """HTTP server for Seshat tools via MCP protocol."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.git = ensure_synced(config.vault_root, config.git_remote_url)
        self.vault = VaultClient(config.vault_root)
        self.tools = {
            "list_projects": list_projects,
            "get_project": get_project,
            "create_project": create_project,
            "append_history": append_history,
            "create_fragment": create_fragment,
            "list_references": list_references,
            "create_reference": create_reference,
            "update_project_status": update_project_status,
            "search_vault": search_vault,
        }
        self.server = None

    def start(self) -> None:
        """Start the HTTP server."""
        handler = self._create_handler_class()
        self.server = HTTPServer((self.config.host, self.config.port), handler)
        print(f"MCP server starting on {self.config.host}:{self.config.port}")
        self.server.serve_forever()

    def stop(self) -> None:
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()

    def _autosync(self, message: str) -> None:
        """Commit and push any vault changes after a write tool call.

        No-ops when no git remote is configured, or when the tool call was
        read-only (commit_and_push checks has_changes() itself). Failures are
        logged but never raised — a push failure shouldn't turn a successful
        write into an error response.
        """
        if not self.config.git_remote_url:
            return
        try:
            self.git.commit_and_push(message)
        except Exception as e:
            print(f"Warning: git autosync failed: {e}")

    def _create_handler_class(self):
        """Create HTTP request handler class with server reference."""
        mcp_server = self

        class MCPRequestHandler(BaseHTTPRequestHandler):
            """HTTP request handler for MCP tool calls."""

            def log_message(self, format, *args):
                """Suppress default logging."""
                pass

            def do_GET(self):
                """Handle GET requests."""
                if self.path == "/health":
                    self._send_json({"status": "healthy", "version": "0.1.0"})
                elif self.path == "/tools":
                    self._send_json({"tools": list(TOOL_SCHEMAS.values())})
                elif self.path == "/git/status":
                    self._handle_git_status()
                elif self.path == "/git/log":
                    self._handle_git_log()
                else:
                    self._send_error(404, "Not found")

            def do_POST(self):
                """Handle POST requests (tool calls)."""
                if not self._check_auth():
                    self._send_error(401, "Unauthorized")
                    return

                try:
                    body = self._read_body()
                    data = json.loads(body)
                except (ValueError, json.JSONDecodeError):
                    self._send_error(400, "Invalid JSON")
                    return

                if self.path == "/call":
                    self._handle_tool_call(data)
                elif self.path == "/git/pull":
                    self._handle_git_pull()
                elif self.path == "/git/push":
                    self._handle_git_push()
                else:
                    self._send_error(404, "Not found")

            def _check_auth(self) -> bool:
                """Check API key authentication."""
                if not mcp_server.config.api_key:
                    return True  # No auth required if not configured
                auth = self.headers.get("Authorization", "")
                expected = f"Bearer {mcp_server.config.api_key}"
                return auth == expected

            def _read_body(self) -> str:
                """Read request body."""
                length = int(self.headers.get("Content-Length", 0))
                if length > 0:
                    return self.rfile.read(length).decode("utf-8")
                return ""

            def _send_json(self, data: dict, status: int = 200) -> None:
                """Send JSON response."""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))

            def _send_error(self, status: int, message: str) -> None:
                """Send error response."""
                self._send_json({"error": message}, status)

            def _handle_tool_call(self, data: dict) -> None:
                """Handle a tool call request."""
                tool_name = data.get("tool")
                params = data.get("params", {})

                if tool_name not in mcp_server.tools:
                    self._send_error(400, f"Unknown tool: {tool_name}")
                    return

                try:
                    tool_fn = mcp_server.tools[tool_name]
                    result = tool_fn(mcp_server.vault, **params)
                    mcp_server._autosync(f"seshat: {tool_name}")
                    self._send_json({"result": result, "tool": tool_name})
                except TypeError as e:
                    self._send_error(400, f"Invalid parameters: {str(e)}")
                except Exception as e:
                    error_msg = str(e)
                    traceback.print_exc()
                    self._send_error(500, f"Tool execution failed: {error_msg}")

            def _handle_git_pull(self) -> None:
                """Handle git pull request."""
                try:
                    status = mcp_server.git.pull()
                    self._send_json({
                        "status": status.status,
                        "message": status.message,
                        "conflicted_files": status.conflicted_files,
                    })
                except Exception as e:
                    self._send_error(500, f"Git pull failed: {str(e)}")

            def _handle_git_push(self) -> None:
                """Handle git push request."""
                try:
                    message = self._read_body()
                    data = json.loads(message) if message else {}
                    commit_msg = data.get("message", "Seshat sync")
                    msg = mcp_server.git.push()
                    self._send_json({
                        "status": "success",
                        "message": msg,
                    })
                except Exception as e:
                    self._send_error(500, f"Git push failed: {str(e)}")

            def _handle_git_status(self) -> None:
                """Handle git status query."""
                try:
                    data = {
                        "initialized": mcp_server.git.is_initialized(),
                        "has_changes": mcp_server.git.has_changes(),
                        "branch": mcp_server.git.current_branch() if mcp_server.git.is_initialized() else None,
                    }
                    self._send_json(data)
                except Exception as e:
                    self._send_error(500, f"Git status failed: {str(e)}")

            def _handle_git_log(self) -> None:
                """Handle git log query."""
                try:
                    max_count = 10
                    if self.path.startswith("/git/log?max="):
                        max_count = int(self.path.split("=")[1])
                    log = mcp_server.git.log(max_count=max_count)
                    self._send_json({"commits": log})
                except Exception as e:
                    self._send_error(500, f"Git log failed: {str(e)}")

        return MCPRequestHandler
