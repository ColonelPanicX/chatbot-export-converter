"""Tests for duplicate conversation ID warning."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from chatbot_export_converter.converter import main


def _make_conv(cid: str, title: str) -> dict:
    return {
        "id": cid,
        "title": title,
        "create_time": 1700000000.0,
        "update_time": 1700000000.0,
        "current_node": "msg-1",
        "mapping": {
            "msg-1": {
                "id": "msg-1",
                "parent": None,
                "children": [],
                "message": {
                    "id": "msg-1",
                    "author": {"role": "user", "name": None, "metadata": {}},
                    "create_time": 1700000001.0,
                    "update_time": None,
                    "content": {"content_type": "text", "parts": [f"Hello from {title}"]},
                    "status": "finished_successfully",
                    "end_turn": False,
                    "weight": 1.0,
                    "metadata": {},
                    "recipient": "all",
                },
            },
        },
    }


def test_duplicate_id_emits_warning(tmp_path: Path, capsys) -> None:
    """A duplicate conversation ID emits a warning to stderr."""
    convs = [
        _make_conv("dup-id-001", "First"),
        _make_conv("dup-id-001", "Second"),  # duplicate
    ]
    (tmp_path / "conversations.json").write_text(json.dumps(convs), encoding="utf-8")
    out_dir = tmp_path / "out"

    with patch(
        "sys.argv",
        ["chatbot-convert", "--input", str(tmp_path), "--output", str(out_dir), "--dry-run"],
    ):
        main()

    captured = capsys.readouterr()
    assert "duplicate" in captured.err.lower()
    assert "dup-id-001" in captured.err


def test_duplicate_id_keeps_last(tmp_path: Path, capsys) -> None:
    """Last-write-wins behavior is preserved — the second title wins."""
    convs = [
        _make_conv("dup-id-002", "First Title"),
        _make_conv("dup-id-002", "Second Title"),
    ]
    (tmp_path / "conversations.json").write_text(json.dumps(convs), encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with patch("sys.argv", ["chatbot-convert", "--input", str(tmp_path), "--output", str(out_dir)]):
        main()

    conv_dirs = [p for p in out_dir.iterdir() if p.is_dir()]
    assert len(conv_dirs) == 1
    assert "second-title" in conv_dirs[0].name


def test_no_warning_for_unique_ids(tmp_path: Path, capsys) -> None:
    """No duplicate warning emitted when all conversation IDs are unique."""
    convs = [_make_conv("id-001", "Chat One"), _make_conv("id-002", "Chat Two")]
    (tmp_path / "conversations.json").write_text(json.dumps(convs), encoding="utf-8")
    out_dir = tmp_path / "out"

    with patch(
        "sys.argv",
        ["chatbot-convert", "--input", str(tmp_path), "--output", str(out_dir), "--dry-run"],
    ):
        main()

    assert "duplicate" not in capsys.readouterr().err.lower()
