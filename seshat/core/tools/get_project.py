"""`get_project` — lê um projeto inteiro (índice + histórico + arquivos)."""

from __future__ import annotations

from ..history import parse_entries
from ..vault import VaultClient, VaultError


def get_project(vault: VaultClient, slug: str) -> dict:
    """`slug` = nome da pasta em `02-Projects/` (formato `YYYYMM_slug`)."""
    project_dir = f"02-Projects/{slug}"
    index_path = f"{project_dir}/00_index.md"

    if not vault.exists(index_path):
        raise VaultError(f"projeto não encontrado: {slug} (esperava {index_path})")

    index_note = vault.read_note(index_path)

    history_entries: list[dict] = []
    history_path = f"{project_dir}/01_history.md"
    if vault.exists(history_path):
        history_note = vault.read_note(history_path)
        history_entries = [
            {"date": e.date, "title": e.title, "summary_line": e.summary_line, "detail": e.detail}
            for e in parse_entries(history_note.body)
        ]

    other_files = [
        note.path.name
        for note in vault.iter_notes(project_dir)
        if note.path.name not in ("00_index.md", "01_history.md")
    ]
    other_files.sort()

    return {
        "slug": slug,
        "frontmatter": index_note.frontmatter,
        "body": index_note.body,
        "history": history_entries,
        "other_files": other_files,
    }
