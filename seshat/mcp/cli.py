"""Command-line interface for running the Seshat MCP server."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .server import MCPServer, ServerConfig


def main():
    """Run the MCP server from CLI."""
    parser = argparse.ArgumentParser(
        description="Seshat MCP server — expose Seshat tools to Claude and other AI agents"
    )
    parser.add_argument(
        "--vault-root",
        required=True,
        help="Path to the Akasha vault root directory",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("SESHAT_API_KEY"),
        help="API key for server authentication (or set SESHAT_API_KEY env var)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)",
    )
    parser.add_argument(
        "--git-remote",
        default=os.getenv("AKASHA_GIT_REMOTE"),
        help="Git remote URL for vault sync (or set AKASHA_GIT_REMOTE). "
        "Required on ephemeral disks (e.g. Render free tier): the vault is cloned from "
        "here on boot and every write is committed and pushed back.",
    )

    args = parser.parse_args()

    vault_root = Path(args.vault_root)
    if not vault_root.is_dir() and not args.git_remote:
        print(f"Error: vault root does not exist: {vault_root} (pass --git-remote to clone it on boot)")
        return 1

    config = ServerConfig(
        vault_root=vault_root,
        api_key=args.api_key,
        host=args.host,
        port=args.port,
        git_remote_url=args.git_remote,
    )

    print(f"Starting Seshat MCP server...")
    print(f"  Vault root: {vault_root}")
    print(f"  Server: {args.host}:{args.port}")
    if config.api_key:
        print(f"  Authentication: Required (API key)")
    else:
        print(f"  Authentication: Disabled")
    print()

    server = MCPServer(config)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutdown requested")
        server.stop()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
