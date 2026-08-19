"""Stdio MCP server exposing Seshat vault tools to Claude Code / Claude Desktop.

Unlike ``seshat.mcp.server`` (a custom HTTP/REST server), this module speaks
the actual Model Context Protocol (JSON-RPC over stdio), so it can be
registered directly with ``claude mcp add``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import Server

from seshat.core import VaultClient
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

TOOLS = {
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


def build_server(vault: VaultClient) -> Server:
    async def on_list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=schema["name"],
                    description=schema["description"],
                    inputSchema=schema["input_schema"],
                )
                for schema in TOOL_SCHEMAS.values()
            ]
        )

    async def on_call_tool(ctx, params) -> types.CallToolResult:
        if params.name not in TOOLS:
            raise ValueError(f"Unknown tool: {params.name}")
        result = TOOLS[params.name](vault, **(params.arguments or {}))
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(result, default=str, ensure_ascii=False),
                )
            ]
        )

    return Server(
        "seshat",
        version="0.1.0",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def run(vault_root: Path) -> None:
    vault = VaultClient(vault_root)
    server = build_server(vault)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seshat MCP stdio server — exposes vault tools over the Model Context Protocol"
    )
    parser.add_argument(
        "--vault-root",
        default=os.getenv("SESHAT_VAULT_ROOT"),
        help="Path to the Akasha vault root directory (or set SESHAT_VAULT_ROOT)",
    )
    args = parser.parse_args()

    if not args.vault_root:
        parser.error("--vault-root is required (or set SESHAT_VAULT_ROOT)")

    vault_root = Path(args.vault_root)
    if not vault_root.is_dir():
        parser.error(f"vault root does not exist: {vault_root}")

    asyncio.run(run(vault_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
