"""Tests for choose_conversation_path ordering."""

from __future__ import annotations

from chatgpt_export_converter.converter import choose_conversation_path


def _node(node_id: str, create_time: float | None = None) -> dict:
    return {
        "id": node_id,
        "parent": None,
        "children": [],
        "message": {
            "id": node_id,
            "author": {"role": "user", "name": None, "metadata": {}},
            "create_time": create_time,
            "update_time": None,
            "content": {"content_type": "text", "parts": [f"msg {node_id}"]},
            "status": "finished_successfully",
            "end_turn": False,
            "weight": 1.0,
            "metadata": {},
            "recipient": "all",
        },
    }


def test_fallback_sort_is_deterministic_without_timestamps() -> None:
    """Nodes with no create_time are sorted by ID — order is consistent across calls."""
    conv = {
        "id": "c1", "title": "T", "current_node": None,
        "mapping": {
            "node-b": _node("node-b"),
            "node-a": _node("node-a"),
            "node-c": _node("node-c"),
        },
    }
    result1 = choose_conversation_path(conv)
    result2 = choose_conversation_path(conv)
    ids1 = [n["id"] for n in result1]
    ids2 = [n["id"] for n in result2]
    assert ids1 == ids2 == ["node-a", "node-b", "node-c"]


def test_fallback_sort_by_timestamp_when_available() -> None:
    """Nodes with create_time are sorted chronologically."""
    conv = {
        "id": "c1", "title": "T", "current_node": None,
        "mapping": {
            "node-z": _node("node-z", create_time=1700000003.0),
            "node-a": _node("node-a", create_time=1700000001.0),
            "node-m": _node("node-m", create_time=1700000002.0),
        },
    }
    result = choose_conversation_path(conv)
    ids = [n["id"] for n in result]
    assert ids == ["node-a", "node-m", "node-z"]


def test_current_node_path_used_when_present() -> None:
    """When current_node is valid, walk the parent chain instead of sorting."""
    conv = {
        "id": "c1", "title": "T", "current_node": "node-2",
        "mapping": {
            "node-1": {**_node("node-1"), "children": ["node-2"]},
            "node-2": {**_node("node-2"), "parent": "node-1"},
        },
    }
    result = choose_conversation_path(conv)
    ids = [n["id"] for n in result]
    assert ids == ["node-1", "node-2"]
