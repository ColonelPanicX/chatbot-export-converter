"""Tests for atomic write / temp-dir-then-rename behavior in render_conversation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from chatbot_export_converter.converter import Summary, render_conversation


def _simple_conversation(cid: str = "test-conv-001") -> dict:
    return {
        "id": cid,
        "title": "Test Conversation",
        "create_time": 1700000000.0,
        "update_time": 1700000000.0,
        "current_node": "msg-2",
        "is_archived": False,
        "mapping": {
            "msg-1": {
                "id": "msg-1",
                "parent": None,
                "children": ["msg-2"],
                "message": {
                    "id": "msg-1",
                    "author": {"role": "user", "name": None, "metadata": {}},
                    "create_time": 1700000001.0,
                    "update_time": None,
                    "content": {"content_type": "text", "parts": ["Hello"]},
                    "status": "finished_successfully",
                    "end_turn": False,
                    "weight": 1.0,
                    "metadata": {},
                    "recipient": "all",
                },
            },
            "msg-2": {
                "id": "msg-2",
                "parent": "msg-1",
                "children": [],
                "message": {
                    "id": "msg-2",
                    "author": {"role": "assistant", "name": None, "metadata": {}},
                    "create_time": 1700000002.0,
                    "update_time": None,
                    "content": {"content_type": "text", "parts": ["Hi there!"]},
                    "status": "finished_successfully",
                    "end_turn": True,
                    "weight": 1.0,
                    "metadata": {},
                    "recipient": "all",
                },
            },
        },
    }


def test_output_written_to_desired_dir(tmp_path: Path) -> None:
    """Successful render produces transcript.md and metadata.json in the expected dir."""
    conv = _simple_conversation()
    summary = Summary()
    render_conversation(conv, tmp_path, tmp_path, {}, [], summary, dry_run=False, incremental=False)

    assert summary.conversations_processed == 1
    output_dirs = [p for p in tmp_path.iterdir() if p.is_dir() and not p.name.startswith(".tmp")]
    assert len(output_dirs) == 1
    chat_dir = output_dirs[0]
    assert (chat_dir / "transcript.md").exists()
    assert not (chat_dir / "metadata.json").exists()


def test_no_temp_dir_left_on_success(tmp_path: Path) -> None:
    """No .tmp-* directory remains after a successful render."""
    conv = _simple_conversation()
    render_conversation(
        conv, tmp_path, tmp_path, {}, [], Summary(), dry_run=False, incremental=False
    )

    leftover_tmp = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp")]
    assert leftover_tmp == [], f"Temp dirs left behind: {leftover_tmp}"


def test_temp_dir_cleaned_up_on_write_failure(tmp_path: Path) -> None:
    """If a write fails mid-render, the temp dir is removed and no partial output exists."""
    conv = _simple_conversation("fail-conv-001")

    with patch(
        "chatbot_export_converter.converter.dump_yaml_front_matter",
        side_effect=RuntimeError("simulated write failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated write failure"):
            render_conversation(
                conv, tmp_path, tmp_path, {}, [], Summary(), dry_run=False, incremental=False
            )

    # No .tmp dirs left
    leftover_tmp = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp")]
    assert leftover_tmp == [], f"Temp dirs left behind: {leftover_tmp}"

    # No partial output dir written
    output_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert output_dirs == []


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    """dry_run=True leaves the output directory completely empty."""
    conv = _simple_conversation()
    summary = Summary()
    render_conversation(conv, tmp_path, tmp_path, {}, [], summary, dry_run=True, incremental=False)

    assert summary.conversations_processed == 1
    assert list(tmp_path.iterdir()) == []
