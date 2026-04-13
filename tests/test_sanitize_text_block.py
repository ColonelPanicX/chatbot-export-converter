"""Tests for sanitize_text_block placeholder escaping."""

from __future__ import annotations

from chatbot_export_converter.converter import sanitize_text_block


def test_bare_placeholder_encoded() -> None:
    assert sanitize_text_block("see assets/<file-123>") == "see assets/&lt;file-123&gt;"


def test_image_link_placeholder_escaped() -> None:
    result = sanitize_text_block("![image](assets/<file-123>)")
    assert result == "!\\[image\\](assets/&lt;file-123&gt;)"


def test_download_link_placeholder_escaped() -> None:
    result = sanitize_text_block("[download file](assets/<file-123>)")
    assert result == "\\[download file\\](assets/&lt;file-123&gt;)"


def test_audio_link_placeholder_escaped() -> None:
    result = sanitize_text_block("[audio file](assets/<file-123>)")
    assert result == "\\[audio file\\](assets/&lt;file-123&gt;)"


def test_real_link_not_modified() -> None:
    """Valid asset links (no angle brackets) pass through unchanged."""
    real = "![image](assets/file-ABC123-photo.png)"
    assert sanitize_text_block(real) == real


def test_plain_text_unchanged() -> None:
    assert sanitize_text_block("just some text") == "just some text"


def test_multiple_placeholders_in_one_string() -> None:
    text = "![image](assets/<file-1>) and assets/<file-2>"
    result = sanitize_text_block(text)
    assert "!\\[image\\](assets/&lt;file-1&gt;)" in result
    assert "assets/&lt;file-2&gt;" in result
