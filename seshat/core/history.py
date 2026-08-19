"""Parsing e escrita de `01_history.md` — timeline + TL;DR mermaid gantt.

Regras (fonte: 20_frontmatter_schema.md, seções "Estrutura de timeline" e
"TL;DR visual em mermaid"):

- Entradas em ordem cronológica invertida no texto (mais nova no topo).
- Cada entrada: `## AAAA-MM-DD — Título curto`, linha-resumo, parágrafo detalhado.
- Bloco ```mermaid gantt``` logo após o frontmatter, ANTES da primeira entrada —
  um milestone por entrada, em ordem cronológica NORMAL (mais antiga primeiro),
  rótulo = linha-resumo. Regenerado inteiro a cada `append_history`.
- Histórico não fabricado: um 01_history.md pode existir só com frontmatter,
  sem nenhuma entrada — não inventar conteúdo pra preencher.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ENTRY_HEADER_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}) — (.+)$")
MERMAID_BLOCK_RE = re.compile(r"```mermaid\ngantt\n.*?\n```\n\n?", re.DOTALL)


@dataclass
class HistoryEntry:
    date: str  # AAAA-MM-DD
    title: str  # título curto do cabeçalho
    summary_line: str  # linha-resumo, estilo commit
    detail: str  # parágrafo(s) detalhado(s), markdown livre


def parse_entries(body: str) -> list[HistoryEntry]:
    """Extrai as entradas já existentes de um corpo de 01_history.md (sem o bloco mermaid).

    Assume ordem invertida no texto (mais nova primeiro) — devolve na mesma ordem
    em que aparecem no arquivo.
    """
    body_no_mermaid = MERMAID_BLOCK_RE.sub("", body, count=1)
    lines = body_no_mermaid.splitlines()

    entries: list[HistoryEntry] = []
    current_header: tuple[str, str] | None = None
    current_lines: list[str] = []

    def flush():
        if current_header is None:
            return
        date, title = current_header
        block = "\n".join(current_lines).strip("\n")
        summary_line, _, rest = block.partition("\n")
        entries.append(
            HistoryEntry(date=date, title=title, summary_line=summary_line.strip(), detail=rest.strip())
        )

    for line in lines:
        match = ENTRY_HEADER_RE.match(line)
        if match:
            flush()
            current_header = (match.group(1), match.group(2))
            current_lines = []
        elif current_header is not None:
            current_lines.append(line)
    flush()

    return entries


def render_entry(entry: HistoryEntry) -> str:
    parts = [f"## {entry.date} — {entry.title}", "", entry.summary_line]
    if entry.detail:
        parts += ["", entry.detail]
    return "\n".join(parts)


def render_gantt(entries_oldest_first: list[HistoryEntry]) -> str:
    """Bloco mermaid gantt, um milestone por entrada, ordem cronológica normal."""
    lines = ["```mermaid", "gantt", "    title Histórico — TL;DR", "    dateFormat YYYY-MM-DD", "    axisFormat %d/%m"]

    by_month: dict[str, list[HistoryEntry]] = {}
    for entry in entries_oldest_first:
        month = entry.date[:7]  # AAAA-MM
        by_month.setdefault(month, []).append(entry)

    milestone_n = 0
    for month in sorted(by_month):
        lines.append(f"    section {month}")
        for entry in by_month[month]:
            milestone_n += 1
            label = _mermaid_safe(entry.summary_line)
            lines.append(f"    {label} :milestone, m{milestone_n}, {entry.date}, 0d")

    lines.append("```")
    return "\n".join(lines)


def _mermaid_safe(text: str) -> str:
    # mermaid gantt não aceita ':' nem quebra de linha no rótulo de uma tarefa
    return text.replace(":", " -").replace("\n", " ").strip()


def render_history_body(entries_newest_first: list[HistoryEntry]) -> str:
    """Monta o corpo completo do 01_history.md: gantt + entradas (mais nova primeiro).

    `entries_newest_first` já deve incluir a entrada nova, na posição correta
    (topo). Se a lista estiver vazia, devolve só o gantt vazio comentado —
    "histórico não fabricado": não inventamos entrada nenhuma.
    """
    if not entries_newest_first:
        return "<!-- Sem entradas ainda — 01_history.md existe mas não há decisão real registrada. -->\n"

    oldest_first = list(reversed(entries_newest_first))
    gantt = render_gantt(oldest_first)
    rendered_entries = "\n\n".join(render_entry(e) for e in entries_newest_first)
    return f"{gantt}\n\n{rendered_entries}\n"
