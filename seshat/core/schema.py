"""Validação do schema de frontmatter do vault Akasha.

Espelha `seixu/akasha/20_frontmatter_schema.md` e `seixu/akasha/21_vocabulario_type.md`
do vault — qualquer mudança de vocabulário deve ser feita nos dois lugares.

Este módulo não decide *onde* gravar (isso é `vault.py`); só decide se um
frontmatter é válido antes de ir pro disco.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


class SchemaValidationError(ValueError):
    """Frontmatter não passa na validação — nunca deve ser gravado no vault."""


# --- Vocabulário fechado (fonte: 20_frontmatter_schema.md / 21_vocabulario_type.md) ---

CATEGORIES = {"project", "reference", "fragment"}

FIELDS = {
    "Programação",
    "Artes",
    "Design",
    "Caligrafia",
    "Costura",
    "Pesquisa",
    "Pessoal",
    "Imagem",
    "Som",
    "Textos",
}

PROJECT_STATUSES = {
    "planning",
    "todo",
    "in_progress",
    "in_review",
    "done",
    "paused",
    "cancelled",
}

PROJECT_STAGES = {"call", "quote", "planning", "production", "delivered"}

TRIAGE_STATUSES = {"pending", "deferred", "waiting"}

# type: undefined é um valor válido de propósito (ver 21_vocabulario_type.md,
# seção "Não passa no teste") — não é ausência de type, é o valor explícito
# pra conteúdo que ainda não tem forma repetível.
TYPES = {
    "index",
    "budget",
    "meeting-log",
    "technique",
    "history",
    "purchase-log",
    "schedule",
    "material-spec",
    "spatial-plan",
    "graph",
    "business",
    "report",
    "set",
    "reading-notes",
    "inventory",
    "document",  # conteúdo em elaboração — único type que aceita o campo `status`
    "undefined",
}

# NOTA: 20_frontmatter_schema.md descreve `ai_access` como "vocabulário fechado"
# mas não enumera os valores. Assumindo read_write/read_only até o vault
# documentar o vocabulário completo — revisar quando a Fase 3 formalizar isso.
AI_ACCESS_VALUES = {"read_write", "read_only"}

STATUS_VALUES = {"draft", "in_review", "final"}


@dataclass
class ValidationContext:
    """Contexto necessário pra validar regras condicionais do schema.

    `is_project_index` = este arquivo é o 00_index.md de uma pasta
    02-Projects/<slug>/? Só ele pode carregar project_type/status/stage/khaos_project_id.
    """

    is_project_index: bool = False
    is_fragment: bool = False


def _require_in(value, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise SchemaValidationError(
            f"'{field_name}' = {value!r} não está no vocabulário fechado: {sorted(allowed)}"
        )


def validate_frontmatter(fm: dict, ctx: ValidationContext) -> None:
    """Regras 1-3 de `20_frontmatter_schema.md`, seção Validação.

    Levanta SchemaValidationError na primeira violação — nunca silenciosa.
    Não muta `fm`; use `apply_write_defaults` pra isso (regras 4-5).
    """
    # Campos sempre obrigatórios
    for required in ("id", "category", "type", "title", "summary", "field", "created_at", "updated_at"):
        if not fm.get(required):
            raise SchemaValidationError(f"campo obrigatório ausente ou vazio: '{required}'")

    # Regra 1 — vocabulário fechado
    _require_in(fm["category"], CATEGORIES, "category")
    _require_in(fm["field"], FIELDS, "field")
    _require_in(fm["type"], TYPES, "type")

    if "project_status" in fm and fm["project_status"] is not None:
        _require_in(fm["project_status"], PROJECT_STATUSES, "project_status")
    if "project_stage" in fm and fm["project_stage"] is not None:
        _require_in(fm["project_stage"], PROJECT_STAGES, "project_stage")
    if "triage_status" in fm and fm["triage_status"] is not None:
        _require_in(fm["triage_status"], TRIAGE_STATUSES, "triage_status")
    if "ai_access" in fm and fm["ai_access"] is not None:
        _require_in(fm["ai_access"], AI_ACCESS_VALUES, "ai_access")

    # Regra 2 — `status` só em type: document (conteúdo em elaboração)
    if "status" in fm and fm["status"] is not None:
        if fm.get("type") != "document":
            raise SchemaValidationError(
                "'status' só é válido quando type == 'document' (conteúdo em elaboração); "
                f"encontrado type={fm.get('type')!r}"
            )
        _require_in(fm["status"], STATUS_VALUES, "status")

    # Regra 3 — campos de projeto só no 00_index.md de category: project
    project_only_fields = ("project_type", "project_status", "project_stage", "khaos_project_id")
    has_project_field = any(fm.get(f) is not None for f in project_only_fields)
    if has_project_field and not ctx.is_project_index:
        raise SchemaValidationError(
            "project_type/project_status/project_stage/khaos_project_id só podem "
            "aparecer no 00_index.md de uma pasta category: project"
        )
    if ctx.is_project_index and fm.get("category") != "project":
        raise SchemaValidationError("is_project_index=True mas category != 'project'")

    if "triage_status" in fm and fm["triage_status"] is not None and not ctx.is_fragment:
        raise SchemaValidationError("'triage_status' só é válido em category: fragment")
    if ctx.is_fragment and fm.get("category") != "fragment":
        raise SchemaValidationError("is_fragment=True mas category != 'fragment'")

    if "used_in" in fm and fm["used_in"] is not None and fm.get("category") != "reference":
        raise SchemaValidationError("'used_in' só é válido em category: reference")


def generate_id(category: str, field_value: str, slug: str) -> str:
    """Regra 4 — gera `id` quando ausente.

    Convenção observada no vault (não formalizada em doc, inferida dos exemplos
    reais: `akasha-frontmatter-schema`, `ref-konnyaku-nori`,
    `pessoal-fragment-cuba-da-cozinha`): `<prefixo-de-area>-<categoria-quando-nao-obvia>-<slug>`.
    Fragmentos e referências levam a categoria no id; projetos geralmente não
    (o slug `YYYYMM_slug` já é identificador suficiente). Ajustável — não é
    regra fechada do schema, só uma convenção a manter consistente até virar
    documentação formal.
    """
    field_slug = field_value.lower().replace(" ", "-")
    if category == "project":
        return slug
    return f"{field_slug}-{category}-{slug}"


def now_iso(tz_offset_hours: int = -3) -> str:
    """timestamptz no formato usado no vault: ISO 8601 com offset explícito.

    Assume horário de Brasília (-03:00) por padrão, igual a todo exemplo no
    schema (`2026-06-03T14:30:00-03:00`). O vault não guarda em UTC.
    """
    tz = timezone(timedelta_hours(tz_offset_hours))
    return datetime.now(tz).replace(microsecond=0).isoformat()


def timedelta_hours(hours: int):
    from datetime import timedelta

    return timedelta(hours=hours)


def apply_write_defaults(fm: dict, *, is_new: bool, category: str, field_value: str, slug: str) -> dict:
    """Regras 4-5 — completa id/timestamps antes de gravar. Retorna uma cópia."""
    fm = dict(fm)
    if not fm.get("id"):
        fm["id"] = generate_id(category, field_value, slug)
    fm.setdefault("ai_access", "read_write")
    fm.setdefault("tags", [])

    ts = now_iso()
    if is_new:
        fm["created_at"] = fm.get("created_at") or ts
        fm["updated_at"] = fm["created_at"]
    else:
        fm["updated_at"] = ts
    return fm
