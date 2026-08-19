import pytest

from seshat.core.schema import SchemaValidationError, ValidationContext, validate_frontmatter


def _base_fm(**overrides):
    fm = {
        "id": "x",
        "category": "fragment",
        "type": "undefined",
        "title": "t",
        "summary": "s",
        "field": "Pessoal",
        "created_at": "2026-08-14T00:00:00-03:00",
        "updated_at": "2026-08-14T00:00:00-03:00",
    }
    fm.update(overrides)
    return fm


def test_valid_fragment_passes():
    validate_frontmatter(_base_fm(triage_status="pending"), ValidationContext(is_fragment=True))


def test_invalid_category_rejected():
    with pytest.raises(SchemaValidationError, match="category"):
        validate_frontmatter(_base_fm(category="nota"), ValidationContext())


def test_invalid_field_rejected():
    with pytest.raises(SchemaValidationError, match="field"):
        validate_frontmatter(_base_fm(field="Culinária"), ValidationContext())


def test_project_fields_rejected_outside_index():
    fm = _base_fm(category="project", project_status="planning")
    with pytest.raises(SchemaValidationError, match="project_type/project_status"):
        validate_frontmatter(fm, ValidationContext(is_project_index=False))


def test_project_fields_allowed_on_index():
    fm = _base_fm(
        category="project",
        type="index",
        project_type="comercial",
        project_status="planning",
        project_stage="call",
    )
    validate_frontmatter(fm, ValidationContext(is_project_index=True))


def test_triage_status_rejected_outside_fragment():
    fm = _base_fm(category="reference", triage_status="pending")
    with pytest.raises(SchemaValidationError, match="triage_status"):
        validate_frontmatter(fm, ValidationContext(is_fragment=False))


def test_status_rejected_outside_document_type():
    fm = _base_fm(status="draft")
    with pytest.raises(SchemaValidationError, match="status"):
        validate_frontmatter(fm, ValidationContext())


def test_status_allowed_on_document_type():
    fm = _base_fm(type="document", status="draft")
    validate_frontmatter(fm, ValidationContext())


def test_missing_required_field_rejected():
    fm = _base_fm()
    del fm["summary"]
    with pytest.raises(SchemaValidationError, match="summary"):
        validate_frontmatter(fm, ValidationContext(is_fragment=True))


def test_used_in_rejected_outside_reference():
    fm = _base_fm(category="fragment", used_in=["algo"])
    with pytest.raises(SchemaValidationError, match="used_in"):
        validate_frontmatter(fm, ValidationContext(is_fragment=True))
