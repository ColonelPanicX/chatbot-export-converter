"""Tests for message_to_markdown rendering."""

from __future__ import annotations

from chatgpt_export_converter.converter import message_to_markdown


def _msg(role: str, ctype: str, **content_fields) -> dict:
    return {
        "author": {"role": role, "name": None, "metadata": {}},
        "content": {"content_type": ctype, **content_fields},
        "metadata": {},
    }


def test_thoughts_single_line_in_blockquote() -> None:
    msg = _msg("assistant", "thoughts", text="Simple thought.")
    output = message_to_markdown(msg, {})
    assert "> [thoughts]" in output
    assert "> Simple thought." in output


def test_thoughts_multiline_all_lines_quoted() -> None:
    msg = _msg("assistant", "thoughts", text="First line.\n\nSecond paragraph.\n\nThird.")
    output = message_to_markdown(msg, {})
    lines = output.splitlines()
    # Every non-empty content line must start with ">"
    content_lines = [l for l in lines if l.strip() and not l.startswith("##")]
    assert all(l.startswith(">") for l in content_lines), (
        f"Not all lines are quoted:\n{output}"
    )


def test_reasoning_recap_multiline_all_lines_quoted() -> None:
    msg = _msg("assistant", "reasoning_recap", text="Step 1.\n\nStep 2.")
    output = message_to_markdown(msg, {})
    lines = output.splitlines()
    content_lines = [l for l in lines if l.strip() and not l.startswith("##")]
    assert all(l.startswith(">") for l in content_lines)


def test_plain_text_not_blockquoted() -> None:
    msg = _msg("user", "text", parts=["Hello there."])
    output = message_to_markdown(msg, {})
    assert "Hello there." in output
    assert not any(l.startswith(">") for l in output.splitlines() if "Hello" in l)
