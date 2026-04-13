"""Tests for CLI menu helpers."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from unittest.mock import patch

from chatgpt_export_converter.converter import (
    _find_zip_in_dir,
    _output_folder_name,
    _prompt_output_dir,
    detect_format_from_path,
)

# All interactive prompts go through three thin wrappers:
#   _ask_select(message, choices) -> str
#   _ask_path(message, only_directories=False) -> str
#   _ask_confirm(message, default=True) -> bool
# Tests patch these so no real terminal is needed.
_MOD = "chatgpt_export_converter.converter"


def test_output_folder_name_format() -> None:
    """Output folder name matches chatgpt-convert-MM.DD.YYYY."""
    name = _output_folder_name()
    assert re.match(
        r"chatgpt-convert-\d{2}\.\d{2}\.\d{4}$", name
    ), f"Unexpected folder name format: {name}"


def test_find_zip_in_dir_single(tmp_path: Path) -> None:
    """Returns the single zip found in the directory without prompting."""
    (tmp_path / "export.zip").touch()
    result = _find_zip_in_dir(tmp_path)
    assert result == tmp_path / "export.zip"


def test_find_zip_in_dir_none(tmp_path: Path) -> None:
    """Returns None when no zip files are present."""
    (tmp_path / "conversations.json").touch()
    result = _find_zip_in_dir(tmp_path)
    assert result is None


def test_find_zip_in_dir_multiple_prompts(tmp_path: Path) -> None:
    """Uses _ask_select when multiple zips are found; returns chosen zip."""
    za = tmp_path / "export-a.zip"
    zb = tmp_path / "export-b.zip"
    za.touch()
    zb.touch()
    with patch(f"{_MOD}._ask_select", return_value=str(za)):
        result = _find_zip_in_dir(tmp_path)
    assert result == za


def test_prompt_output_dir_default(tmp_path: Path) -> None:
    """Selecting the default option returns input_path.parent / folder_name."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    with patch(f"{_MOD}._ask_select", return_value="__default__"):
        result = _prompt_output_dir(input_path)
    assert result.parent == tmp_path
    assert result.name.startswith("chatgpt-convert-")


def test_prompt_output_dir_custom(tmp_path: Path) -> None:
    """Selecting custom and entering a path places the dated folder inside it."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    custom_parent = tmp_path / "custom"
    with (
        patch(f"{_MOD}._ask_select", return_value="__custom__"),
        patch(f"{_MOD}._ask_path", return_value=str(custom_parent)),
    ):
        result = _prompt_output_dir(input_path)
    assert result.parent == custom_parent
    assert result.name.startswith("chatgpt-convert-")


def test_output_placed_in_dated_folder(tmp_path: Path) -> None:
    """Output path is always the dated folder, never the bare parent."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    with patch(f"{_MOD}._ask_select", return_value="__default__"):
        result = _prompt_output_dir(input_path)
    assert result != tmp_path
    assert result.parent == tmp_path


def test_prompt_output_dir_claude_prefix(tmp_path: Path) -> None:
    """Claude format produces a claude-convert- prefixed folder."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    with patch(f"{_MOD}._ask_select", return_value="__default__"):
        result = _prompt_output_dir(input_path, fmt="claude")
    assert result.name.startswith("claude-convert-")


# ---------------------------------------------------------------------------
# detect_format_from_path
# ---------------------------------------------------------------------------


def _write_zip(path: Path, conversations: list) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("conversations.json", json.dumps(conversations))


def test_detect_format_claude_zip(tmp_path: Path) -> None:
    """Zip with chat_messages key is detected as claude."""
    zp = tmp_path / "claude.zip"
    _write_zip(zp, [{"uuid": "x", "chat_messages": []}])
    assert detect_format_from_path(zp) == "claude"


def test_detect_format_chatgpt_zip(tmp_path: Path) -> None:
    """Zip with mapping key is detected as chatgpt."""
    zp = tmp_path / "chatgpt.zip"
    _write_zip(zp, [{"id": "x", "mapping": {}}])
    assert detect_format_from_path(zp) == "chatgpt"


def test_detect_format_claude_dir(tmp_path: Path) -> None:
    """Directory with chat_messages conversations.json is detected as claude."""
    (tmp_path / "conversations.json").write_text(json.dumps([{"uuid": "x", "chat_messages": []}]))
    assert detect_format_from_path(tmp_path) == "claude"


def test_detect_format_chatgpt_dir(tmp_path: Path) -> None:
    """Directory with mapping conversations.json is detected as chatgpt."""
    (tmp_path / "conversations.json").write_text(json.dumps([{"id": "x", "mapping": {}}]))
    assert detect_format_from_path(tmp_path) == "chatgpt"


def test_detect_format_unknown_for_unrecognised_file(tmp_path: Path) -> None:
    """Non-zip, non-directory path returns unknown."""
    f = tmp_path / "data.json"
    f.write_text("{}")
    assert detect_format_from_path(f) == "unknown"
