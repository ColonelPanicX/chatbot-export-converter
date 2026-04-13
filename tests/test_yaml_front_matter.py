"""Tests for YAML front matter output."""

from __future__ import annotations

from chatgpt_export_converter.converter import _yaml_str, dump_yaml_front_matter

# ---------------------------------------------------------------------------
# _yaml_str escaping
# ---------------------------------------------------------------------------


def test_yaml_str_plain() -> None:
    assert _yaml_str("hello") == '"hello"'


def test_yaml_str_escapes_double_quotes() -> None:
    assert _yaml_str('say "hi"') == '"say \\"hi\\""'


def test_yaml_str_escapes_backslash() -> None:
    assert _yaml_str("a\\b") == '"a\\\\b"'


def test_yaml_str_empty() -> None:
    assert _yaml_str("") == '""'


# ---------------------------------------------------------------------------
# dump_yaml_front_matter
# ---------------------------------------------------------------------------


def test_archived_false_is_bare_boolean() -> None:
    conv = {"id": "c1", "title": "Test", "is_archived": False}
    output = dump_yaml_front_matter(conv)
    assert "archived: false" in output
    assert 'archived: "false"' not in output


def test_archived_true_is_bare_boolean() -> None:
    conv = {"id": "c1", "title": "Test", "is_archived": True}
    output = dump_yaml_front_matter(conv)
    assert "archived: true" in output
    assert 'archived: "true"' not in output


def test_archived_missing_defaults_false() -> None:
    conv = {"id": "c1", "title": "Test"}
    output = dump_yaml_front_matter(conv)
    assert "archived: false" in output


def test_title_with_quotes_is_escaped() -> None:
    conv = {"id": "c1", "title": 'She said "hello"'}
    output = dump_yaml_front_matter(conv)
    assert 'title: "She said \\"hello\\""' in output


def test_conversation_id_with_quotes_is_escaped() -> None:
    conv = {"id": 'id-"weird"', "title": "Test"}
    output = dump_yaml_front_matter(conv)
    assert 'conversation_id: "id-\\"weird\\""' in output
