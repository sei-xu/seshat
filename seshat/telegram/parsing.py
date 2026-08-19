"""Argument parsing helpers for the Telegram bot's `chave=valor` command syntax.

Every write/filter command takes `chave=valor` tokens (shlex-quoted for values
with spaces), e.g. `/newproject year_month=202608 slug=teste title="Café com leite"`.
"""

from __future__ import annotations

import shlex


class ArgParseError(ValueError):
    """Raised when command arguments can't be parsed as `chave=valor` tokens."""


def parse_kv_args(raw: str) -> dict[str, str]:
    """Parse a raw command argument string into a dict of `chave=valor` pairs."""
    try:
        tokens = shlex.split(raw)
    except ValueError as e:
        raise ArgParseError(f"não consegui interpretar os argumentos (aspas não fechadas?): {e}") from e

    result: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            raise ArgParseError(f"argumento inválido (esperava chave=valor): {token!r}")
        key, _, value = token.partition("=")
        key = key.strip()
        if not key:
            raise ArgParseError(f"argumento inválido (chave vazia): {token!r}")
        result[key] = value
    return result


def split_list(value: str | None) -> list[str] | None:
    """Split a comma-separated value into a list, or None if the value is None/empty."""
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_allowed_ids(raw: str | None) -> set[int]:
    """Parse a comma-separated string of Telegram user ids into a set of ints."""
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
            raise ArgParseError(f"id de usuário inválido {chunk!r} (esperava inteiro)") from None
    return ids


def require(args: dict[str, str], *keys: str) -> None:
    """Raise ArgParseError listing every missing required key at once."""
    missing = [k for k in keys if k not in args]
    if missing:
        raise ArgParseError(f"faltam argumentos obrigatórios: {', '.join(missing)}")
