"""`search_vault` — busca por texto/tag/field em toda a área migrada
(01-Fragments/02-Projects/03-References).

Fonte: 10_arquitetura_seshat.md — "search_vault já cobre busca por
texto/tag/campo em toda a área migrada [...] Não há hoje um componente de
busca semântica separado". Esta é busca literal (substring, case-insensitive),
sem embeddings/ranking — full-text simples sobre frontmatter + corpo.
"""

from __future__ import annotations

from ..vault import VaultClient

SEARCHABLE_ROOTS = ("01-Fragments", "02-Projects", "03-References")


def search_vault(
    vault: VaultClient,
    *,
    query: str | None = None,  # substring, case-insensitive, buscada em title/summary/body
    tag: str | None = None,  # match exato dentro de tags (case-insensitive)
    field: str | None = None,
    category: str | None = None,
) -> list[dict]:
    if not any([query, tag, field, category]):
        raise ValueError("search_vault precisa de ao menos um critério: query, tag, field ou category")

    query_lower = query.lower() if query else None
    tag_lower = tag.lower() if tag else None

    results = []
    for root in SEARCHABLE_ROOTS:
        for note in vault.iter_notes(root):
            fm = note.frontmatter

            if category and fm.get("category") != category:
                continue
            if field and fm.get("field") != field:
                continue
            if tag_lower:
                note_tags = [str(t).lower() for t in (fm.get("tags") or [])]
                if tag_lower not in note_tags:
                    continue
            if query_lower:
                haystack = " ".join(
                    str(fm.get(k, "")) for k in ("title", "summary")
                ) + " " + note.body
                if query_lower not in haystack.lower():
                    continue

            results.append(
                {
                    "path": note.relative_to(vault.root),
                    "id": fm.get("id"),
                    "title": fm.get("title"),
                    "summary": fm.get("summary"),
                    "category": fm.get("category"),
                    "type": fm.get("type"),
                    "field": fm.get("field"),
                    "tags": fm.get("tags") or [],
                    "updated_at": fm.get("updated_at"),
                }
            )

    results.sort(key=lambda r: (r["path"]))
    return results
