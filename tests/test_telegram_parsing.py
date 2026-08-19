import pytest

from seshat.telegram.parsing import ArgParseError, parse_kv_args, require, split_list


def test_parse_kv_args_basic():
    assert parse_kv_args("slug=teste title=Teste") == {"slug": "teste", "title": "Teste"}


def test_parse_kv_args_quoted_value_with_spaces():
    assert parse_kv_args('title="Café com leite" field=Programação') == {
        "title": "Café com leite",
        "field": "Programação",
    }


def test_parse_kv_args_empty():
    assert parse_kv_args("") == {}


def test_parse_kv_args_missing_equals_raises():
    with pytest.raises(ArgParseError):
        parse_kv_args("slug teste")


def test_parse_kv_args_unclosed_quote_raises():
    with pytest.raises(ArgParseError):
        parse_kv_args('title="unclosed')


def test_require_all_present():
    require({"a": "1", "b": "2"}, "a", "b")  # não levanta


def test_require_missing_lists_all():
    with pytest.raises(ArgParseError, match="a, b"):
        require({}, "a", "b")


def test_split_list_none():
    assert split_list(None) is None
    assert split_list("") is None


def test_split_list_values():
    assert split_list("a, b ,c") == ["a", "b", "c"]
