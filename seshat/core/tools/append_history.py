"""`append_history` — adiciona entrada datada a um 01_history.md. Nunca sobrescreve, só acrescenta.

Regenera o bloco mermaid gantt inteiro a cada chamada (ver `history.py`) —
nunca fica dessincronizado do texto.
"""

from __future__ import annotations

from ..history import HistoryEntry, parse_entries, render_history_body
from ..schema import ValidationContext
from ..vault import VaultClient, VaultError


def append_history(
    vault: VaultClient,
    *,
    history_relative_path: str,  # ex: "02-Projects/202608_foo/01_history.md"
    date: str,  # "AAAA-MM-DD"
    title: str,  # título curto do cabeçalho
    summary_line: str,  # linha-resumo, estilo commit
    detail: str = "",  # parágrafo detalhado (pode ficar vazio)
) -> dict:
    if not vault.exists(history_relative_path):
        raise VaultError(f"01_history.md não encontrado: {history_relative_path}")

    note = vault.read_note(history_relative_path)
    existing_entries_newest_first = parse_entries(note.body)  # já vem na ordem do arquivo (mais nova primeiro)

    new_entry = HistoryEntry(date=date, title=title, summary_line=summary_line, detail=detail)
    all_entries_newest_first = [new_entry, *existing_entries_newest_first]

    new_body = render_history_body(all_entries_newest_first)

    updated_note = vault.write_note(
        history_relative_path,
        note.frontmatter,
        new_body,
        ctx=ValidationContext(),
        category=note.frontmatter.get("category", "project"),
        field_value=note.frontmatter.get("field"),
        slug=note.path.parent.name,
        overwrite=True,  # única ferramenta autorizada a "sobrescrever" um 01_history.md —
        # na prática é acréscimo: a entrada anterior nunca é removida, só o
        # arquivo inteiro (gantt + entradas) é regravado com a entrada nova no topo.
    )

    return {
        "path": updated_note.relative_to(vault.root),
        "entry_count": len(all_entries_newest_first),
        "frontmatter": updated_note.frontmatter,
    }
