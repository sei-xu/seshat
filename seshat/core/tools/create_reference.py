"""`create_reference` — cria referência, flat ou pasta, dependendo se o conteúdo pede história.

Fonte: 20_frontmatter_schema.md ("Referências: pasta é sobre forma do
conteúdo, não sobre type") e 22_estrutura_pastas.md. `area_slug` é a subpasta
fixa por área dentro de `03-References/` (ex: "caligrafia") — diferente de
01-Fragments/02-Projects, References preserva subpasta por field.
"""

from __future__ import annotations

from ..history import render_history_body
from ..schema import ValidationContext
from ..vault import VaultClient, VaultError, slugify


def create_reference(
    vault: VaultClient,
    *,
    area_slug: str,  # ex: "caligrafia" — deve bater com o field (slugify do field, ou já estabelecido no vault)
    slug: str,
    title: str,
    summary: str,
    field: str,
    type: str,
    body: str = "",
    as_folder: bool = False,  # True cria 00_index.md + 01_history.md; False cria <slug>.md único
    tags: list[str] | None = None,
) -> dict:
    area = slugify(area_slug)
    file_slug = slugify(slug)

    if as_folder:
        ref_dir = f"03-References/{area}/{file_slug}"
        index_path = f"{ref_dir}/00_index.md"
        history_path = f"{ref_dir}/01_history.md"

        if vault.exists(index_path):
            raise VaultError(f"já existe uma referência em {ref_dir}")

        index_fm = {
            "category": "reference",
            "type": type,
            "title": title,
            "summary": summary,
            "field": field,
            "tags": tags or [],
        }
        index_note = vault.write_note(
            index_path,
            index_fm,
            body=body,
            ctx=ValidationContext(),
            category="reference",
            field_value=field,
            slug=file_slug,
        )

        # 01_history.md nasce vazio — "histórico não fabricado" (mesma regra de create_project).
        history_fm = {
            "category": "reference",
            "type": "history",
            "title": f"{title} — Histórico",
            "summary": f"Histórico de uso/evolução da referência {title}.",
            "field": field,
        }
        history_note = vault.write_note(
            history_path,
            history_fm,
            body=render_history_body([]),
            ctx=ValidationContext(),
            category="reference",
            field_value=field,
            slug=file_slug + "-history",
        )

        return {
            "area_slug": area,
            "slug": file_slug,
            "is_folder": True,
            "index": {"path": index_note.relative_to(vault.root), "frontmatter": index_note.frontmatter},
            "history": {"path": history_note.relative_to(vault.root), "frontmatter": history_note.frontmatter},
        }

    # Referência simples: arquivo único direto na subpasta da área.
    path = f"03-References/{area}/{file_slug}.md"
    if vault.exists(path):
        raise VaultError(f"já existe uma referência em {path}")

    fm = {
        "category": "reference",
        "type": type,
        "title": title,
        "summary": summary,
        "field": field,
        "tags": tags or [],
    }
    note = vault.write_note(
        path,
        fm,
        body=body,
        ctx=ValidationContext(),
        category="reference",
        field_value=field,
        slug=file_slug,
    )

    return {
        "area_slug": area,
        "slug": file_slug,
        "is_folder": False,
        "path": note.relative_to(vault.root),
        "frontmatter": note.frontmatter,
    }
