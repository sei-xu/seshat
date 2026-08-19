"""Runs the MCP server and the Telegram bot in a single process/service.

For deployments with no persistent disk (e.g. Render's free tier), running
two separate services would mean two independent ephemeral clones of the
vault drifting apart. This entrypoint shares one vault_root between both:
the MCP server syncs it first (clone-or-pull), then the bot's own sync is
just a cheap pull against an already-initialized repo — no cloning race.

The MCP server's HTTP loop runs in a background thread; the Telegram bot's
polling loop owns the main thread.
"""

from __future__ import annotations

import argparse
import logging
import os
import threading
from pathlib import Path

from seshat.mcp.server import MCPServer, ServerConfig
from seshat.telegram.bot import SeshatTelegramBot
from seshat.telegram.parsing import parse_allowed_ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seshat combined service — MCP server + Telegram bot sharing one vault"
    )
    parser.add_argument("--vault-root", default=os.getenv("SESHAT_VAULT_ROOT", "/tmp/vault"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--api-key", default=os.getenv("SESHAT_API_KEY"))
    parser.add_argument("--telegram-token", default=os.getenv("SESHAT_TELEGRAM_TOKEN"))
    parser.add_argument("--allowed-users", default=os.getenv("SESHAT_TELEGRAM_ALLOWED_USERS"))
    parser.add_argument("--git-remote", default=os.getenv("AKASHA_GIT_REMOTE"))
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if not args.telegram_token:
        print("Error: no Telegram bot token given (use --telegram-token or SESHAT_TELEGRAM_TOKEN)")
        return 1

    allowed_user_ids = parse_allowed_ids(args.allowed_users)
    if not allowed_user_ids:
        print(
            "Error: no allowed Telegram user ids configured (use --allowed-users or "
            "SESHAT_TELEGRAM_ALLOWED_USERS) — refusing to start an open bot with vault write access"
        )
        return 1

    if not args.git_remote:
        print(
            "Warning: no --git-remote/AKASHA_GIT_REMOTE configured — on an ephemeral disk "
            "the vault will be empty and everything written will be lost on restart"
        )

    vault_root = Path(args.vault_root)

    print("Starting Seshat combined service (MCP server + Telegram bot)...")
    print(f"  Vault root: {vault_root}")
    print(f"  HTTP: {args.host}:{args.port}")
    print(f"  Allowed Telegram users: {sorted(allowed_user_ids)}")

    server = MCPServer(
        ServerConfig(
            vault_root=vault_root,
            api_key=args.api_key,
            host=args.host,
            port=args.port,
            git_remote_url=args.git_remote,
        )
    )
    bot = SeshatTelegramBot(vault_root, args.telegram_token, allowed_user_ids, git_remote_url=args.git_remote)

    server_thread = threading.Thread(target=server.start, daemon=True, name="mcp-server")
    server_thread.start()

    try:
        bot.run()  # blocks — owns the process's main thread and asyncio loop
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
