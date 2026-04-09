"""Tests for YAML front matter output."""

from __future__ import annotations

from chatgpt_export_converter.converter import dump_yaml_front_matter


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
