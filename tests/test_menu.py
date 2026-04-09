"""Tests for CLI menu helpers."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from chatgpt_export_converter.converter import (
    _output_folder_name,
    _prompt_output_dir,
)


def test_output_folder_name_format() -> None:
    """Output folder name matches chatgpt-convert-MM.DD.YYYY."""
    import re
    name = _output_folder_name()
    assert re.match(r"chatgpt-convert-\d{2}\.\d{2}\.\d{4}$", name), (
        f"Unexpected folder name format: {name}"
    )


def test_prompt_output_dir_default(tmp_path: Path) -> None:
    """Choosing option 1 returns input_path.parent / folder_name."""
    input_path = tmp_path / "export.zip"
    input_path.touch()

    with patch("builtins.input", return_value="1"):
        result = _prompt_output_dir(input_path)

    assert result.parent == tmp_path
    assert result.name.startswith("chatgpt-convert-")


def test_prompt_output_dir_empty_input_uses_default(tmp_path: Path) -> None:
    """Pressing enter (empty) on the choice selects option 1."""
    input_path = tmp_path / "export.zip"
    input_path.touch()

    with patch("builtins.input", return_value=""):
        result = _prompt_output_dir(input_path)

    assert result.parent == tmp_path
    assert result.name.startswith("chatgpt-convert-")


def test_prompt_output_dir_custom(tmp_path: Path) -> None:
    """Choosing option 2 and entering a custom path uses that path."""
    input_path = tmp_path / "export.zip"
    input_path.touch()
    custom_parent = tmp_path / "custom"

    responses = iter(["2", str(custom_parent)])
    with patch("builtins.input", side_effect=responses):
        result = _prompt_output_dir(input_path)

    assert result.parent == custom_parent
    assert result.name.startswith("chatgpt-convert-")


def test_output_placed_inside_folder_named_by_date(tmp_path: Path) -> None:
    """The final output path always ends in the dated folder, not a bare parent."""
    input_path = tmp_path / "export.zip"
    input_path.touch()

    with patch("builtins.input", return_value="1"):
        result = _prompt_output_dir(input_path)

    # Must not be the bare parent
    assert result != tmp_path
    # Must be one level deep from the parent
    assert result.parent == tmp_path
