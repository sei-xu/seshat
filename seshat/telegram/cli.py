"""Command-line entrypoint for running the Seshat Telegram bot."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from .bot import SeshatTelegramBot


def _parse_allowed_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    ids = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError:
            raise SystemExit(f"SESHAT_TELEGRAM_ALLOWED_USERS: id inválido {chunk!r} (esperava inteiro)")
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Seshat Telegram bot — chat interface for the Akasha vault")
    parser.add_argument("--vault-root", required=True, help="Path to the Akasha vault root directory")
    parser.add_argument(
        "--token",
        default=os.getenv("SESHAT_TELEGRAM_TOKEN"),
        help="Telegram bot token (or set SESHAT_TELEGRAM_TOKEN env var)",
    )
    parser.add_argument(
        "--allowed-users",
        default=os.getenv("SESHAT_TELEGRAM_ALLOWED_USERS"),
        help="Comma-separated Telegram user ids allowed to use the bot (or set SESHAT_TELEGRAM_ALLOWED_USERS)",
    )
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if not args.token:
        print("Error: no Telegram bot token given (use --token or SESHAT_TELEGRAM_TOKEN)")
        return 1

    vault_root = Path(args.vault_root)
    if not vault_root.is_dir():
        print(f"Error: vault root does not exist: {vault_root}")
        return 1

    allowed_user_ids = _parse_allowed_ids(args.allowed_users)
    if not allowed_user_ids:
        print(
            "Error: no allowed Telegram user ids configured (use --allowed-users or "
            "SESHAT_TELEGRAM_ALLOWED_USERS) — refusing to start an open bot with vault write access"
        )
        return 1

    print("Starting Seshat Telegram bot...")
    print(f"  Vault root: {vault_root}")
    print(f"  Allowed users: {sorted(allowed_user_ids)}")

    bot = SeshatTelegramBot(vault_root, args.token, allowed_user_ids)
    bot.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
