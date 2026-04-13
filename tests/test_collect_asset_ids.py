"""Tests for collect_asset_ids_from_obj depth limit and key-based collection."""

from __future__ import annotations

from chatgpt_export_converter.converter import _MAX_COLLECT_DEPTH, collect_asset_ids_from_obj


def test_asset_pointer_key_collected() -> None:
    # asset_pointer values are direct IDs (not URL-scheme strings)
    out: list[str] = []
    collect_asset_ids_from_obj({"asset_pointer": "file-ABC123"}, out)
    assert "file-ABC123" in out


def test_file_id_starting_with_file_dash_collected() -> None:
    out: list[str] = []
    collect_asset_ids_from_obj({"id": "file-XYZ789"}, out)
    assert "file-XYZ789" in out


def test_arbitrary_string_not_collected() -> None:
    """Strings not under a known key are no longer scanned — reduces false positives."""
    out: list[str] = []
    collect_asset_ids_from_obj({"text": "Some text with file-ABC123 in it"}, out)
    assert out == []


def test_depth_limit_prevents_deep_recursion() -> None:
    """Objects nested beyond _MAX_COLLECT_DEPTH are skipped without error."""
    # Build a chain _MAX_COLLECT_DEPTH + 5 levels deep
    deep: dict = {"asset_pointer": "file-DEEP999"}
    for _ in range(_MAX_COLLECT_DEPTH + 5):
        deep = {"nested": deep}

    out: list[str] = []
    collect_asset_ids_from_obj(deep, out)
    # The deeply nested asset should NOT be collected (depth limit hit)
    assert "file-DEEP999" not in out


def test_shallow_nesting_still_collected() -> None:
    """Assets within the depth limit are still found."""
    obj = {"level1": {"level2": {"asset_pointer": "file-SHALLOW01"}}}
    out: list[str] = []
    collect_asset_ids_from_obj(obj, out)
    assert "file-SHALLOW01" in out


def test_list_items_traversed() -> None:
    obj = [{"asset_pointer": "file-LIST001"}, {"asset_pointer": "file-LIST002"}]
    out: list[str] = []
    collect_asset_ids_from_obj(obj, out)
    assert "file-LIST001" in out
    assert "file-LIST002" in out
