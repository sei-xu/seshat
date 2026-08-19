"""Renders tool results as Telegram-friendly (MarkdownV2-escaped) text."""

from __future__ import annotations

_MDV2_SPECIAL = r"_*[]()~`>#+-=|{}.!"


def escape_md(text: object) -> str:
    """Escape a value for Telegram MarkdownV2."""
    s = str(text)
    return "".join(f"\\{c}" if c in _MDV2_SPECIAL else c for c in s)


def format_project_summary(p: dict) -> str:
    return (
        f"*{escape_md(p.get('title') or p.get('slug'))}*\n"
        f"slug: `{escape_md(p.get('slug'))}`\n"
        f"campo: {escape_md(p.get('field'))} · tipo: {escape_md(p.get('project_type'))}\n"
        f"status: {escape_md(p.get('project_status'))} · etapa: {escape_md(p.get('project_stage'))}\n"
        f"{escape_md(p.get('summary') or '')}"
    )


def format_projects_list(projects: list[dict]) -> str:
    if not projects:
        return "Nenhum projeto encontrado\\."
    lines = [f"*{len(projects)} projeto\\(s\\)*"]
    for p in projects:
        lines.append(
            f"• `{escape_md(p.get('slug'))}` — {escape_md(p.get('title'))} "
            f"\\[{escape_md(p.get('project_status'))}/{escape_md(p.get('project_stage'))}\\]"
        )
    return "\n".join(lines)


def format_project_detail(result: dict) -> str:
    fm = result.get("frontmatter", {})
    lines = [
        f"*{escape_md(fm.get('title'))}*",
        f"slug: `{escape_md(result.get('slug'))}`",
        f"campo: {escape_md(fm.get('field'))} · tipo: {escape_md(fm.get('project_type'))}",
        f"status: {escape_md(fm.get('project_status'))} · etapa: {escape_md(fm.get('project_stage'))}",
        escape_md(fm.get("summary") or ""),
        "",
        "*Histórico:*",
    ]
    history = result.get("history", [])
    if not history:
        lines.append("_sem entradas_")
    for e in history[:10]:
        lines.append(f"• {escape_md(e.get('date'))} — *{escape_md(e.get('title'))}*: {escape_md(e.get('summary_line'))}")
    if len(history) > 10:
        lines.append(f"_\\.\\.\\. e mais {len(history) - 10} entrada\\(s\\)_")
    return "\n".join(lines)


def format_references_list(refs: list[dict]) -> str:
    if not refs:
        return "Nenhuma referência encontrada\\."
    lines = [f"*{len(refs)} referência\\(s\\)*"]
    for r in refs:
        lines.append(f"• `{escape_md(r.get('area_slug'))}/{escape_md(r.get('slug'))}` — {escape_md(r.get('title'))}")
    return "\n".join(lines)


def format_search_results(results: list[dict]) -> str:
    if not results:
        return "Nenhum resultado encontrado\\."
    lines = [f"*{len(results)} resultado\\(s\\)*"]
    for r in results[:25]:
        lines.append(f"• \\[{escape_md(r.get('category'))}\\] `{escape_md(r.get('path'))}` — {escape_md(r.get('title'))}")
    if len(results) > 25:
        lines.append(f"_\\.\\.\\. e mais {len(results) - 25} resultado\\(s\\)_")
    return "\n".join(lines)


def format_error(exc: Exception) -> str:
    return f"⚠️ *Erro:* {escape_md(str(exc))}"
