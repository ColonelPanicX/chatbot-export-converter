"""Tests for build_asset_index search consistency and extract_asset_id URL handling."""

from __future__ import annotations

from pathlib import Path

from chatbot_export_converter.converter import build_asset_index, extract_asset_id


def test_filename_starting_with_asset_id_is_indexed(tmp_path: Path) -> None:
    """Files whose names start with the asset ID pattern are indexed."""
    (tmp_path / "file-ABC123-image.png").touch()
    by_id, _ = build_asset_index(tmp_path)
    assert "file-ABC123" in by_id


def test_filename_with_prefix_before_asset_id_is_indexed(tmp_path: Path) -> None:
    """Files whose names contain the asset ID pattern after a prefix are also indexed.

    This was previously missed because build_asset_index used .match() (anchored)
    while collect_asset_ids_from_obj used .search() (anywhere). Now both use .search().
    """
    (tmp_path / "prefix-file-XYZ789-data.bin").touch()
    by_id, _ = build_asset_index(tmp_path)
    assert "file-XYZ789" in by_id


def test_all_files_collected_regardless_of_asset_id(tmp_path: Path) -> None:
    """all_files includes every file, even those without an asset ID in the name."""
    (tmp_path / "chat.html").touch()
    (tmp_path / "user.json").touch()
    (tmp_path / "file-ABC123.png").touch()
    _, all_files = build_asset_index(tmp_path)
    names = {p.name for p in all_files}
    assert names == {"chat.html", "user.json", "file-ABC123.png"}


def test_no_false_positives_for_non_asset_files(tmp_path: Path) -> None:
    """Files with no asset ID pattern are not added to the index."""
    (tmp_path / "conversations.json").touch()
    by_id, _ = build_asset_index(tmp_path)
    assert len(by_id) == 0


def test_extract_asset_id_strips_url_scheme() -> None:
    """URL-format asset pointers return the ID after the scheme, not the scheme prefix."""
    assert extract_asset_id("file-service://file-ABC123") == "file-ABC123"


def test_extract_asset_id_bare_id_unchanged() -> None:
    """Bare asset IDs (no scheme) are returned as-is."""
    assert extract_asset_id("file-ABC123") == "file-ABC123"


def test_extract_asset_id_underscore_format_after_scheme() -> None:
    """Underscore-format IDs after a URL scheme are extracted correctly."""
    assert extract_asset_id("file-service://file_0000000009e071f8") == "file_0000000009e071f8"
