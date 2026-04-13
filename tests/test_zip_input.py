"""Tests for zip file input handling."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from chatbot_export_converter.converter import extracted_input


def make_zip(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a zip file containing the given filename->content mapping."""
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return zip_path


def test_directory_input_passthrough(tmp_path: Path) -> None:
    """A directory input is yielded unchanged."""
    with extracted_input(tmp_path) as result:
        assert result == tmp_path


def test_zip_extracted_to_temp_dir(tmp_path: Path) -> None:
    """A zip input is extracted to a temp directory."""
    conversations = json.dumps([{"id": "abc", "title": "test", "mapping": {}}])
    zip_path = make_zip(tmp_path, {"conversations.json": conversations})

    with extracted_input(zip_path) as result:
        assert result != zip_path
        assert result.is_dir()
        assert (result / "conversations.json").exists()


def test_zip_temp_dir_cleaned_up(tmp_path: Path) -> None:
    """Temp directory is removed after the context manager exits."""
    zip_path = make_zip(tmp_path, {"conversations.json": "[]"})

    with extracted_input(zip_path) as result:
        temp_dir = result

    assert not temp_dir.exists()


def test_zip_multiple_files_extracted(tmp_path: Path) -> None:
    """All files in the zip are extracted."""
    zip_path = make_zip(
        tmp_path,
        {
            "conversations.json": "[]",
            "user.json": "{}",
            "chat.html": "<html></html>",
        },
    )

    with extracted_input(zip_path) as result:
        assert (result / "conversations.json").exists()
        assert (result / "user.json").exists()
        assert (result / "chat.html").exists()


def test_zip_temp_dir_cleaned_up_on_exception(tmp_path: Path) -> None:
    """Temp directory is removed even if an exception occurs inside the block."""
    zip_path = make_zip(tmp_path, {"conversations.json": "[]"})

    temp_dir = None
    with pytest.raises(RuntimeError):
        with extracted_input(zip_path) as result:
            temp_dir = result
            raise RuntimeError("simulated failure")

    assert temp_dir is not None
    assert not temp_dir.exists()
