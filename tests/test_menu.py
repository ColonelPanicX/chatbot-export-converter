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


def test_output_folder_name_format() -> None:
    """Output folder name matches chatgpt-convert-MM.DD.YYYY."""
    name = _output_folder_name()
    assert re.match(r"chatgpt-convert-\d{2}\.\d{2}\.\d{4}$", name), (
        f"Unexpected folder name format: {name}"
    )


def test_find_zip_in_dir_single(tmp_path: Path) -> None:
    """Returns the single zip found in the directory."""
    (tmp_path / "export.zip").touch()
    result = _find_zip_in_dir(tmp_path)
    assert result == tmp_path / "export.zip"


def test_find_zip_in_dir_none(tmp_path: Path) -> None:
    """Returns None when no zip files are present."""
    (tmp_path / "conversations.json").touch()
    result = _find_zip_in_dir(tmp_path)
    assert result is None


def test_find_zip_in_dir_multiple_prompts(tmp_path: Path) -> None:
    """Prompts user to choose when multiple zips are found."""
    (tmp_path / "export-a.zip").touch()
    (tmp_path / "export-b.zip").touch()
    with patch("builtins.input", return_value="1"):
        result = _find_zip_in_dir(tmp_path)
    assert result is not None
    assert result.suffix == ".zip"


def test_prompt_output_dir_default(tmp_path: Path) -> None:
    """Choosing option 1 returns input_path.parent / folder_name."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    with patch("builtins.input", return_value="1"):
        result = _prompt_output_dir(input_path)
    assert result.parent == tmp_path
    assert result.name.startswith("chatgpt-convert-")


def test_prompt_output_dir_empty_uses_default(tmp_path: Path) -> None:
    """Pressing enter (empty) selects option 1."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    with patch("builtins.input", return_value=""):
        result = _prompt_output_dir(input_path)
    assert result.parent == tmp_path
    assert result.name.startswith("chatgpt-convert-")


def test_prompt_output_dir_custom(tmp_path: Path) -> None:
    """Choosing option 2 and entering a path uses that location."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    custom_parent = tmp_path / "custom"
    responses = iter(["2", str(custom_parent)])
    with patch("builtins.input", side_effect=responses):
        result = _prompt_output_dir(input_path)
    assert result.parent == custom_parent
    assert result.name.startswith("chatgpt-convert-")


def test_output_placed_in_dated_folder(tmp_path: Path) -> None:
    """Output path is always the dated folder, never the bare parent."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    with patch("builtins.input", return_value="1"):
        result = _prompt_output_dir(input_path)
    assert result != tmp_path
    assert result.parent == tmp_path


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
    (tmp_path / "conversations.json").write_text(
        json.dumps([{"uuid": "x", "chat_messages": []}])
    )
    assert detect_format_from_path(tmp_path) == "claude"


def test_detect_format_chatgpt_dir(tmp_path: Path) -> None:
    """Directory with mapping conversations.json is detected as chatgpt."""
    (tmp_path / "conversations.json").write_text(
        json.dumps([{"id": "x", "mapping": {}}])
    )
    assert detect_format_from_path(tmp_path) == "chatgpt"


def test_detect_format_unknown_for_unrecognised_file(tmp_path: Path) -> None:
    """Non-zip, non-directory path returns unknown."""
    f = tmp_path / "data.json"
    f.write_text("{}")
    assert detect_format_from_path(f) == "unknown"
