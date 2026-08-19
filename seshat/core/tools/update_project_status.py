"""`update_project_status` — atualiza project_status/project_stage, sempre
pedindo (ou gerando) uma entrada de histórico.

Fonte: 10_arquitetura_seshat.md, tabela de ferramentas do MCP server. Nunca
muda status silenciosamente — toda chamada grava uma entrada em 01_history.md
via append_history, mesmo padrão de "toda decisão real nasce dentro de um
projeto e fica registrada no histórico" (20_frontmatter_schema.md, "Por que
não existe category: decision").
"""

from __future__ import annotations

from .append_history import append_history
from ..schema import ValidationContext
from ..vault import VaultClient, VaultError


def update_project_status(
    vault: VaultClient,
    *,
    slug: str,  # pasta em 02-Projects/, formato YYYYMM_slug
    date: str,  # "AAAA-MM-DD" — data da mudança, pra entrada de histórico
    project_status: str | None = None,
    project_stage: str | None = None,
    summary_line: str | None = None,  # linha-resumo da entrada de histórico; gerada se ausente
    detail: str = "",
) -> dict:
    if project_status is None and project_stage is None:
        raise VaultError("update_project_status precisa de project_status e/ou project_stage")

    project_dir = f"02-Projects/{slug}"
    index_path = f"{project_dir}/00_index.md"
    history_path = f"{project_dir}/01_history.md"

    if not vault.exists(index_path):
        raise VaultError(f"projeto não encontrado: {slug} (esperava {index_path})")

    note = vault.read_note(index_path)
    fm = dict(note.frontmatter)

    old_status = fm.get("project_status")
    old_stage = fm.get("project_stage")

    changes = []
    if project_status is not None and project_status != old_status:
        fm["project_status"] = project_status
        changes.append(f"project_status: {old_status!r} → {project_status!r}")
    if project_stage is not None and project_stage != old_stage:
        fm["project_stage"] = project_stage
        changes.append(f"project_stage: {old_stage!r} → {project_stage!r}")

    if not changes:
        raise VaultError("nenhuma mudança real — valores informados já são os atuais")

    updated_note = vault.write_note(
        index_path,
        fm,
        note.body,
        ctx=ValidationContext(is_project_index=True),
        category="project",
        field_value=fm.get("field"),
        slug=slug,
        overwrite=True,
    )

    history_result = None
    if vault.exists(history_path):
        title = "Status atualizado"
        line = summary_line or "; ".join(changes)
        history_result = append_history(
            vault,
            history_relative_path=history_path,
            date=date,
            title=title,
            summary_line=line,
            detail=detail,
        )

    return {
        "slug": slug,
        "changes": changes,
        "frontmatter": updated_note.frontmatter,
        "history": history_result,
    }
