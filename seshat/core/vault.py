"""Leitura/escrita de markdown com frontmatter no vault Akasha.

Camada fina sobre o disco — não sabe nada sobre `list_projects`/`create_fragment`/etc,
só sabe ler e escrever notas respeitando o schema (`schema.py`).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from .schema import ValidationContext, apply_write_defaults, validate_frontmatter


class VaultError(ValueError):
    pass


@dataclass
class Note:
    path: Path
    frontmatter: dict
    body: str

    def relative_to(self, root: Path) -> str:
        return str(self.path.relative_to(root))


class VaultClient:
    """Aponta pra raiz de um vault Akasha (produção ou clone de teste)."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise VaultError(f"raiz do vault não existe: {self.root}")

    # --- leitura ---

    def read_note(self, relative_path: str) -> Note:
        path = self.root / relative_path
        if not path.is_file():
            raise VaultError(f"nota não encontrada: {relative_path}")
        post = frontmatter.load(path)
        return Note(path=path, frontmatter=dict(post.metadata), body=post.content)

    def exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).is_file()

    def iter_notes(self, under: str) -> list[Note]:
        """Lê toda nota .md sob `under` (relativo à raiz do vault)."""
        base = self.root / under
        if not base.is_dir():
            return []
        notes = []
        for path in sorted(base.rglob("*.md")):
            try:
                post = frontmatter.load(path)
            except Exception as exc:  # arquivo malformado não derruba a listagem inteira
                raise VaultError(f"falha ao ler {path.relative_to(self.root)}: {exc}") from exc
            notes.append(Note(path=path, frontmatter=dict(post.metadata), body=post.content))
        return notes

    # --- escrita ---

    def write_note(
        self,
        relative_path: str,
        fm: dict,
        body: str,
        *,
        ctx: ValidationContext,
        category: str,
        field_value: str,
        slug: str,
        overwrite: bool = False,
    ) -> Note:
        """Valida e grava. Nunca sobrescreve sem `overwrite=True` explícito —
        `01_history.md` nunca deve ser sobrescrito por esta via (usar `append_history`)."""
        path = self.root / relative_path
        is_new = not path.is_file()
        if not is_new and not overwrite:
            raise VaultError(
                f"'{relative_path}' já existe — use overwrite=True (evite pra 01_history.md; "
                "use append_history em vez disso)"
            )

        fm_final = apply_write_defaults(fm, is_new=is_new, category=category, field_value=field_value, slug=slug)
        validate_frontmatter(fm_final, ctx)

        path.parent.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post(body, **fm_final)
        path.write_bytes(frontmatter.dumps(post).encode("utf-8"))
        return Note(path=path, frontmatter=fm_final, body=body)


def slugify(text: str) -> str:
    """snake_case sem acentos, pro nome de arquivo/pasta — não é o `id`."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return normalized or "sem_titulo"


def project_folder_name(year_month: str, slug: str) -> str:
    """`YYYYMM_slug`, convenção fixa de `20_frontmatter_schema.md` ("Nome de pasta de projeto")."""
    if not re.fullmatch(r"\d{6}", year_month):
        raise VaultError(f"year_month deve ser 'YYYYMM', recebido: {year_month!r}")
    return f"{year_month}_{slugify(slug)}"
