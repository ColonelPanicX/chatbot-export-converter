"""Tests for load_all_conversations error handling."""

from __future__ import annotations

import json
from pathlib import Path

from chatbot_export_converter.converter import load_all_conversations


def test_malformed_json_emits_warning(tmp_path: Path, capsys) -> None:
    """A file that fails to parse emits a warning and is skipped."""
    bad = tmp_path / "conversations.json"
    bad.write_text("this is not json", encoding="utf-8")

    convs, files = load_all_conversations(tmp_path)

    assert convs == []
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert str(bad) in captured.err


def test_good_file_still_loads_after_bad_file(tmp_path: Path, capsys) -> None:
    """A bad file does not prevent subsequent good files from loading."""
    bad = tmp_path / "conversations-000.json"
    bad.write_text("{invalid", encoding="utf-8")

    good_convs = [{"id": "abc", "title": "ok", "mapping": {}}]
    good = tmp_path / "conversations-001.json"
    good.write_text(json.dumps(good_convs), encoding="utf-8")

    convs, files = load_all_conversations(tmp_path)

    assert len(convs) == 1
    assert convs[0]["id"] == "abc"
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()


def test_all_valid_files_load_cleanly(tmp_path: Path, capsys) -> None:
    """No warning emitted when all files parse successfully."""
    data = [{"id": "c1", "title": "Chat 1", "mapping": {}}]
    (tmp_path / "conversations.json").write_text(json.dumps(data), encoding="utf-8")

    convs, files = load_all_conversations(tmp_path)

    assert len(convs) == 1
    assert capsys.readouterr().err == ""
