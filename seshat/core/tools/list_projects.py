"""`list_projects` — lista projetos, filtra por field/project_status/project_stage."""

from __future__ import annotations

from ..vault import VaultClient


def list_projects(
    vault: VaultClient,
    *,
    field: str | None = None,
    project_status: str | None = None,
    project_stage: str | None = None,
) -> list[dict]:
    """Varre `02-Projects/*/00_index.md` e devolve um resumo por projeto.

    Não lê `01_history.md` nem os demais arquivos — pra isso, `get_project`.
    """
    results = []
    for note in vault.iter_notes("02-Projects"):
        if note.path.name != "00_index.md":
            continue
        fm = note.frontmatter
        if fm.get("category") != "project":
            continue  # defensivo — todo 00_index.md de 02-Projects deveria ser category: project
        if field and fm.get("field") != field:
            continue
        if project_status and fm.get("project_status") != project_status:
            continue
        if project_stage and fm.get("project_stage") != project_stage:
            continue

        results.append(
            {
                "slug": note.path.parent.name,
                "id": fm.get("id"),
                "title": fm.get("title"),
                "summary": fm.get("summary"),
                "field": fm.get("field"),
                "project_type": fm.get("project_type"),
                "project_status": fm.get("project_status"),
                "project_stage": fm.get("project_stage"),
                "khaos_project_id": fm.get("khaos_project_id"),
                "updated_at": fm.get("updated_at"),
            }
        )

    results.sort(key=lambda r: r["slug"])
    return results
