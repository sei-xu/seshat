"""Command-line entrypoint for running the Seshat Telegram bot."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from .bot import SeshatTelegramBot
from .parsing import ArgParseError, parse_allowed_ids


def _parse_allowed_ids(raw: str | None) -> set[int]:
    try:
        return parse_allowed_ids(raw)
    except ArgParseError as e:
        raise SystemExit(f"SESHAT_TELEGRAM_ALLOWED_USERS: {e}") from e


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
    parser.add_argument(
        "--git-remote",
        default=os.getenv("AKASHA_GIT_REMOTE"),
        help="Git remote URL for vault sync (or set AKASHA_GIT_REMOTE). "
        "Required on ephemeral disks (e.g. Render free tier): the vault is cloned from "
        "here on boot and every write is committed and pushed back.",
    )
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if not args.token:
        print("Error: no Telegram bot token given (use --token or SESHAT_TELEGRAM_TOKEN)")
        return 1

    vault_root = Path(args.vault_root)
    if not vault_root.is_dir() and not args.git_remote:
        print(f"Error: vault root does not exist: {vault_root} (pass --git-remote to clone it on boot)")
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

    bot = SeshatTelegramBot(vault_root, args.token, allowed_user_ids, git_remote_url=args.git_remote)
    bot.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
