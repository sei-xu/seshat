"""MCP server for Seshat tools.

Exposes all 9 core tools via HTTP/SSE with proper authentication.
"""

from .server import MCPServer
from .schemas import get_tool_schemas

__all__ = ["MCPServer", "get_tool_schemas"]
