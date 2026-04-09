"""Tests for date_from_timestamp fallback behavior."""

from __future__ import annotations

from chatgpt_export_converter.converter import date_from_timestamp


def test_valid_timestamp_returns_iso_date() -> None:
    assert date_from_timestamp(1700000000.0) == "2023-11-14"


def test_none_returns_undated() -> None:
    assert date_from_timestamp(None) == "undated"


def test_zero_converts_correctly() -> None:
    # Epoch zero is a valid timestamp — it converts to a real date, not "undated".
    assert date_from_timestamp(0) == "1970-01-01"


def test_empty_string_returns_undated() -> None:
    assert date_from_timestamp("") == "undated"


def test_invalid_string_returns_undated() -> None:
    assert date_from_timestamp("not-a-date") == "undated"


def test_iso_string_passthrough() -> None:
    assert date_from_timestamp("2024-06-15T12:00:00+00:00") == "2024-06-15"
