"""`create_project` — cria 00_index.md + 01_history.md seguindo o schema.

Fase 2 não inclui `suggest_decade_numbering` (comportamento ativo, Fase 7) —
essa ferramenta só cria o par índice+histórico, sem sugerir dezenas ainda.
"""

from __future__ import annotations

from ..history import render_history_body
from ..schema import ValidationContext
from ..vault import VaultClient, VaultError, project_folder_name, slugify


def create_project(
    vault: VaultClient,
    *,
    year_month: str,  # "YYYYMM"
    slug: str,
    title: str,
    summary: str,
    field: str,
    project_type: str,
    project_status: str = "planning",
    project_stage: str = "call",
    khaos_project_id: str | None = None,
) -> dict:
    folder = project_folder_name(year_month, slug)
    project_dir = f"02-Projects/{folder}"
    index_path = f"{project_dir}/00_index.md"
    history_path = f"{project_dir}/01_history.md"

    if vault.exists(index_path):
        raise VaultError(f"já existe um projeto em {project_dir}")

    index_fm = {
        "category": "project",
        "type": "index",
        "title": title,
        "summary": summary,
        "field": field,
        "project_type": project_type,
        "project_status": project_status,
        "project_stage": project_stage,
        "khaos_project_id": khaos_project_id,
    }
    index_note = vault.write_note(
        index_path,
        index_fm,
        body="",
        ctx=ValidationContext(is_project_index=True),
        category="project",
        field_value=field,
        slug=slugify(folder),
    )

    # 01_history.md nasce vazio (sem entradas) — "histórico não fabricado".
    history_fm = {
        "category": "project",
        "type": "history",
        "title": f"{title} — Histórico",
        "summary": f"Histórico de decisões do projeto {title}.",
        "field": field,
    }
    history_note = vault.write_note(
        history_path,
        history_fm,
        body=render_history_body([]),
        ctx=ValidationContext(is_project_index=False),
        category="project",
        field_value=field,
        slug=slugify(folder) + "-history",
    )

    return {
        "slug": folder,
        "index": {"path": index_note.relative_to(vault.root), "frontmatter": index_note.frontmatter},
        "history": {"path": history_note.relative_to(vault.root), "frontmatter": history_note.frontmatter},
    }
