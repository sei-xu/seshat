"""`create_fragment` — cria nota solta em 01-Fragments/, mínimo de fricção.

Fase 2 não inclui `suggest_fragment_triage` (comportamento ativo, Fase 6/7) —
esta ferramenta só grava o fragmento com `triage_status: pending`, sem sugerir
destino ainda.
"""

from __future__ import annotations

from ..schema import ValidationContext
from ..vault import VaultClient, VaultError, slugify


def create_fragment(
    vault: VaultClient,
    *,
    filename_slug: str,
    title: str,
    summary: str,
    field: str,
    body: str,
    tags: list[str] | None = None,
) -> dict:
    slug = slugify(filename_slug)
    path = f"01-Fragments/{slug}.md"

    if vault.exists(path):
        raise VaultError(f"já existe um fragmento em {path}")

    fm = {
        "category": "fragment",
        "type": "undefined",
        "title": title,
        "summary": summary,
        "field": field,
        "tags": tags or [],
        "triage_status": "pending",
    }

    note = vault.write_note(
        path,
        fm,
        body=body,
        ctx=ValidationContext(is_fragment=True),
        category="fragment",
        field_value=field,
        slug=slug,
    )

    return {"path": note.relative_to(vault.root), "frontmatter": note.frontmatter}
