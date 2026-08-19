import pytest

from seshat.core.tools import (
    create_project,
    create_reference,
    list_references,
    search_vault,
    update_project_status,
)
from seshat.core.vault import VaultError


# --- create_reference / list_references ---


def test_create_reference_flat_file(vault):
    result = create_reference(
        vault,
        area_slug="Programação",
        slug="Serviços",
        title="Serviços",
        summary="Lista de serviços oferecidos.",
        field="Programação",
        type="business",
        body="Corpo da referência.",
    )
    assert result["is_folder"] is False
    assert result["path"] == "03-References/programacao/servicos.md"
    note = vault.read_note("03-References/programacao/servicos.md")
    assert note.frontmatter["category"] == "reference"
    assert note.frontmatter["type"] == "business"


def test_create_reference_as_folder_gets_index_and_empty_history(vault):
    result = create_reference(
        vault,
        area_slug="caligrafia",
        slug="Montagem Kakejiku",
        title="Montagem de Kakejiku",
        summary="Técnica de montagem.",
        field="Caligrafia",
        type="technique",
        as_folder=True,
    )
    assert result["is_folder"] is True
    assert vault.exists("03-References/caligrafia/montagem_kakejiku/00_index.md")
    assert vault.exists("03-References/caligrafia/montagem_kakejiku/01_history.md")
    history_note = vault.read_note("03-References/caligrafia/montagem_kakejiku/01_history.md")
    assert "Sem entradas" in history_note.body


def test_create_reference_duplicate_rejected(vault):
    kwargs = dict(
        area_slug="programacao",
        slug="dup",
        title="Dup",
        summary="s",
        field="Programação",
        type="business",
    )
    create_reference(vault, **kwargs)
    with pytest.raises(VaultError, match="já existe"):
        create_reference(vault, **kwargs)


def test_list_references_mixes_flat_and_folder_but_only_lists_index_for_folder(vault):
    create_reference(
        vault, area_slug="programacao", slug="a", title="A", summary="s", field="Programação", type="business"
    )
    create_reference(
        vault,
        area_slug="programacao",
        slug="b",
        title="B",
        summary="s",
        field="Programação",
        type="technique",
        as_folder=True,
    )

    results = list_references(vault, area_slug="programacao")
    assert len(results) == 2
    slugs = {r["slug"] for r in results}
    assert slugs == {"a", "b"}


def test_list_references_filters_by_type(vault):
    create_reference(
        vault, area_slug="programacao", slug="a", title="A", summary="s", field="Programação", type="business"
    )
    create_reference(
        vault, area_slug="programacao", slug="c", title="C", summary="s", field="Programação", type="technique"
    )

    only_technique = list_references(vault, type="technique")
    assert [r["slug"] for r in only_technique] == ["c"]


# --- update_project_status ---


def test_update_project_status_changes_fields_and_appends_history(vault):
    create_project(
        vault, year_month="202608", slug="e", title="E", summary="s", field="Programação", project_type="x"
    )

    result = update_project_status(
        vault,
        slug="202608_e",
        date="2026-08-14",
        project_status="in_progress",
        project_stage="production",
    )
    assert "project_status: 'planning' → 'in_progress'" in result["changes"]
    assert result["history"]["entry_count"] == 1

    note = vault.read_note("02-Projects/202608_e/00_index.md")
    assert note.frontmatter["project_status"] == "in_progress"
    assert note.frontmatter["project_stage"] == "production"


def test_update_project_status_no_change_rejected(vault):
    create_project(
        vault, year_month="202608", slug="f", title="F", summary="s", field="Programação", project_type="x"
    )
    with pytest.raises(VaultError, match="nenhuma mudança"):
        update_project_status(vault, slug="202608_f", date="2026-08-14", project_status="planning")


def test_update_project_status_missing_project_raises(vault):
    with pytest.raises(VaultError, match="não encontrado"):
        update_project_status(vault, slug="202608_nao_existe", date="2026-08-14", project_status="done")


# --- search_vault ---


def test_search_vault_by_query_matches_title_and_body(vault):
    create_project(
        vault,
        year_month="202608",
        slug="etto",
        title="Etto",
        summary="Assistente pessoal via Telegram.",
        field="Programação",
        project_type="business",
    )

    results = search_vault(vault, query="telegram")
    assert len(results) == 1
    assert results[0]["title"] == "Etto"


def test_search_vault_by_field(vault):
    create_project(
        vault, year_month="202608", slug="g", title="G", summary="s", field="Caligrafia", project_type="x"
    )
    create_project(
        vault, year_month="202608", slug="h", title="H", summary="s", field="Programação", project_type="x"
    )

    results = search_vault(vault, field="Caligrafia")
    assert {r["title"] for r in results} == {"G", "G — Histórico"}


def test_search_vault_requires_at_least_one_criterion(vault):
    with pytest.raises(ValueError, match="ao menos um critério"):
        search_vault(vault)
