"""Tests for CLI menu helpers."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from chatgpt_export_converter.converter import (
    _find_zip_in_dir,
    _output_folder_name,
    _prompt_output_dir,
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
