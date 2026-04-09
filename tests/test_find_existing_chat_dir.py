"""Tests for find_existing_chat_dir collision detection."""

from __future__ import annotations

from pathlib import Path

from chatgpt_export_converter.converter import find_existing_chat_dir


def test_returns_none_when_output_dir_missing(tmp_path: Path) -> None:
    result = find_existing_chat_dir(tmp_path / "nonexistent", "abc123")
    assert result is None


def test_returns_none_when_no_match(tmp_path: Path) -> None:
    (tmp_path / "2024-01-01__other-chat__xyz999").mkdir()
    result = find_existing_chat_dir(tmp_path, "abc123")
    assert result is None


def test_returns_match_when_one_exists(tmp_path: Path) -> None:
    expected = tmp_path / "2024-01-01__my-chat__abc123"
    expected.mkdir()
    result = find_existing_chat_dir(tmp_path, "abc123")
    assert result == expected


def test_warns_and_returns_first_on_collision(tmp_path: Path, capsys) -> None:
    (tmp_path / "2024-01-01__first__abc123").mkdir()
    (tmp_path / "2024-06-01__second__abc123").mkdir()

    result = find_existing_chat_dir(tmp_path, "abc123")

    assert result is not None
    assert result.name == "2024-01-01__first__abc123"
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert "abc123" in captured.err


def test_no_warning_for_single_match(tmp_path: Path, capsys) -> None:
    (tmp_path / "2024-01-01__chat__abc123").mkdir()
    find_existing_chat_dir(tmp_path, "abc123")
    assert capsys.readouterr().err == ""
