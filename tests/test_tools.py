import pytest

from seshat.core.tools import append_history, create_fragment, create_project, get_project, list_projects
from seshat.core.vault import VaultError


def test_create_project_writes_index_and_empty_history(vault):
    result = create_project(
        vault,
        year_month="202608",
        slug="Projeto Teste",
        title="Projeto Teste",
        summary="Um projeto de teste.",
        field="Programação",
        project_type="comercial",
    )
    assert result["slug"] == "202608_projeto_teste"
    assert vault.exists("02-Projects/202608_projeto_teste/00_index.md")
    assert vault.exists("02-Projects/202608_projeto_teste/01_history.md")

    history_note = vault.read_note("02-Projects/202608_projeto_teste/01_history.md")
    assert "Sem entradas" in history_note.body


def test_create_project_duplicate_rejected(vault):
    kwargs = dict(
        year_month="202608",
        slug="dup",
        title="Dup",
        summary="s",
        field="Programação",
        project_type="comercial",
    )
    create_project(vault, **kwargs)
    with pytest.raises(VaultError, match="já existe"):
        create_project(vault, **kwargs)


def test_list_projects_filters_by_field_and_status(vault):
    create_project(
        vault, year_month="202608", slug="a", title="A", summary="s", field="Programação", project_type="x"
    )
    create_project(
        vault,
        year_month="202608",
        slug="b",
        title="B",
        summary="s",
        field="Caligrafia",
        project_type="x",
        project_status="in_progress",
    )

    all_projects = list_projects(vault)
    assert len(all_projects) == 2

    only_prog = list_projects(vault, field="Programação")
    assert [p["slug"] for p in only_prog] == ["202608_a"]

    only_in_progress = list_projects(vault, project_status="in_progress")
    assert [p["slug"] for p in only_in_progress] == ["202608_b"]


def test_get_project_reads_index_and_history(vault):
    create_project(
        vault, year_month="202608", slug="c", title="C", summary="s", field="Programação", project_type="x"
    )
    append_history(
        vault,
        history_relative_path="02-Projects/202608_c/01_history.md",
        date="2026-08-14",
        title="Início",
        summary_line="Projeto começou.",
        detail="Detalhe do início.",
    )

    project = get_project(vault, "202608_c")
    assert project["frontmatter"]["title"] == "C"
    assert len(project["history"]) == 1
    assert project["history"][0]["summary_line"] == "Projeto começou."


def test_get_project_missing_raises(vault):
    with pytest.raises(VaultError, match="não encontrado"):
        get_project(vault, "202608_nao_existe")


def test_append_history_accumulates_newest_first(vault):
    create_project(
        vault, year_month="202608", slug="d", title="D", summary="s", field="Programação", project_type="x"
    )
    path = "02-Projects/202608_d/01_history.md"

    append_history(vault, history_relative_path=path, date="2026-08-01", title="Um", summary_line="Primeira")
    append_history(vault, history_relative_path=path, date="2026-08-10", title="Dois", summary_line="Segunda")

    note = vault.read_note(path)
    gantt_end = note.body.index("```\n\n", note.body.index("```mermaid")) + len("```\n\n")
    gantt_block, entries_block = note.body[:gantt_end], note.body[gantt_end:]

    # gantt: mais antiga primeiro
    assert gantt_block.index("Primeira") < gantt_block.index("Segunda")
    # texto das entradas: mais nova primeiro
    assert entries_block.index("Segunda") < entries_block.index("Primeira")


def test_create_fragment_defaults(vault):
    result = create_fragment(
        vault,
        filename_slug="Ideia Solta",
        title="Ideia Solta",
        summary="Uma ideia qualquer.",
        field="Pessoal",
        body="Corpo do fragmento.",
    )
    assert result["path"] == "01-Fragments/ideia_solta.md"
    note = vault.read_note("01-Fragments/ideia_solta.md")
    assert note.frontmatter["triage_status"] == "pending"
    assert note.frontmatter["category"] == "fragment"
    assert note.frontmatter["type"] == "undefined"


def test_create_fragment_duplicate_rejected(vault):
    kwargs = dict(filename_slug="dup", title="Dup", summary="s", field="Pessoal", body="x")
    create_fragment(vault, **kwargs)
    with pytest.raises(VaultError, match="já existe"):
        create_fragment(vault, **kwargs)


def test_schema_rejects_invalid_field_on_create_fragment(vault):
    with pytest.raises(Exception):
        create_fragment(
            vault,
            filename_slug="bad",
            title="Bad",
            summary="s",
            field="Culinária",  # fora do vocabulário
            body="x",
        )
