"""Tests for conversation_signature stability."""

from __future__ import annotations

from chatgpt_export_converter.converter import conversation_signature


def _msg(mid: str, create_time: float, update_time: float | None = None) -> dict:
    return {"id": mid, "create_time": create_time, "update_time": update_time}


def _conv(cid: str) -> dict:
    return {"id": cid, "title": "Test", "create_time": 1700000000.0, "current_node": "m1"}


def test_signature_stable_when_update_time_added(  ) -> None:
    """Adding update_time to a message does not change the signature."""
    conv = _conv("c1")
    msgs = [_msg("m1", 1700000001.0, update_time=None)]

    sig_before = conversation_signature(conv, msgs, [], 1)

    msgs_with_update = [_msg("m1", 1700000001.0, update_time=1700000099.0)]
    sig_after = conversation_signature(conv, msgs_with_update, [], 1)

    assert sig_before == sig_after


def test_signature_changes_when_content_changes() -> None:
    """A new message ID changes the signature."""
    conv = _conv("c1")
    msgs_v1 = [_msg("m1", 1700000001.0)]
    msgs_v2 = [_msg("m1", 1700000001.0), _msg("m2", 1700000002.0)]

    assert conversation_signature(conv, msgs_v1, [], 1) != \
           conversation_signature(conv, msgs_v2, [], 2)


def test_signature_changes_when_title_changes() -> None:
    conv_v1 = {"id": "c1", "title": "Old Title", "create_time": 1700000000.0, "current_node": "m1"}
    conv_v2 = {"id": "c1", "title": "New Title", "create_time": 1700000000.0, "current_node": "m1"}
    msgs = [_msg("m1", 1700000001.0)]

    assert conversation_signature(conv_v1, msgs, [], 1) != \
           conversation_signature(conv_v2, msgs, [], 1)


def test_signature_changes_when_assets_change() -> None:
    conv = _conv("c1")
    msgs = [_msg("m1", 1700000001.0)]

    assert conversation_signature(conv, msgs, [], 1) != \
           conversation_signature(conv, msgs, ["file-ABC123"], 1)
