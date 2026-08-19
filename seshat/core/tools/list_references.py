"""`list_references` — lista referências, filtra por type/field.

Cobre os dois formatos de referência (arquivo único direto na subpasta da área,
ou pasta com 00_index.md — ver 22_estrutura_pastas.md, "Referências: pasta é
sobre forma do conteúdo, não sobre type"): para o formato-pasta, só o
00_index.md é listado (mesmo espírito de list_projects); para arquivo único,
o próprio arquivo.
"""

from __future__ import annotations

from ..vault import VaultClient


def list_references(
    vault: VaultClient,
    *,
    area_slug: str | None = None,  # ex: "caligrafia" — subpasta de 03-References/
    type: str | None = None,
    field: str | None = None,
) -> list[dict]:
    """Varre `03-References/<area>/` e devolve um resumo por referência.

    Não lê o corpo nem `01_history.md` de referências em formato-pasta —
    pra isso, leitura direta via `VaultClient.read_note`/futuro `get_reference`.
    """
    under = f"03-References/{area_slug}" if area_slug else "03-References"
    results = []
    seen_index_dirs: set = set()

    for note in vault.iter_notes(under):
        fm = note.frontmatter
        if fm.get("category") != "reference":
            continue  # defensivo — ex: 01_history.md de uma referência-pasta não é a própria referência

        is_index = note.path.name == "00_index.md"
        if is_index:
            seen_index_dirs.add(note.path.parent)
        elif note.path.parent in seen_index_dirs or (note.path.parent / "00_index.md").is_file():
            continue  # arquivo de passo (10_x.md) dentro de uma referência-pasta — não lista solto

        if type and fm.get("type") != type:
            continue
        if field and fm.get("field") != field:
            continue

        area = note.path.relative_to(vault.root / "03-References").parts[0]
        results.append(
            {
                "area_slug": area,
                "path": note.relative_to(vault.root),
                "is_folder": is_index,
                "slug": note.path.parent.name if is_index else note.path.stem,
                "id": fm.get("id"),
                "title": fm.get("title"),
                "summary": fm.get("summary"),
                "type": fm.get("type"),
                "field": fm.get("field"),
                "updated_at": fm.get("updated_at"),
            }
        )

    results.sort(key=lambda r: (r["area_slug"], r["slug"]))
    return results
